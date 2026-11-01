import hashlib
import json
import os
import secrets
import smtplib
from email.message import EmailMessage
from datetime import timedelta
from functools import wraps
from flask import Blueprint, request, session, g, jsonify, render_template, current_app, send_from_directory
from sqlalchemy import select, delete, text
from sqlalchemy.dialects.postgresql import insert
from werkzeug.security import generate_password_hash, check_password_hash
from email_validator import validate_email, EmailNotValidError
import phonenumbers
from .models import User, Idempotency, LoginBucket, ResetToken, Shift, ShiftAudit, now
from .domain import Invalid, zone
from .services import (uid, owned, dashboard, save_workplace, save_shift,
                       confirm_payment, Conflict, NotFound)

bp = Blueprint('web', __name__)
DUMMY = generate_password_hash('dummy-password-not-a-user')


def identity(data):
    name = str(data.get('name', '')).strip()
    if not 1 <= len(name) <= 120:
        raise Invalid('Full name is required (maximum 120 characters).')
    try:
        email = validate_email(str(data.get('email', '')).strip(), check_deliverability=False).normalized.casefold()
        phone = phonenumbers.parse(str(data.get('phone', '')), None)
        if not phonenumbers.is_valid_number(phone):
            raise ValueError()
        phone = phonenumbers.format_number(phone, phonenumbers.PhoneNumberFormat.E164)
    except (EmailNotValidError, phonenumbers.NumberParseException, ValueError):
        raise Invalid('Enter a valid email and phone number including country code (e.g. +61).')
    return name, email, phone, zone(data.get('timezone', 'Australia/Sydney'))


def password(value):
    if not isinstance(value, str) or not 6 <= len(value) <= 128:
        raise Invalid('Password must contain 6–128 characters.')
    return generate_password_hash(value)


def throttle(label, limit=10):
    """Shared PostgreSQL rate bucket. Commit independently of login outcome."""
    key = hashlib.sha256((label + '|' + (request.remote_addr or '')).encode()).hexdigest()
    with current_app.extensions['db_factory'].begin() as db:
        db.execute(delete(LoginBucket).where(LoginBucket.expires < now() - timedelta(days=1)))
        stmt = insert(LoginBucket).values(key=key, count=0, expires=now() + timedelta(minutes=15)).on_conflict_do_nothing()
        db.execute(stmt)
        bucket = db.scalar(select(LoginBucket).where(LoginBucket.key == key).with_for_update())
        if bucket.expires <= now():
            bucket.count = 0
            bucket.expires = now() + timedelta(minutes=15)
        bucket.count += 1
        blocked = bucket.count > limit
    if blocked:
        return jsonify(error='Too many attempts. Try again in 15 minutes.'), 429


def mutate(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            raise Invalid('A JSON object is required.')
        key = uid(request.headers.get('Idempotency-Key'))
        fingerprint = hashlib.sha256((request.path + json.dumps(body, sort_keys=True)).encode()).hexdigest()
        # Same user lock also protects workplace count and concurrent replays.
        g.db.execute(select(User.id).where(User.id == g.user.id).with_for_update())
        g.db.refresh(g.user)
        if g.user.session_version != session.get('version'):
            session.clear()
            return jsonify(error='Sign in again to continue.'), 401
        old = g.db.get(Idempotency, (g.user.id, key))
        if old:
            if old.fingerprint != fingerprint:
                raise Conflict('Idempotency key was already used for a different request.')
            return jsonify(old.response)
        response = fn(body, *args, **kwargs)
        g.db.add(Idempotency(user_id=g.user.id, key=key, fingerprint=fingerprint, response=response))
        g.db.commit()
        return jsonify(response)
    return wrapped


@bp.route('/auth', methods=['GET', 'POST'])
def auth():
    if request.method == 'GET':
        return render_template('auth.html', csrf=session['csrf'])
    data = request.get_json(silent=True) or request.form
    limited = throttle('auth:' + str(data.get('email', '')).strip().casefold())
    if limited:
        return limited
    mode = data.get('mode', 'login')
    if mode == 'register':
        name, email, phone, tz = identity(data)
        user = User(name=name, email=email, phone=phone, timezone=tz, password_hash=password(data.get('password')))
        g.db.add(user)
        g.db.commit()
    elif mode == 'login':
        login = str(data.get('email', '')).strip().casefold()
        user = g.db.scalar(select(User).where(User.email == login))
        valid = check_password_hash(user.password_hash if user else DUMMY, str(data.get('password', '')))
        if not user or not valid:
            return jsonify(error='Email or password is incorrect.'), 401
    elif mode == 'forgot':
        if not os.environ.get('SMTP_HOST') or not os.environ.get('MAIL_FROM'):
            return jsonify(error='Password reset delivery is not configured. Contact the server operator.'), 503
        user = g.db.scalar(select(User).where(User.email == str(data.get('email', '')).strip().casefold()))
        if user:
            token = secrets.token_urlsafe(32)
            digest = hashlib.sha256(token.encode()).hexdigest()
            g.db.add(ResetToken(digest=digest, user_id=user.id, expires=now()+timedelta(minutes=30)))
            message = EmailMessage()
            message['Subject'] = 'Reset your Hourly password'
            message['From'] = os.environ['MAIL_FROM']
            message['To'] = user.email
            message.set_content('Reset your password within 30 minutes:\n' + current_app.config['PUBLIC_URL'] + '/reset#' + token)
            try:
                with smtplib.SMTP(os.environ['SMTP_HOST'], int(os.environ.get('SMTP_PORT', '587')), timeout=10) as smtp:
                    smtp.starttls()
                    if os.environ.get('SMTP_USER'):
                        smtp.login(os.environ['SMTP_USER'], os.environ['SMTP_PASSWORD'])
                    smtp.send_message(message)
                g.db.commit()
            except (OSError, smtplib.SMTPException):
                g.db.rollback()
                current_app.logger.error('Password reset delivery failed')
                return jsonify(error='Password reset delivery is temporarily unavailable.'), 503
        return jsonify(message='If that account exists, a reset email has been sent.')
    else:
        raise Invalid('Unknown authentication action.')
    session.clear()
    session.update(user_id=str(user.id), version=user.session_version, csrf=secrets.token_urlsafe(32))
    session.permanent = True
    return jsonify(ok=True)


@bp.route('/reset', methods=['GET', 'POST'])
def reset():
    if request.method == 'GET':
        return render_template('reset.html', csrf=session['csrf'])
    limited = throttle('reset')
    if limited:
        return limited
    data = request.get_json(silent=True) or {}
    digest = hashlib.sha256(str(data.get('token', '')).encode()).hexdigest()
    token = g.db.scalar(select(ResetToken).where(ResetToken.digest == digest).with_for_update())
    if not token or token.used or token.expires < now():
        raise Invalid('Reset link expired or was already used.')
    user = g.db.scalar(select(User).where(User.id == token.user_id).with_for_update().execution_options(populate_existing=True))
    user.password_hash = password(data.get('password'))
    user.session_version += 1
    token.used = True
    g.db.commit()
    session.clear()
    return jsonify(ok=True)


@bp.get('/')
def index():
    return render_template('app.html', csrf=session['csrf'], user_id=str(g.user.id))


@bp.get('/api/session')
def session_data():
    return jsonify(csrf=session['csrf'], user=dict(id=str(g.user.id), name=g.user.name,
                   email=g.user.email, phone=g.user.phone, timezone=g.user.timezone))


@bp.post('/api/logout')
def logout():
    session.clear()
    return jsonify(ok=True)


@bp.post('/api/profile')
@mutate
def profile(data):
    name, email, phone, tz = identity(data)
    if email != g.user.email or phone != g.user.phone or data.get('new_password'):
        if not check_password_hash(g.user.password_hash, str(data.get('current_password', ''))):
            raise Invalid('Current password is required to change email, phone or password.')
    g.user.name, g.user.email, g.user.phone, g.user.timezone = name, email, phone, tz
    if data.get('new_password'):
        g.user.password_hash = password(data['new_password'])
        g.user.session_version += 1
        session['version'] = g.user.session_version
    return {'ok':True}


@bp.get('/api/dashboard')
def report():
    return jsonify(dashboard(g.db, g.user, request.args.get('workplace'), request.args.get('period', 'Week'), request.args.get('offset', 0)))


@bp.post('/api/workplaces')
@mutate
def workplace_create(data):
    return save_workplace(g.db, g.user, data)


@bp.post('/api/workplaces/<identifier>')
@mutate
def workplace_update(data, identifier):
    return save_workplace(g.db, g.user, data, identifier)


@bp.post('/api/workplaces/<identifier>/shifts')
@mutate
def shift_save(data, identifier):
    return save_shift(g.db, g.user, identifier, data)


@bp.get('/api/shifts/<identifier>/history')
def history(identifier):
    s = g.db.get(Shift, uid(identifier))
    if not s:
        raise NotFound('Shift not found.')
    owned(g.db, g.user, s.workplace_id)
    rows = g.db.scalars(select(ShiftAudit).where(ShiftAudit.shift_id == s.id).order_by(ShiftAudit.id.desc()).limit(100)).all()
    return jsonify(items=[dict(action=a.action, at=a.created_at.isoformat(), snapshot=a.snapshot) for a in rows])


@bp.post('/api/workplaces/<identifier>/payments')
@mutate
def payment_save(data, identifier):
    return confirm_payment(g.db, g.user, identifier, data)


@bp.get('/offline')
def offline():
    return render_template('app.html', csrf='', user_id='')


@bp.get('/sw.js')
def worker():
    return send_from_directory(current_app.static_folder, 'sw.js', mimetype='application/javascript')


@bp.get('/health')
def health():
    g.db.execute(text('SELECT 1'))
    return jsonify(status='ok', version='1.0.0')

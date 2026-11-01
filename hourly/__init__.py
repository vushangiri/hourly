"""Flask factory, request-scoped transactions and security boundaries."""
import os
import secrets
from datetime import timedelta
from flask import Flask, g, request, session, jsonify, redirect, url_for
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from .models import User
from .domain import Invalid
from .services import Conflict, NotFound, uid


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get('SECRET_KEY'),
        DATABASE_URL=os.environ.get('DATABASE_URL', 'postgresql+psycopg://hourly:hourly@localhost:5432/hourly'),
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE', '1') == '1',
        PERMANENT_SESSION_LIFETIME=timedelta(days=14), MAX_CONTENT_LENGTH=32 * 1024,
        PUBLIC_URL=os.environ.get('PUBLIC_URL', 'http://localhost:8080').rstrip('/'),
    )
    if test_config:
        app.config.update(test_config)
    if not app.config['SECRET_KEY'] or len(app.config['SECRET_KEY']) < 32 or app.config['SECRET_KEY'].startswith('REPLACE_'):
        raise RuntimeError('Set SECRET_KEY to a random value of at least 32 characters.')
    if not app.config['DATABASE_URL'].startswith('postgresql'):
        raise RuntimeError('PostgreSQL is required; SQLite is not supported.')
    engine = create_engine(app.config['DATABASE_URL'], pool_pre_ping=True, pool_size=5, max_overflow=5)
    app.extensions['engine'] = engine
    app.extensions['db_factory'] = sessionmaker(engine, expire_on_commit=False)

    @app.before_request
    def begin():
        g.db = app.extensions['db_factory']()
        g.user = None
        if session.get('user_id'):
            g.user = g.db.get(User, uid(session['user_id']))
            if not g.user or g.user.session_version != session.get('version'):
                session.clear()
                g.user = None
        if 'csrf' not in session:
            session['csrf'] = secrets.token_urlsafe(32)
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            token = request.headers.get('X-CSRF-Token') or request.form.get('csrf') or ''
            if not secrets.compare_digest(token, session['csrf']):
                return jsonify(error='Session expired. Reload and try again.'), 400
        public = {'web.auth', 'web.reset', 'web.offline', 'web.worker', 'web.health', 'static'}
        if request.endpoint and request.endpoint not in public and not g.user:
            if request.path.startswith('/api/'):
                return jsonify(error='Sign in again to continue.'), 401
            return redirect(url_for('web.auth'))

    @app.after_request
    def security(response):
        response.headers.update({
            'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY',
            'Referrer-Policy': 'same-origin', 'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
        })
        if request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        if not request.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.teardown_request
    def finish(exc):
        if hasattr(g, 'db'):
            g.db.rollback()
            g.db.close()

    @app.errorhandler(Invalid)
    def invalid(exc):
        g.db.rollback()
        return jsonify(error=str(exc)), 409 if isinstance(exc, Conflict) else 404 if isinstance(exc, NotFound) else 422

    @app.errorhandler(IntegrityError)
    def integrity(exc):
        g.db.rollback()
        return jsonify(error='A record with these details already exists. Reload and check your entry.'), 409

    from .web import bp
    app.register_blueprint(bp)
    from .cli import register
    register(app)
    return app

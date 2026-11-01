"""Transactional use cases. Call inside a Session transaction."""
from datetime import timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo
from sqlalchemy import select, func
from .models import User, Workplace, Schedule, Shift, ShiftAudit, Payment, now
from .domain import Invalid, config, day, timestamps, calculate, period_range, pay_range, next_payday, decimal, integer


class Conflict(Invalid):
    pass


class NotFound(Invalid):
    pass


def uid(value):
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        raise NotFound('Record not found.')


def owned(db, user, identifier, lock=False):
    q = select(Workplace).where(Workplace.id == uid(identifier), Workplace.user_id == user.id)
    if lock:
        q = q.with_for_update()
    w = db.scalar(q)
    if not w:
        raise NotFound('Workplace not found.')
    return w


def revisions(db, w):
    return db.scalars(select(Schedule).where(Schedule.workplace_id == w.id).order_by(Schedule.effective_date, Schedule.revision)).all()


def applicable(rows, d):
    choices = [r for r in rows if r.effective_date <= d]
    return choices[-1].config if choices else None


def workplace_json(w, rows):
    latest = rows[-1]
    return dict(id=str(w.id), name=w.name, description=w.description, contact=w.contact,
                archived=w.archived, revision=w.revision, effective_date=latest.effective_date.isoformat(), **latest.config)


def save_workplace(db, user, data, identifier=None):
    # All creations and idempotent mutations serialize through the account row.
    db.execute(select(User.id).where(User.id == user.id).with_for_update())
    if not isinstance(data.get('name'), str) or not data['name'].strip() or len(data['name']) > 120:
        raise Invalid('Workplace name is required (maximum 120 characters).')
    c = config(data, user.timezone)
    today = now().astimezone(ZoneInfo(c['timezone'])).date()
    if identifier:
        w = owned(db, user, identifier, True)
        if integer(data.get('revision', 0), 0, 100000000) != w.revision:
            raise Conflict('Workplace changed. Reload before saving.')
        # Reconcile old completed schedule first, preserving history.
        reconcile(db, w, now())
        w.revision += 1
        effective = max(today + timedelta(days=1), revisions(db, w)[-1].effective_date)
    else:
        count = db.scalar(select(func.count()).select_from(Workplace).where(Workplace.user_id == user.id))
        if count >= 3:
            raise Invalid('Maximum three workplaces, including archived workplaces.')
        w = Workplace(user_id=user.id, name=data['name'].strip(), cursor=today)
        db.add(w)
        db.flush()
        effective = today
    w.name = data['name'].strip()
    w.description = str(data.get('description', ''))[:500]
    w.contact = str(data.get('contact', ''))[:200]
    archived = data.get('archived', False)
    if not isinstance(archived, bool):
        raise Invalid('Invalid archive setting.')
    w.archived = archived
    if archived:
        c['auto'] = False
    db.add(Schedule(workplace_id=w.id, revision=w.revision, effective_date=effective, config=c))
    db.flush()
    return workplace_json(w, revisions(db, w))


def shift_json(s):
    tz = ZoneInfo(s.timezone)
    return dict(id=str(s.id), workplace_id=str(s.workplace_id), date=s.local_date.isoformat(),
                slot=s.slot, start=s.start_at.astimezone(tz).strftime('%H:%M') if s.start_at else '',
                end=s.end_at.astimezone(tz).strftime('%H:%M') if s.end_at else '',
                start_at=s.start_at.isoformat() if s.start_at else None,
                end_at=s.end_at.isoformat() if s.end_at else None,
                start_fold=s.start_at.astimezone(tz).fold if s.start_at else 0,
                end_fold=s.end_at.astimezone(tz).fold if s.end_at else 0,
                breaks=s.break_minutes, seconds=s.net_seconds, rate=str(s.rate), earnings=str(s.earnings),
                status=s.status, origin=s.origin, revision=s.revision, timezone=s.timezone)


def audit(db, s, actor, action):
    db.flush()
    db.add(ShiftAudit(shift_id=s.id, actor_id=actor, action=action, snapshot=shift_json(s)))


def scheduled_shift(db, w, d, c, at):
    if not c or not c['auto'] or d.weekday() not in c['workdays']:
        return True
    s, e = timestamps(d, c['start'], c['end'], c['timezone'])
    if e > at:
        return False
    existing = db.scalar(select(Shift).where(Shift.workplace_id == w.id, Shift.local_date == d, Shift.slot == 'scheduled'))
    if not existing or existing.status == 'planned':
        overlap_query = select(Shift.id).where(Shift.workplace_id == w.id, Shift.status.in_(['manual', 'auto']), Shift.start_at < e, Shift.end_at > s)
        overlap = db.scalar(overlap_query)
        if overlap:
            entry = existing or Shift(workplace_id=w.id, local_date=d, slot='scheduled', timezone=c['timezone'],
                          rate=Decimal(c['rate']), earnings=Decimal(0), status='off', origin='auto')
            if existing:
                entry.status = 'off'
                entry.start_at = entry.end_at = None
                entry.revision += 1
            db.add(entry)
            audit(db, entry, None, 'overlap-review-required')
            return True
        seconds, earnings = calculate(s, e, c['breaks'], c['rate'])
        entry = existing or Shift(workplace_id=w.id, local_date=d, slot='scheduled', start_at=s, end_at=e,
                      timezone=c['timezone'], break_minutes=c['breaks'], net_seconds=seconds,
                      rate=Decimal(c['rate']), earnings=earnings, status='auto', origin='auto')
        if existing:
            entry.start_at, entry.end_at, entry.timezone = s, e, c['timezone']
            entry.break_minutes, entry.net_seconds = c['breaks'], seconds
            entry.rate, entry.earnings, entry.status = Decimal(c['rate']), earnings, 'auto'
            entry.revision += 1
        db.add(entry)
        audit(db, entry, None, 'generated')
    return True


def reconcile(db, w, at, batch=62):
    """Caller holds workplace lock. Bounded recovery; cursor persists atomically."""
    rows = revisions(db, w)
    if not rows:
        return 0
    today = at.astimezone(ZoneInfo(rows[-1].config['timezone'])).date()
    count = 0
    while w.cursor <= today and count < batch:
        c = applicable(rows, w.cursor)
        # Spring gap schedules cannot be assigned correct timestamps automatically.
        # Keep a durable off record, with explicit audit reason; user can correct.
        try:
            done = scheduled_shift(db, w, w.cursor, c, at)
        except Invalid:
            existing = db.scalar(select(Shift).where(Shift.workplace_id == w.id, Shift.local_date == w.cursor, Shift.slot == 'scheduled'))
            if not existing or existing.status == 'planned':
                s = existing or Shift(workplace_id=w.id, local_date=w.cursor, slot='scheduled', timezone=c['timezone'],
                          rate=Decimal(c['rate']), earnings=Decimal(0), status='off', origin='auto')
                if existing:
                    s.status, s.net_seconds, s.earnings = 'off', 0, Decimal(0)
                    s.start_at = s.end_at = None
                    s.revision += 1
                db.add(s)
                audit(db, s, None, 'dst-review-required')
            done = True
        if not done:
            break
        w.cursor += timedelta(days=1)
        count += 1
    return count


def save_shift(db, user, workplace_id, data):
    w = owned(db, user, workplace_id, True)
    if w.archived:
        raise Invalid('Restore the workplace before editing shifts.')
    rows = revisions(db, w)
    d = day(data.get('date'))
    if d.year < 2000 or d.year > 2100:
        raise Invalid('Shift date must be between 2000 and 2100.')
    c = applicable(rows, d) or rows[0].config
    slot = data.get('slot', 'scheduled')
    if slot != 'scheduled':
        slot = str(uid(slot))
    s = db.scalar(select(Shift).where(Shift.workplace_id == w.id, Shift.local_date == d, Shift.slot == slot))
    revision = integer(data.get('revision', 0), 0, 100000000)
    if (s.revision if s else 0) != revision:
        raise Conflict('This shift changed on another device. Review the latest record before retrying.')
    action = data.get('action', 'save')
    if action not in ('save', 'off', 'restore'):
        raise Invalid('Unknown shift action.')
    if action == 'restore' and slot != 'scheduled':
        raise Invalid('Restore applies to the scheduled shift only.')
    if not s:
        s = Shift(workplace_id=w.id, local_date=d, slot=slot, timezone=c['timezone'],
                  rate=Decimal(c['rate']), earnings=Decimal(0), status='manual', origin='manual')
        db.add(s)
    else:
        s.revision += 1
    if action == 'off':
        s.status, s.net_seconds, s.earnings = 'off', 0, Decimal(0)
        s.start_at = s.end_at = None
        s.break_minutes = 0
    else:
        values = c if action == 'restore' else data
        tz = s.timezone
        a, b = timestamps(d, values.get('start'), values.get('end'), tz,
                          integer(values.get('start_fold', 0), 0, 1), integer(values.get('end_fold', 0), 0, 1))
        future = b > now()
        if future and action != 'restore':
            raise Invalid('A shift can only be recorded after it has ended.')
        # Prevent two saved shifts charging for the same instant in one workplace.
        with db.no_autoflush:
            query = select(Shift.id).where(Shift.workplace_id == w.id, Shift.status.in_(['manual', 'auto']), Shift.start_at < b, Shift.end_at > a)
            if s.id:
                query = query.where(Shift.id != s.id)
            if db.scalar(query):
                raise Invalid('This shift overlaps another recorded shift at this workplace.')
        breaks = integer(values.get('breaks', 0), 0, 1500)
        seconds, earnings = calculate(a, b, breaks, s.rate)
        s.start_at, s.end_at, s.break_minutes = a, b, breaks
        s.net_seconds, s.earnings, s.status = (0, Decimal(0), 'planned') if future else (seconds, earnings, 'manual')
    audit(db, s, user.id, action)
    return shift_json(s)


def dashboard(db, user, identifier, period, offset, reference=None):
    all_mode = identifier == 'all'
    workplaces = db.scalars(select(Workplace).where(Workplace.user_id == user.id).order_by(Workplace.created_at)).all()
    if not workplaces:
        return dict(workplaces=[], days=[], summary={'seconds':0, 'earnings':'0.00', 'manual':0, 'auto':0})
    selected = workplaces if all_mode else [owned(db, user, identifier or workplaces[0].id)]
    schedule_rows = db.scalars(select(Schedule).where(Schedule.workplace_id.in_([w.id for w in workplaces])).order_by(Schedule.effective_date, Schedule.revision)).all()
    grouped = {w.id: [r for r in schedule_rows if r.workplace_id == w.id] for w in workplaces}
    latest = grouped[selected[0].id][-1].config
    today = (reference or now()).astimezone(ZoneInfo(user.timezone if all_mode else latest['timezone'])).date()
    active_config = applicable(grouped[selected[0].id], today) or latest
    start, end = period_range(today, period, offset, None if all_mode else active_config)
    ids = [w.id for w in selected]
    entries = db.scalars(select(Shift).where(Shift.workplace_id.in_(ids), Shift.local_date.between(start, end)).order_by(Shift.local_date, Shift.slot)).all()
    days = []
    for w in selected:
        d = start
        while d <= end:
            found = [s for s in entries if s.workplace_id == w.id and s.local_date == d]
            for s in found:
                days.append(dict(workplace=w.name, **shift_json(s)))
            if not any(s.slot == 'scheduled' for s in found):
                c = applicable(grouped[w.id], d)
                planned = c and d.weekday() in c['workdays'] and not w.archived
                days.append(dict(id=None, workplace_id=str(w.id), workplace=w.name, date=d.isoformat(), slot='scheduled',
                                 status='planned' if planned else 'off', origin=None, revision=0,
                                 start=c['start'] if c else latest['start'], end=c['end'] if c else latest['end'],
                                 breaks=c['breaks'] if c else 0, seconds=0, earnings='0.00', timezone=c['timezone'] if c else latest['timezone']))
            d += timedelta(days=1)
    days.sort(key=lambda x: (x['date'], x['workplace'], x['slot']))
    total_seconds = sum(s.net_seconds for s in entries)
    total_earnings = sum((s.earnings for s in entries), Decimal(0))
    payments = []
    for w in selected:
        c = applicable(grouped[w.id], today) or grouped[w.id][-1].config
        # Bounded payment history for visible report. Unpaid uses SQL NOT EXISTS across all history.
        ps = db.scalars(select(Payment).where(Payment.workplace_id == w.id, Payment.period_start <= end, Payment.period_end >= start)).all()
        unpaid = db.scalar(select(func.coalesce(func.sum(Shift.earnings), 0)).where(Shift.workplace_id == w.id,
            ~select(Payment.id).where(Payment.workplace_id == w.id, Payment.period_start <= Shift.local_date, Payment.period_end >= Shift.local_date).exists()))
        pay_start, pay_end = pay_range(start, applicable(grouped[w.id], start) or grouped[w.id][0].config)
        estimate = db.scalar(select(func.coalesce(func.sum(Shift.earnings), 0)).where(Shift.workplace_id == w.id, Shift.local_date.between(pay_start, pay_end)))
        adjustments = db.scalar(select(func.coalesce(func.sum(Shift.earnings), 0)).where(Shift.workplace_id == w.id,
            select(Payment.id).where(Payment.workplace_id == w.id, Payment.period_start <= Shift.local_date, Payment.period_end >= Shift.local_date).exists()))
        confirmed_total = db.scalar(select(func.coalesce(func.sum(Payment.confirmed_estimate), 0)).where(Payment.workplace_id == w.id))
        payments.append(dict(adjustment=str(adjustments - confirmed_total), workplace_id=str(w.id), name=w.name, next_payday=next_payday(today, c).isoformat(),
            unpaid=str(unpaid), period_start=pay_start.isoformat(), period_end=pay_end.isoformat(), estimate=str(estimate),
            confirmed=[dict(id=str(p.id), start=p.period_start.isoformat(), end=p.period_end.isoformat(), paid_date=p.paid_date.isoformat(),
                            amount=str(p.actual_amount) if p.actual_amount is not None else None, estimate=str(p.confirmed_estimate)) for p in ps]))
    return dict(workplaces=[workplace_json(w, grouped[w.id]) for w in workplaces], days=days,
                start=start.isoformat(), end=end.isoformat(), today=today.isoformat(), payments=payments,
                summary=dict(seconds=total_seconds, earnings=str(total_earnings),
                             manual=sum(s.status == 'manual' for s in entries), auto=sum(s.status == 'auto' for s in entries)))


def confirm_payment(db, user, identifier, data):
    w = owned(db, user, identifier, True)
    rows = revisions(db, w)
    d = day(data.get('period_start'))
    c = applicable(rows, d) or rows[0].config
    start, end = pay_range(d, c)
    if start != d:
        raise Invalid('Payment start must match the configured pay cycle.')
    today = now().astimezone(ZoneInfo(c['timezone'])).date()
    paid = day(data.get('paid_date'))
    if end >= today or paid > today:
        raise Invalid('Confirm a completed pay period with a payment date no later than today.')
    overlap = db.scalar(select(Payment.id).where(Payment.workplace_id == w.id, Payment.period_start <= end, Payment.period_end >= start))
    if overlap:
        raise Conflict('This pay period overlaps an existing payment confirmation.')
    estimate = db.scalar(select(func.coalesce(func.sum(Shift.earnings), 0)).where(Shift.workplace_id == w.id, Shift.local_date.between(start, end)))
    amount = data.get('actual_amount')
    p = Payment(workplace_id=w.id, period_start=start, period_end=end, paid_date=paid,
                actual_amount=None if amount in ('', None) else decimal(amount), confirmed_estimate=estimate)
    db.add(p)
    db.flush()
    return {'id':str(p.id)}

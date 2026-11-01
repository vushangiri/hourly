import os
import time
import click
from sqlalchemy import select
from werkzeug.security import generate_password_hash
from .models import User, Workplace, now
from .services import reconcile, save_workplace


def scheduler_tick(factory):
    # Enumerate ids, then independent per-workplace transactions. SKIP LOCKED
    # allows multiple workers without duplicate processing or a global mutex.
    with factory() as db:
        ids = db.scalars(select(Workplace.id).order_by(Workplace.id)).all()
    processed = 0
    for identifier in ids:
        with factory.begin() as db:
            w = db.scalar(select(Workplace).where(Workplace.id == identifier).with_for_update(skip_locked=True))
            if w:
                processed += reconcile(db, w, now())
    return processed


def register(app):
    @app.cli.command('scheduler')
    @click.option('--once', is_flag=True)
    def scheduler(once):
        """Reconcile ended scheduled shifts; repeat every 30 seconds."""
        while True:
            try:
                count = scheduler_tick(app.extensions['db_factory'])
                if count:
                    app.logger.info('Reconciled %d local dates', count)
            except Exception:
                app.logger.exception('Scheduler pass failed; retrying without advancing failed cursor')
                if once:
                    raise
            if once:
                break
            time.sleep(30)

    @app.cli.command('seed-demo')
    def seed_demo():
        """Create a demo account only with an operator-supplied password."""
        secret = os.environ.get('DEMO_PASSWORD', '')
        if len(secret) < 12:
            raise click.ClickException('Set DEMO_PASSWORD (at least 12 characters).')
        with app.extensions['db_factory'].begin() as db:
            if db.scalar(select(User.id).where(User.email == 'demo@example.com')):
                raise click.ClickException('Demo account already exists.')
            u = User(name='Demo User', email='demo@example.com', phone='+61412345678', password_hash=generate_password_hash(secret))
            db.add(u)
            db.flush()
            save_workplace(db, u, dict(name='Car Wash', start='07:30', end='17:00', breaks=30,
                rate='25.00', workdays=[0,1,2,3,4,5], auto=True, weekStart=2, pay='Weekly',
                anchor='2026-01-07', payday=4, timezone='Australia/Sydney'))
        click.echo('Created demo@example.com. No artificial earnings were inserted.')

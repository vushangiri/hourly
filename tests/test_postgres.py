"""Real PostgreSQL tests; no SQLite substitution. Uses a disposable database."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from hourly.models import User, Workplace, Schedule, Shift, ShiftAudit, Payment
from hourly.services import (save_workplace, save_shift, reconcile, dashboard, confirm_payment,
                             Conflict, NotFound, Invalid, owned)
from hourly.cli import scheduler_tick
from hourly import create_app
from werkzeug.security import generate_password_hash

AT=datetime(2026,11,2,23,tzinfo=timezone.utc)


def data(**changes):
    d=dict(name='Car Wash',rate='25.00',start='07:30',end='17:00',breaks=30,workdays=[0,1,2,3,4,5,6],weekStart=2,pay='Weekly',anchor='2026-01-07',auto=True,timezone='Australia/Sydney')
    d.update(changes);return d


def seed(factory):
    with factory.begin() as db:
        u=User(name='Test',email='one@example.com',phone='+61412345678',password_hash=generate_password_hash('test-password-long'))
        db.add(u);db.flush();w=save_workplace(db,u,data())
        work=db.get(Workplace,w['id']);work.cursor=date(2026,10,28)
        sched=db.scalar(select(Schedule));sched.effective_date=date(2026,10,28)
        return u.id,work.id


def body(d='2026-10-28',**kwargs):
    out=dict(date=d,start='07:30',end='17:00',breaks=30,revision=0,slot='scheduled');out.update(kwargs);return out


def test_scheduler_restart_idempotent(database):
    user,wid=seed(database)
    for _ in range(2):
        with database.begin() as db:reconcile(db,db.get(Workplace,wid),AT)
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Shift))==6
        assert db.scalar(select(func.sum(Shift.earnings)))==Decimal('1350.00')


def test_concurrent_workers(database):
    user,wid=seed(database)
    def run(_):
        with database.begin() as db:
            w=db.scalar(select(Workplace).where(Workplace.id==wid).with_for_update())
            reconcile(db,w,AT)
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(run,range(8)))
    with database() as db:assert db.scalar(select(func.count()).select_from(Shift))==6


def test_concurrent_workplace_limit(database):
    user,wid=seed(database)
    def create(i):
        try:
            with database.begin() as db:save_workplace(db,db.get(User,user),data(name=f'Place {i}'))
            return True
        except Invalid:return False
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(create,range(6)))
    assert sum(results)==2
    with database() as db:assert db.scalar(select(func.count()).select_from(Workplace))==3


def test_manual_off_not_recreated(database):
    user,wid=seed(database)
    with database.begin() as db:
        save_shift(db,db.get(User,user),wid,body(action='off'))
        reconcile(db,db.get(Workplace,wid),AT)
    with database() as db:
        s=db.scalar(select(Shift).where(Shift.local_date==date(2026,10,28)))
        assert s.status=='off' and s.earnings==0


def test_auto_correction_origin_and_audit(database):
    user,wid=seed(database)
    with database.begin() as db:reconcile(db,db.get(Workplace,wid),AT)
    with database.begin() as db:
        result=save_shift(db,db.get(User,user),wid,body(revision=1,end='16:00'))
        assert result['origin']=='auto' and result['status']=='manual' and result['earnings']=='200.00'
        assert db.scalar(select(func.count()).select_from(ShiftAudit).where(ShiftAudit.shift_id==result['id']))==2
    with database.begin() as db:
        with pytest.raises(Conflict):save_shift(db,db.get(User,user),wid,body(revision=1))


def test_multiple_shifts_and_overlap(database):
    user,wid=seed(database)
    with database.begin() as db:
        u=db.get(User,user)
        save_shift(db,u,wid,body(start='07:00',end='10:00',breaks=0))
        save_shift(db,u,wid,body(slot=str(uuid4()),start='11:00',end='13:00',breaks=0))
    with database() as db:
        r=dashboard(db,db.get(User,user),str(wid),'Week',0,AT)
        assert r['summary']['earnings']=='125.00'
    with database.begin() as db:
        with pytest.raises(Invalid):save_shift(db,db.get(User,user),wid,body(slot=str(uuid4()),start='09:00',end='12:00',breaks=0))


def test_isolation(database):
    user,wid=seed(database)
    with database.begin() as db:
        other=User(name='Other',email='other@example.com',phone='+61412345679',password_hash='hash');db.add(other);db.flush()
        with pytest.raises(NotFound):owned(db,other,wid)
        with pytest.raises(NotFound):save_shift(db,other,wid,body())
        with pytest.raises(NotFound):confirm_payment(db,other,wid,{'period_start':'2026-10-28','paid_date':'2026-11-01'})


def test_rate_snapshot(database):
    user,wid=seed(database)
    with database.begin() as db:
        u=db.get(User,user);save_shift(db,u,wid,body())
        save_workplace(db,u,data(rate='30.00',revision=1),str(wid))
    with database() as db:
        s=db.scalar(select(Shift).where(Shift.local_date==date(2026,10,28)))
        assert s.rate==Decimal('25.00') and s.earnings==Decimal('225.00')


def test_no_future_generation(database):
    user,wid=seed(database)
    with database.begin() as db:
        w=db.get(Workplace,wid);reconcile(db,w,datetime(2026,10,28,0,tzinfo=timezone.utc))
        assert db.scalar(select(func.count()).select_from(Shift))==0
        assert w.cursor==date(2026,10,28)


def test_downtime_recovery_bounded(database):
    user,wid=seed(database)
    with database.begin() as db:
        w=db.get(Workplace,wid);reconcile(db,w,AT,batch=2);assert w.cursor==date(2026,10,30)
        reconcile(db,w,AT,batch=2);assert w.cursor==date(2026,11,1)


def test_restore_off(database):
    user,wid=seed(database)
    with database.begin() as db:
        u=db.get(User,user);save_shift(db,u,wid,body(action='off'))
        result=save_shift(db,u,wid,body(action='restore',revision=1))
        assert result['status']=='manual' and result['earnings']=='225.00'


def test_archive_keeps_history(database):
    user,wid=seed(database)
    with database.begin() as db:
        u=db.get(User,user);save_shift(db,u,wid,body());save_workplace(db,u,data(revision=1,archived=True),wid)
    with database() as db:assert db.scalar(select(func.count()).select_from(Shift))>=1


def test_offline_idempotency_api(database):
    user,wid=seed(database)
    url=str(database.kw['bind'].url.render_as_string(hide_password=False))
    app=create_app({'TESTING':True,'SECRET_KEY':'x'*40,'SESSION_COOKIE_SECURE':False,'DATABASE_URL':url})
    c=app.test_client()
    with c.session_transaction() as s:s.update(user_id=str(user),version=1,csrf='csrf')
    headers={'X-CSRF-Token':'csrf','Idempotency-Key':str(uuid4())}
    path=f'/api/workplaces/{wid}/shifts'
    r=c.post(path,json=body(),headers=headers);assert r.status_code==200,r.json
    again=c.post(path,json=body(),headers=headers);assert again.json==r.json
    assert c.post(path,json=body(end='16:00'),headers=headers).status_code==409


def test_register_login_duplicate_and_profile(database):
    url=database.kw['bind'].url.render_as_string(hide_password=False)
    app=create_app({'TESTING':True,'SECRET_KEY':'x'*40,'SESSION_COOKIE_SECURE':False,'DATABASE_URL':url})
    c=app.test_client();c.get('/auth')
    with c.session_transaction() as s:csrf=s['csrf']
    payload=dict(mode='register',name='Tester',email='tester@example.com',phone='+61412345678',password='a-long-test-password',timezone='Australia/Sydney')
    r=c.post('/auth',json=payload,headers={'X-CSRF-Token':csrf});assert r.status_code==200,r.json
    assert c.get('/api/session').json['user']['email']=='tester@example.com'
    with c.session_transaction() as s:csrf=s['csrf']
    assert c.post('/api/logout',json={},headers={'X-CSRF-Token':csrf}).status_code==200
    c.get('/auth')
    with c.session_transaction() as s:csrf=s['csrf']
    assert c.post('/auth',json=payload,headers={'X-CSRF-Token':csrf}).status_code==409
    payload['mode']='login'
    assert c.post('/auth',json=payload,headers={'X-CSRF-Token':csrf}).status_code==200


def test_payment_confirmations_and_unpaid(database):
    user,wid=seed(database)
    with database.begin() as db:
        u=db.get(User,user)
        save_shift(db,u,wid,body('2026-10-21'))
        p=confirm_payment(db,u,wid,{'period_start':'2026-10-21','paid_date':'2026-10-28','actual_amount':'225.00'})
        assert p['id']
    with database() as db:
        r=dashboard(db,db.get(User,user),str(wid),'Month',0,AT)
        assert Decimal(r['payments'][0]['unpaid'])==0
        assert Decimal(r['payments'][0]['adjustment'])==0
    with database.begin() as db:
        with pytest.raises(Conflict):confirm_payment(db,db.get(User,user),wid,{'period_start':'2026-10-21','paid_date':'2026-10-28'})


def test_paid_shift_correction_reports_adjustment(database):
    user,wid=seed(database)
    with database.begin() as db:
        u=db.get(User,user)
        save_shift(db,u,wid,body('2026-10-21'))
        confirm_payment(db,u,wid,{'period_start':'2026-10-21','paid_date':'2026-10-28'})
        save_shift(db,u,wid,body('2026-10-21',revision=1,end='16:00'))
    with database() as db:
        r=dashboard(db,db.get(User,user),str(wid),'Month',0,AT)
        assert Decimal(r['payments'][0]['adjustment'])==Decimal('-25.00')


def test_future_manual_rejected(database):
    user,wid=seed(database)
    with database.begin() as db:
        with pytest.raises(Invalid):save_shift(db,db.get(User,user),wid,body('2099-10-21'))


def test_dst_gap_review_record(database):
    user,wid=seed(database)
    with database.begin() as db:
        w=db.get(Workplace,wid);w.cursor=date(2026,10,4)
        sched=db.scalar(select(Schedule));sched.effective_date=date(2026,10,4)
        sched.config={**sched.config,'start':'02:30','end':'04:00'}
        reconcile(db,w,datetime(2026,10,4,10,tzinfo=timezone.utc))
    with database() as db:
        s=db.scalar(select(Shift));assert s.status=='off' and s.earnings==0
        assert db.scalar(select(ShiftAudit)).action=='dst-review-required'


def test_reset_token_one_use(database):
    import hashlib
    from hourly.models import ResetToken,now
    user,wid=seed(database)
    with database.begin() as db:db.add(ResetToken(digest=hashlib.sha256(b'known-test-token').hexdigest(),user_id=user,expires=now()+timedelta(minutes=10)))
    url=database.kw['bind'].url.render_as_string(hide_password=False)
    app=create_app({'TESTING':True,'SECRET_KEY':'x'*40,'SESSION_COOKIE_SECURE':False,'DATABASE_URL':url})
    c=app.test_client();c.get('/reset')
    with c.session_transaction() as s:csrf=s['csrf']
    headers={'X-CSRF-Token':csrf}
    assert c.post('/reset',json={'token':'known-test-token','password':'new-long-password-123'},headers=headers).status_code==200
    c.get('/reset')
    with c.session_transaction() as s:headers={'X-CSRF-Token':s['csrf']}
    assert c.post('/reset',json={'token':'known-test-token','password':'another-long-password'},headers=headers).status_code==422


def test_scheduler_api_manual_race(database):
    user,wid=seed(database)
    def auto():
        with database.begin() as db:
            w=db.scalar(select(Workplace).where(Workplace.id==wid).with_for_update());reconcile(db,w,AT)
    def manual():
        try:
            with database.begin() as db:save_shift(db,db.get(User,user),wid,body(action='off'))
            return 'off'
        except Conflict:return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(auto);b=pool.submit(manual);a.result();out=b.result()
    with database() as db:
        shifts=db.scalars(select(Shift).where(Shift.local_date==date(2026,10,28))).all()
        assert len(shifts)==1
        assert shifts[0].status==('off' if out=='off' else 'auto')


def test_future_restore_resumes_planned_schedule(database):
    from hourly.models import now
    user,wid=seed(database)
    d=now().date()+timedelta(days=2)
    with database.begin() as db:
        u=db.get(User,user)
        save_shift(db,u,wid,body(d.isoformat(),action='off'))
        result=save_shift(db,u,wid,body(d.isoformat(),action='restore',revision=1))
        assert result['status']=='planned' and Decimal(result['earnings'])==0
        w=db.get(Workplace,wid);w.cursor=d
        reconcile(db,w,datetime.combine(d+timedelta(days=1),datetime.min.time(),tzinfo=timezone.utc))
    with database() as db:
        s=db.scalar(select(Shift).where(Shift.local_date==d))
        assert s.status=='auto' and s.earnings==Decimal('225.00')

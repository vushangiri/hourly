from datetime import date, datetime, timezone
from decimal import Decimal
import pytest
from hourly.domain import (Invalid, timestamps, calculate, period_range, config, decimal,
                           pay_range, payday_for, next_payday, integer, zone)


def cfg(**changes):
    values=dict(start='07:30',end='17:00',breaks=30,rate='25.00',workdays=[0,1,2,3,4,5],
                weekStart=2,pay='Weekly',anchor='2026-01-07',payday=4,monthDay=31,timezone='Australia/Sydney',auto=True)
    values.update(changes)
    return config(values)


def test_normal_shift():
    a,b=timestamps(date(2026,11,1),'07:30','17:00','Australia/Sydney')
    assert calculate(a,b,30,'25.00')==(32400,Decimal('225.00'))


def test_overnight():
    a,b=timestamps(date(2026,11,1),'22:00','06:00','Australia/Sydney')
    assert calculate(a,b,30,'25.00')==(27000,Decimal('187.50'))


def test_dst_spring_elapsed_time():
    a,b=timestamps(date(2026,10,4),'00:00','04:00','Australia/Sydney')
    assert calculate(a,b,0,'25.00')==(10800,Decimal('75.00'))


def test_dst_fall_elapsed_time():
    a,b=timestamps(date(2026,4,5),'00:00','04:00','Australia/Sydney')
    assert calculate(a,b,0,'25.00')==(18000,Decimal('125.00'))


def test_dst_nonexistent_rejected():
    with pytest.raises(Invalid):timestamps(date(2026,10,4),'02:30','04:00','Australia/Sydney')


def test_dst_fold_explicit():
    a,b=timestamps(date(2026,4,5),'02:15','03:15','Australia/Sydney',0,0)
    c,d=timestamps(date(2026,4,5),'02:15','03:15','Australia/Sydney',1,0)
    assert (b-a).total_seconds()==7200
    assert (d-c).total_seconds()==3600


def test_week_wednesday():
    assert period_range(date(2026,11,1),'Week',0,cfg())==(date(2026,10,28),date(2026,11,3))


def test_fortnight_anchor():
    c=cfg(anchor='2026-10-21')
    assert period_range(date(2026,11,1),'Fortnight',0,c)==(date(2026,10,21),date(2026,11,3))
    assert period_range(date(2026,10,20),'Fortnight',0,c)==(date(2026,10,7),date(2026,10,20))


@pytest.mark.parametrize('year,month,last',[(2024,2,29),(2026,2,28),(2026,11,30),(2026,12,31)])
def test_calendar_month(year,month,last):
    assert period_range(date(year,month,15),'Month',0)==(date(year,month,1),date(year,month,last))


def test_month_navigation_year_boundary():
    assert period_range(date(2026,1,1),'Month',-1)[0]==date(2025,12,1)


def test_common_calendar_week():
    assert period_range(date(2026,11,1),'Week',0)[0]==date(2026,10,26)


def test_monthly_payday_clamped():
    assert payday_for(date(2026,1,31),cfg(pay='Monthly'))==date(2026,2,28)


def test_weekly_payday_after_period_end():
    c=cfg();start,end=pay_range(date(2026,11,1),c)
    assert start==date(2026,10,28)
    assert payday_for(end,c)==date(2026,11,6)
    assert next_payday(date(2026,10,30),c)==date(2026,10,30)


def test_round_half_up():
    a=datetime(2026,1,1,tzinfo=timezone.utc);b=datetime(2026,1,1,0,1,tzinfo=timezone.utc)
    assert calculate(a,b,0,'0.30')[1]==Decimal('0.01')


@pytest.mark.parametrize('value',['NaN','Infinity','-1','1.001','oops',None,'1000001'])
def test_money_validation(value):
    with pytest.raises(Invalid):decimal(value)


@pytest.mark.parametrize('changes',[{'workdays':[]},{'workdays':[7]},{'auto':'yes'},{'breaks':600},{'rate':'-1'},{'pay':'Daily'},{'start':'24:00'},{'timezone':'Unknown/Invalid'}])
def test_invalid_config(changes):
    with pytest.raises(Invalid):cfg(**changes)


def test_independent_configs():
    a=cfg();b=cfg(rate='28',weekStart=0,workdays=[3,4,5,6]);b['workdays'].append(1)
    assert a['rate']=='25.00' and a['weekStart']==2 and a['workdays']==[0,1,2,3,4,5]


def test_invalid_break():
    a,b=timestamps(date(2026,1,1),'09:00','10:00','UTC')
    with pytest.raises(Invalid):calculate(a,b,60,'25')

"""Pure calendar, time, validation and Decimal rules; no Flask/database dependencies."""
import calendar
import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = timezone.utc


class Invalid(ValueError):
    pass


def decimal(value, maximum='1000000'):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result > Decimal(maximum):
            raise Invalid('Amount outside permitted range.')
        if result != result.quantize(Decimal('.01')):
            raise Invalid('Use at most two decimal places.')
        return result.quantize(Decimal('.01'))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise Invalid('Enter a valid non-negative amount with at most two decimals.') from exc


def integer(value, low, high):
    if isinstance(value, bool) or not re.fullmatch(r'-?\d+', str(value)):
        raise Invalid('Enter a whole number.')
    n = int(value)
    if not low <= n <= high:
        raise Invalid(f'Enter a number between {low} and {high}.')
    return n


def zone(value):
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, TypeError, ValueError):
        raise Invalid('Use an IANA timezone, for example Australia/Sydney.')
    return value


def day(value):
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise Invalid('Enter a valid date (YYYY-MM-DD).')


def clock(value):
    if not isinstance(value, str) or not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', value):
        raise Invalid('Enter time as HH:MM.')
    return time.fromisoformat(value)


def localize(naive, tz, fold=0):
    """Choose fold 0/1 explicitly; reject nonexistent spring-forward wall times."""
    aware = naive.replace(tzinfo=ZoneInfo(tz), fold=fold)
    if aware.astimezone(UTC).astimezone(ZoneInfo(tz)).replace(tzinfo=None) != naive:
        raise Invalid('This local time does not exist because of daylight saving. Choose another time.')
    return aware.astimezone(UTC)


def timestamps(d, start, end, tz, start_fold=0, end_fold=0):
    a, b = clock(start), clock(end)
    end_date = d + timedelta(days=int(b <= a))
    s = localize(datetime.combine(d, a), tz, start_fold)
    e = localize(datetime.combine(end_date, b), tz, end_fold)
    if e <= s or e - s > timedelta(hours=26):
        raise Invalid('Shift must last more than zero and at most 26 hours.')
    return s, e


def calculate(s, e, breaks, rate):
    breaks = integer(breaks, 0, 1500)
    seconds = int((e - s).total_seconds()) - breaks * 60
    if seconds <= 0:
        raise Invalid('Unpaid break must be shorter than the shift.')
    earnings = (Decimal(seconds) * Decimal(rate) / Decimal(3600)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    return seconds, earnings


def config(data, default_tz='Australia/Sydney'):
    days = data.get('workdays', [])
    if not isinstance(days, list) or not days:
        raise Invalid('Select at least one working day.')
    days = sorted(set(integer(x, 0, 6) for x in days))
    pay = data.get('pay', 'Weekly')
    if pay not in ('Weekly', 'Fortnightly', 'Monthly'):
        raise Invalid('Unknown payment frequency.')
    tz = zone(data.get('timezone', default_tz))
    start, end = data.get('start'), data.get('end')
    s, e = timestamps(date(2026, 1, 15), start, end, tz)
    rate = decimal(data.get('rate'), '10000')
    breaks = integer(data.get('breaks', 0), 0, 1500)
    calculate(s, e, breaks, rate)
    if not isinstance(data.get('auto', False), bool):
        raise Invalid('Automatic logging must be true or false.')
    return dict(start=start, end=end, rate=str(rate), breaks=breaks, workdays=days,
                weekStart=integer(data.get('weekStart', 0), 0, 6), pay=pay,
                auto=data.get('auto', False), timezone=tz,
                anchor=day(data.get('anchor', date.today().isoformat())).isoformat(),
                payday=integer(data.get('payday', 4), 0, 6),
                monthDay=integer(data.get('monthDay', 28), 1, 31))


def month_add(d, n):
    y, m = divmod(d.year * 12 + d.month - 1 + n, 12)
    return date(y, m + 1, 1)


def period_range(today, period, offset, c=None):
    offset = integer(offset, -1200, 1200)
    c = c or {'weekStart': 0, 'anchor': '2024-01-01'}
    if period == 'Month':
        start = month_add(today.replace(day=1), offset)
        return start, month_add(start, 1) - timedelta(days=1)
    if period == 'Week':
        start = today - timedelta(days=(today.weekday() - c['weekStart']) % 7)
        start += timedelta(days=offset * 7)
        return start, start + timedelta(days=6)
    if period == 'Fortnight':
        anchor = day(c['anchor'])
        start = anchor + timedelta(days=((today - anchor).days // 14 + offset) * 14)
        return start, start + timedelta(days=13)
    raise Invalid('Unknown reporting period.')


def pay_range(d, c):
    if c['pay'] == 'Monthly':
        return period_range(d, 'Month', 0, c)
    size = 7 if c['pay'] == 'Weekly' else 14
    anchor = day(c['anchor'])
    start = anchor + timedelta(days=((d - anchor).days // size) * size)
    return start, start + timedelta(days=size - 1)


def payday_for(end, c):
    # Always after period end; monthly payday is in following calendar month.
    if c['pay'] == 'Monthly':
        m = month_add(end, 1)
        return m.replace(day=min(c['monthDay'], calendar.monthrange(m.year, m.month)[1]))
    first = end + timedelta(days=1)
    return first + timedelta(days=(c['payday'] - first.weekday()) % 7)


def next_payday(today, c):
    start, end = pay_range(today, c)
    previous_end = start - timedelta(days=1)
    due = payday_for(previous_end, c)
    return due if due >= today else payday_for(end, c)

"""Opt-in real browser test against a disposable running Hourly deployment.
Set BROWSER_TEST_URL=http://localhost:8080. Creates one test account/workplace.
Run after python -m playwright install chromium. Does not use mocked API data.
"""
import os
import secrets
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import pytest

URL=os.environ.get('BROWSER_TEST_URL')
pytestmark=pytest.mark.skipif(not URL,reason='BROWSER_TEST_URL unset: real deployment and Chromium required')


def test_mobile_end_to_end():
    from playwright.sync_api import sync_playwright, expect
    with sync_playwright() as p:
        browser=p.chromium.launch()
        context=browser.new_context(viewport={'width':390,'height':844},reduced_motion='reduce')
        page=context.new_page()
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(URL+'/auth')
        page.get_by_role('button',name='Create account',exact=True).click()
        email=f'test-{secrets.token_hex(6)}@example.com'
        page.get_by_label('Full name').fill('Browser QA')
        page.get_by_label('Phone with country code').fill('+614'+str(secrets.randbelow(100000000)).zfill(8))
        page.get_by_label('Timezone',exact=True).fill('Australia/Sydney')
        page.get_by_label('Email',exact=True).fill(email)
        page.get_by_label('Password (12–128 characters)',exact=True).fill('browser-test-password-123')
        page.locator('#submit').click()
        page.get_by_role('button',name='＋ Add workplace',exact=True).click()
        page.get_by_label('Workplace name',exact=True).fill('QA Workplace')
        page.get_by_role('button',name='Save workplace',exact=True).click()
        expect(page.locator('#orgpick')).to_be_visible()
        page.get_by_role('button',name='＋ Log a shift',exact=True).click()
        yesterday=(datetime.now(ZoneInfo('Australia/Sydney')).date()-timedelta(days=1)).isoformat()
        page.get_by_label('Shift start date',exact=True).fill(yesterday)
        page.get_by_label('Start time',exact=True).fill('09:00')
        page.get_by_label('End time',exact=True).fill('10:00')
        page.get_by_label('Unpaid break (minutes)',exact=True).fill('0')
        page.get_by_role('button',name='✓ Save manual shift',exact=True).click()
        expect(page.locator('#overlay')).to_be_hidden()
        page.get_by_role('button',name='Toggle dark mode',exact=True).click()
        expect(page.locator('#shell')).to_have_class('shell dark')
        page.locator('[data-period="Month"]').click()
        expect(page.locator('#progress')).to_be_hidden()
        page.locator('[data-period="Fortnight"]').click()
        expect(page.locator('#progress')).to_be_hidden()
        page.locator('[data-tab="Workplaces"]').click()
        expect(page.get_by_role('heading',name='My workplaces',exact=True)).to_be_visible()
        page.get_by_role('button',name='View timesheet',exact=True).click()
        # Cache active report and app shell; then prove a queued offline edit replays.
        page.evaluate('navigator.serviceWorker.ready')
        page.reload()
        expect(page.locator('#orgpick')).to_be_visible()
        context.set_offline(True)
        page.reload()
        expect(page.locator('#orgpick')).to_be_visible()
        page.get_by_role('button',name='＋ Log a shift',exact=True).click()
        page.get_by_label('Shift start date',exact=True).fill(yesterday)
        page.get_by_label('Start time',exact=True).fill('11:00')
        page.get_by_label('End time',exact=True).fill('12:00')
        page.get_by_label('Unpaid break (minutes)',exact=True).fill('0')
        page.get_by_role('button',name='✓ Save manual shift',exact=True).click()
        expect(page.locator('#network')).to_contain_text('pending')
        context.set_offline(False)
        expect(page.locator('#network')).to_be_hidden(timeout=15000)
        page.locator('[data-tab="Settings"]').click()
        page.get_by_role('button',name='Review pending edits',exact=True).click()
        expect(page.get_by_text('No pending edits.',exact=True)).to_be_visible()
        page.get_by_role('button',name='Close dialog',exact=True).click()
        assert not errors, errors
        browser.close()

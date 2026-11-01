# Release acceptance checklist

Run on a disposable deployment first. Do not mark an item passed without executing it.

## Database / deployment

- [ ] Fresh `alembic upgrade head` on PostgreSQL 17 completes; app and scheduler start.
- [ ] `docker compose --profile test up --build --abort-on-container-exit --exit-code-from tests tests` passes all database tests (browser test may skip separately).
- [ ] Run two scheduler workers concurrently; no duplicate scheduled slots; restart midway through a recovery batch.
- [ ] Confirm a 62+ day backlog recovers through multiple passes without losing manual overrides.
- [ ] Database backup can be restored into an isolated database and historical totals match.
- [ ] HTTPS, secure cookies, health endpoint and log rotation work on the target VPS.

## Authentication / isolation

- [ ] Register, reject duplicate email and phone separately, login, reject wrong password, logout.
- [ ] Verify two accounts cannot access each other's workplace/shift/history/payment URLs.
- [ ] After repeated wrong login attempts, rate limiting returns 429 and later expires.
- [ ] With configured SMTP, receive a reset email, use its token, reject a second use, revoke old sessions.
- [ ] Missing SMTP credentials return an honest delivery-unavailable error.
- [ ] Changing email, phone or password requires the current password.

## Workplaces / time / payments

- [ ] Create three different workplaces; fourth creation fails, including concurrent attempts.
- [ ] Change weekday, rate, timezone, pay anchor, payday and auto setting independently.
- [ ] Archive/restore preserves history; tomorrow-effective settings do not rewrite past shifts.
- [ ] Auto entries appear only after end time without opening a browser.
- [ ] Correct an auto entry, mark off, restore, inspect the original auto audit snapshot.
- [ ] Add nonoverlapping extra shifts; reject overlapping shifts and too-long breaks.
- [ ] Test Sydney spring gap and autumn fold; explicitly select the repeated-time occurrence.
- [ ] Weekly/fortnight/month/combined ranges and totals match manually calculated examples.
- [ ] Confirm a completed pay period; actual amount is distinct from estimate; duplicate confirmation fails.
- [ ] Edit a paid shift and verify the post-confirmation adjustment appears separately.

## UI / offline / PWA

- [ ] Run `tests/test_browser.py` against a real disposable deployment.
- [ ] At 360/390/430 px widths, navigation stays visible; forms and bottom sheets fit and scroll.
- [ ] Keyboard focus remains inside open dialogs, Escape closes, and focus returns appropriately.
- [ ] Light/dark contrast, touch targets and reduced-motion preference work on target devices.
- [ ] Loading indicators terminate on success, validation errors, offline failure and server errors.
- [ ] Install on Android Chrome and iOS Safari over HTTPS; standalone icons and safe areas display correctly.
- [ ] Load a report online, close/reopen offline, verify cached dates and clear offline indicator.
- [ ] Queue an offline shift; confirmed totals remain unchanged; reconnect and replay exactly once.
- [ ] Change that shift on another device first; the offline client must show a conflict and allow review/discard.
- [ ] Open two tabs and queue independent operations; no queue item is lost.
- [ ] Expired session preserves pending edits for reauthentication to the same account.
- [ ] Sign-out clears cached private data; switching account cannot expose another account's cache.
- [ ] Publish a bumped service-worker version; update banner appears, pending edits block update, reload installs new assets.
- [ ] Measure actual LCP/INP/CLS, report query timings and mobile frame behavior; source-size measurements alone are insufficient.

# Test and delivery report

Build environment: Python 3.12.14, pinned dependencies in requirements files. Validation performed 1 November 2026. This is an implemented application package with explicit verification gaps; it is **not certified production-ready**.

## Executed successfully

| Check | Result |
|---|---|
| `python -m pytest -q -ra` | **40 passed, 22 skipped** |
| Python pure-domain tests | 34 passed: ordinary/overnight/DST shifts, folds/gaps, Decimal rounding, real months, fortnight anchors, paydays, independent configuration and validation |
| Public HTTP/security-boundary tests | 6 passed: auth-page headers/cookies, CSRF rejection, anonymous API rejection, account-free offline shell, manifest/icons/worker routes and SQLite refusal |
| `node --check` | app.js, auth.js and sw.js parsed successfully |
| `python -m compileall` | Python application and test source compiled |
| Ruff undefined/unused-name checks (`--select F`) | Passed after removing unused imports |
| Alembic offline SQL generation | `upgrade head --sql` generated initial PostgreSQL DDL; **not execution against a database** |
| Asset build | CSS minification script executed |
| Local performance measurement | 1,000 pure-domain call bundles; results in PERFORMANCE.json |

A cloud browser inspected the actual application CSS/JavaScript with a **separate simulated API fixture**, not a mock database. Checked the home summary, shift editor, day-off save feedback, workplace form/weekdays/save feedback, navigation, Settings, light/dark styling and a 390×844 iframe viewport. This found and repaired the non-secure-context UUID assumption and nonpersistent bottom navigation. The fixture is not included in the delivered runtime and its displayed totals are not database test evidence.

Later queue/security corrections passed syntax/static and supported Python tests. They were not revalidated end-to-end in a real browser/database deployment.

## Skipped / blocked

**21 PostgreSQL tests** require TEST_DATABASE_URL. They cover scheduler restart/idempotency, concurrent workers, concurrent workplace limits, manual day-off protection, correction provenance/audit, multiple shifts/overlap rejection, account isolation, rate snapshots, no future auto entries, bounded downtime recovery, restoration, archive preservation, HTTP idempotency, registration/login/duplicate identity, payments/unpaid balances, paid-period adjustments, future manual rejection, DST review, reset-token single use, scheduler/manual races, and future schedule restoration.

**1 Playwright test** requires a running real deployment and Chromium. It checks account registration, workplace creation, manual recording, theme/navigation, service-worker offline display, queued edits and reconnection. Browser UI fixture inspection does not replace this test.

Docker and PostgreSQL executables were unavailable. Installing PostgreSQL through the system package manager failed because package metadata was unavailable and environment permissions prevented package-manager setup. The managed browser preview runtime also lacked Python, so the Flask server could not run there. No SQLite or synthetic database was used to claim integration success.

Unverified: real migrations, PostgreSQL constraints/locks, Docker startup, Nginx/HTTPS deployment, SMTP email receipt, OS PWA installation, service-worker upgrade lifecycle, real offline conflict races, backup restoration, sustained load, actual mobile 60 FPS and web-vitals/accessibility audit. There is no evidence-based claim that all these pass.

Run the exact commands in README and complete ACCEPTANCE.md before entering records you cannot afford to lose.

## Performance scope

The calculation benchmark measures a local bundle of timezone timestamp conversion, Decimal earnings and calendar-month boundaries. Asset sizes include raw/gzip lengths. These measurements **do not establish** PostgreSQL query latency, LCP/INP/CLS, 60 FPS, cellular performance or production capacity. Reports query bounded date ranges; summary totals are calculated from those returned saved entries. Unpaid/paid adjustments use indexed SQL aggregates.

## Deliberate limitations / remaining work

- No real-device PWA/SMTP verification; operational credentials and target infrastructure must be configured.
- Offline sync runs when open/on reconnect, not while the app is closed. Server auto logging is independent.
- Offline edits show pending state without optimistic financial totals. Conflicts require review/discard and re-entry; no automatic field merge or force overwrite.
- No local PIN/encrypted offline vault, no bounded LRU report cache, and no periodic backup automation.
- Payment confirmations have no edit/reversal UI. Corrections to paid-period shifts are shown as an aggregate adjustment.
- Three workplaces includes archived profiles. Schedule changes take effect tomorrow; invalid DST automatic shifts require manual review.
- Vanilla JS is used instead of HTMX/Alpine; JS is gzip-served but not minified. No adjacent-period prefetch, OS push reminders or OS background sync is claimed.
- The audit viewer shows the latest 100 revisions per shift; older history remains stored but needs an administrative query.
- Dependency vulnerability scanning, penetration testing and formal accessibility certification were not performed.

No remaining infrastructure test has been reported as passing merely because its source exists.

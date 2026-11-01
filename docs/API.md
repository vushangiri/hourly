# HTTP contract

All endpoints are same-origin. Protected routes use the session cookie. JSON writes require `Content-Type: application/json` and `X-CSRF-Token`; authenticated resource mutations additionally require a fresh UUID `Idempotency-Key`, retained for retries. `GET /api/session` returns the current CSRF value. No earnings totals supplied by clients are trusted.

| Method | Path | Request / response |
|---|---|---|
| GET | /auth | Styled registration/login/reset-request page |
| POST | /auth | `mode: register`, name/email/phone/password/timezone; `mode: login`, email/password; or `mode: forgot`, email |
| GET, POST | /reset | Reset page; POST token/password, single use |
| GET | / | Authenticated application shell |
| GET | /api/session | Current profile and CSRF token |
| POST | /api/logout | Empty JSON; clear session |
| POST | /api/profile | name/email/phone/timezone; current_password required for contact/password changes; optional new_password |
| GET | /api/dashboard | workplace UUID or `all`; period `Week`, `Fortnight`, `Month`; integer offset. Returns selected dates, bounded shift rows, workplaces, summary and payment estimates |
| POST | /api/workplaces | name/rate/start/end/breaks/workdays/weekStart/pay/auto/timezone/anchor/payday/monthDay; optional description/contact |
| POST | /api/workplaces/{id} | Same workplace fields plus observed revision and optional archived boolean |
| POST | /api/workplaces/{id}/shifts | date, slot=`scheduled` or independent UUID, revision, action=`save`/`off`/`restore`, start/end/breaks; optional start_fold/end_fold=0/1 |
| GET | /api/shifts/{id}/history | Latest 100 immutable snapshots, newest first |
| POST | /api/workplaces/{id}/payments | period_start, paid_date, optional actual_amount. Period must be completed and not overlap an existing confirmation |
| GET | /health | DB connectivity and app version |
| GET | /offline | Account-free offline shell |
| GET | /sw.js | Versioned service worker script |

Weekdays are Monday=0 through Sunday=6. Times are HH:MM. Dates are YYYY-MM-DD. Money is sent/returned as decimal strings. Workdays is a nonempty integer array. New resources have revision 0 in requests; existing resources use their current revision. Successful writes return HTTP 200 with the saved record or `{ok:true}`. Stable idempotent replay returns the original body.

Errors return `{error: "description"}`: 400 CSRF, 401 session/login, 404 unavailable/not-owned resource, 409 uniqueness/revision/idempotency conflict, 422 validation, 429 throttle, 503 unavailable email delivery. Unexpected infrastructure errors must not be interpreted as a saved operation; retain the original idempotency key when retrying.

# Engineering and business rules

## Scope and architecture decisions

One Flask monolith and PostgreSQL are authoritative. The independent scheduler is a second process from the same image. No Redis, Celery, React or Node build runtime is required. Jinja serves the shell/auth pages; small vanilla fetch handlers replace HTMX/Alpine because this UI already needs a durable IndexedDB outbox and explicit conflict reconciliation. Avoiding two additional client state systems keeps one request path. This is an intentional departure from those *preferred*, not mandatory, libraries.

CSS is derived from the approved reference. System fonts avoid external font blocking and external requests. The source JS remains unminified for maintainability; Nginx gzip reduces transfer cost. `scripts/build_assets.py` performs deterministic CSS whitespace/comment reduction. Do not represent the shipped JS as minified.

## Data model

| Table | Responsibility / constraints |
|---|---|
| users | UUID identity; normalized unique email and E.164 phone; password hash; timezone; session revocation version |
| workplaces | Owner FK; archive flag; monotonic revision; persisted next date for scheduler recovery |
| schedule_revisions | Append-only configuration snapshots with effective local date; unique workplace/revision |
| shifts | UUID identity; unique workplace/local date/slot; UTC timestamps; timezone; saved rate, seconds and Decimal earnings; current status and original source |
| shift_revisions | Immutable after-change snapshots with actor, timestamp and action; includes original generated state |
| payment_confirmations | Non-overlapping confirmed periods enforced under workplace lock; immutable estimate snapshot; optional amount actually received |
| idempotency_keys | Account/key compound PK; request fingerprint and committed JSON response |
| login_buckets | Shared DB-backed per-email/IP attempt windows; expired buckets cleaned |
| reset_tokens | Hashed single-use expiring token; owner FK |

Full executable DDL is in `schema.sql`. FKs do not cascade away audit-critical data. Workdays, rates, timezone and pay-cycle settings are stored together in versioned JSONB schedule snapshots; there is no duplicate current-pay-configuration table to drift out of sync. JSON shape is validated in `domain.config` before persistence. Old schedule rows are never modified by application routes.

## Calendar and earnings rules

- All amounts are AUD gross estimates, not take-home pay, tax calculations or proof of payment.
- Rate and earnings use Decimal. Duration is elapsed UTC seconds minus unpaid breaks. Each shift rounds half-up to cents; totals sum saved cents.
- End wall time at or before start means the next day, including a 24-hour same-time shift. Maximum elapsed shift is 26 hours; breaks must be shorter than elapsed duration.
- Repeated autumn times default to first occurrence. The editor exposes independent start/end occurrence selectors. Invalid spring-gap wall times are rejected for manual entries.
- Automatic DST-invalid shifts become zero-earnings `off` review records, with `dst-review-required` audit action. They never acquire invented hours. The user can correct them.
- Overlapping recorded shifts at the same workplace are rejected. Automatic schedules conflicting with an extra manual shift create an `off` review record with `overlap-review-required`. Different workplaces may overlap; the app does not infer employment conflicts.
- Dates identify the shift's local *start* date. An overnight shift belongs entirely to that date for reporting. Combined reports use the same ISO start/end dates for all workplaces; they do not convert each workplace's date label into a different timezone.
- Weekly reports use the workplace's weekday. Fortnight reports use floor division around the actual 14-day anchor, including dates before it. Months use real calendar boundaries. All-workplace weeks start Monday; combined fortnights use the fixed Monday 2024-01-01 anchor.
- Weekly/fortnightly payment cycles use their configured anchor; payday is the next configured weekday strictly after period end. Monthly cycles are calendar months; payday is in the following month, capped to that month's final date. A payday equal to today is still “next”.
- Rate changes affect future schedule revisions. Every shift retains its saved rate on correction. A historical manual shift before workplace creation uses the earliest known schedule rate; this assumption is documented rather than guessing an unknown prior rate.
- Corrections to already paid periods do not invent additional payments. Reports show the net difference from the confirmed estimate as “Changes to already confirmed periods”. This is separate from earnings in unconfirmed periods. Payment confirmations are immutable in this MVP; no reversal interface exists.

## Workplaces and scheduling

Maximum **three total profiles including archived**. Archiving keeps history and avoids creating extra profiles to bypass the limit; archived workplaces can be restored in the edit form. Schedule edits are effective next local day, never earlier than any already recorded pending effective date. Name/contact/archive presentation is immediate. Current-day shifts, including overnight shifts, retain the old schedule. Unarchiving requires explicitly turning auto logging on again.

The application does not infer past attendance at signup. The first schedule begins on the creation date. Manual historical entry remains possible.

Every auto date has the stable `scheduled` slot. Additional shifts use independent UUID slots. “Mark this shift off” creates/updates an `off` tombstone and blocks future scheduled recreation; it does not delete extra shifts that same day. Restoring a completed schedule produces a manual entry and preserves the original source. Restoring a future schedule creates a zero-earnings planned entry; the scheduler may complete it when automatic logging is enabled and its end time passes.

Each scheduler pass enumerates workplaces and processes at most 62 local dates per workplace, inside its own transaction. A row lock with SKIP LOCKED permits multiple workers. The persisted cursor advances only with committed reconciliation. Future/end-not-reached dates stop processing. Repeated passes recover arbitrary downtime without one unlimited transaction. Unique shift keys provide a second duplicate guard. Manual mutation uses the same workplace lock, so automation cannot overwrite a manual record. The CLI logs failures and retries on the next 30-second pass.

## Transactions and conflicts

All authenticated JSON mutations need a CSRF token and UUID `Idempotency-Key`. Account-row locking serializes idempotency replay and workplace creation; workplace-row locking serializes schedule/shift/payment mutation. A repeated key with the same path and payload returns the original committed response. Reuse with a different payload returns 409. No side effect commits without its idempotency response.

Workplace and shift edits carry their observed `revision`. Creation uses 0; existing revisions start at 1. A mismatch is HTTP 409. Clients must review, not blindly force overwrite. No deletion route exists for history.

## Offline and privacy

Service worker cache contains only public static files and an account-free shell. Account profiles/reports and shift outbox items use IndexedDB namespaced by account UUID. No cookie, password, CSRF token or reset token is persisted there. localStorage contains only appearance and the last account UUID.

An edit is durably appended before its first POST. Queue append/removal uses an IndexedDB read/write transaction, avoiding lost updates between browser tabs. Replay reuses the same UUID key. Network/server failures retain pending operations. Validation/revision conflicts remain explicit for review. The pending record is visible, but financial totals stay at the last server-confirmed snapshot. Queue review lets the user discard the pending device change and re-enter after reviewing current data.

Synchronisation runs when the app opens, when connectivity returns while open, or via Sync now. It is **not OS background sync while the PWA is closed**. Automatic shift generation is independent of this and continues on the server.

Session expiry sends the user to sign-in while retaining queued edits. Signing into the same account retains them; signing into another account clears the prior device cache/outbox. Explicit sign-out is blocked until pending edits are synced/discarded, then clears the device store. On a shared unlocked browser, previously cached data remains readable offline until sign-out. There is no separate local PIN/encrypted offline vault.

Reports cache only requested periods; there is no silent download of all shift history. This MVP does not impose an LRU disk cap on the report cache. Browser storage eviction remains possible; use offline edits as a temporary queue, not your only backup.

## Security and deployment

Scrypt password hashes, signed HttpOnly SameSite=Lax cookies, secure cookies in HTTPS deployment, CSRF tokens, CSP, escaped dynamic strings, owner predicates, and database-backed login throttling are included. Contact/password changes require the current password. Reset increments session version to revoke old sessions. Email/phone are normalized but registration itself does not verify contact ownership; password reset verifies control via email possession.

Throttling is per normalized email + remote IP, with 10 attempts per 15 minutes; PostgreSQL makes limits shared across app instances. Behind the supplied proxy the remote IP can be shared, but different account addresses have independent buckets. This is not comprehensive edge-level abuse protection. Do not trust arbitrary X-Forwarded-For headers. If adding real-client-IP handling, scope trusted proxy configuration to your actual network.

Authentication/reset pages and API responses are `no-store`. The health endpoint verifies database connectivity. Secrets must be random and operator-configured. SMTP requires STARTTLS and accurate PUBLIC_URL. No credentials are included in the archive.

## Adding features

1. Write/extend pure calculations in `domain.py`, with behavior tests.
2. Add model fields and create an Alembic migration using `alembic revision --autogenerate -m 'description'` against your development DB. Review the generated DDL; never edit the applied initial migration.
3. Add transactional logic to services, preserving lock order: user then workplace, and keeping immutable history.
4. Expose an owner-scoped route. Use `@mutate` for authenticated writes, current revision for edits, and server-calculated financial fields.
5. Add form/UI behavior in app.js. Escape untrusted text with `esc`. Only shift edits currently participate in offline queuing.
6. Test domain behavior, another-account access, duplicate key replay, concurrent workers and stale revisions. Run the real PostgreSQL and browser suites.
7. Update API docs and bump service-worker cache version when changing assets. Test an installed old client upgrading to the new one with queued edits.

Do not add a second earnings formula in the browser or rewrite historical rates when updating a workplace.

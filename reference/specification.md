# HOURLY — COMPLETE MOBILE-FIRST PWA DEVELOPMENT MASTER PROMPT

## ROLE AND OBJECTIVE

Act as the Principal Full-Stack Engineer, UI/UX Engineer, Database Architect, Security Engineer, QA Engineer and DevOps Engineer responsible for designing, implementing, testing, auditing and delivering **Hourly**, a production-ready mobile-first Progressive Web Application for tracking work hours and estimating earnings.

Your responsibility is to build the entire functioning application, not merely produce documentation, wireframes, database models, mock APIs or a frontend prototype.

I have attached the approved standalone HTML/CSS/JavaScript UI reference.

**The attached reference is the visual source of truth.**

Preserve its visual identity, mobile-first layout, typography, colour palette, spacing, rounded cards, navigation, light/dark modes, and general interaction patterns.

You may improve technical implementation, accessibility, transitions, responsiveness and loading states without unnecessarily changing the approved design.

The reference is a prototype, not an authoritative implementation of business rules. Where its JavaScript contains simplified calculations, fixed dates or temporary state, replace those with correct production logic.

Do not redesign the application into a conventional desktop dashboard.

---

# 1. PRODUCT OVERVIEW

Hourly is a personal work-hours and earnings tracker designed primarily for mobile phones.

The application's fundamental purpose is to let users:

1. Register and securely access an account.
2. Create and manage up to three workplace profiles.
3. Configure independent working schedules for each workplace.
4. Automatically record scheduled shifts when enabled.
5. Manually create, edit or correct daily work-hour records.
6. Distinguish automatic entries from manually entered records.
7. View hours and estimated earnings by week, fortnight and month.
8. Configure a different workweek starting day for each workplace.
9. Track payment frequency and expected payday.
10. Install and use the application as a PWA.

The product should feel lightweight, exceptionally responsive, and intuitive enough that recording a shift requires only a few interactions.

Avoid unnecessary features, complex navigation, enterprise-style dashboards or excessive settings.

---

# 2. TECHNOLOGY AND ARCHITECTURE

Use a minimal, maintainable architecture.

Preferred technology stack:

- Python 3.12+
- Flask
- PostgreSQL
- SQLAlchemy 2
- Alembic / Flask-Migrate
- Jinja2 server-side templates
- HTMX for partial updates
- Alpine.js for lightweight client-side interaction
- Tailwind CSS or carefully organised compiled CSS
- Minimal vanilla JavaScript where necessary
- Service Worker and Web App Manifest for PWA support
- Docker Compose for local and production deployment
- Gunicorn and Nginx
- Pytest for automated testing

Do not introduce React, Next.js, Kubernetes, Redis, Celery, Kafka or other substantial infrastructure without demonstrating a concrete requirement that cannot reasonably be met with the preferred stack.

Use a modular Flask monolith.

Keep business logic separate from HTTP routes, templates and persistence code.

PostgreSQL is the authoritative production database. Do not silently substitute SQLite in the final application.

For automatic logging, use a lightweight, reliable scheduled execution mechanism backed by PostgreSQL, such as a dedicated scheduler process with database locking.

The scheduler must be safe across restarts and must not create duplicate entries if multiple application instances are running.

Use a transactional, idempotent database design.

---

# 3. AUTHENTICATION AND USER ACCOUNTS

Implement functional registration, login, logout and profile management.

Registration requires:

- Full name
- Phone number
- Email address
- Password

Requirements:

- Unique email and phone identifiers.
- Proper input validation and normalisation.
- Secure password hashing.
- Secure cookie-based sessions.
- CSRF protection.
- Login rate limiting.
- Account-level data isolation.
- Secure password reset using an appropriate verified delivery channel.
- Profile editing.

Do not fabricate successful email or SMS delivery without configured provider credentials.

Do not expose sensitive user data to other accounts.

All authentication pages must match the approved application's mobile-first visual design.

---

# 4. WORKPLACE PROFILES

Each account can create a maximum of three workplaces.

The limit must be enforced server-side, including under concurrent requests.

Each workplace contains:

**Required fields**

- Workplace name
- Hourly pay rate
- Default shift start time
- Default shift end time
- Scheduled working days
- Workweek starting weekday
- Payment frequency
- Automatic logging enabled/disabled

**Additional fields**

- Unpaid break duration
- Payday configuration
- Pay-cycle anchor date
- Optional workplace description
- Optional workplace contact details
- Timezone, defaulting to the user's configured timezone
- Active or archived status

The working days must be selectable using the compact seven-day selector shown in the approved reference.

Users must be able to select any combination of weekdays.

For MVP, one default shift schedule per workplace is sufficient, but individual daily shifts must remain editable.

Workplace configuration must be independent.

For example:

Workplace A:

- Monday–Saturday
- Wednesday workweek start
- 7:30 AM–5:00 PM
- $25 per hour
- Automatic logging enabled
- Weekly payment

Workplace B:

- Thursday–Sunday
- Monday workweek start
- 4:00 PM–10:00 PM
- $28 per hour
- Automatic logging disabled
- Fortnightly payment

Editing one workplace must never modify another workplace's records.

Support workplace archiving without destroying historical financial records.

---

# 5. AUTOMATIC WORK-HOUR LOGGING

This is a core requirement.

When automatic logging is enabled, the application should automatically create work-hour entries using the workplace's configured working days, start time, end time and unpaid break duration.

Automatic entries must be created only after the scheduled shift has actually ended.

Do not count future scheduled shifts as completed work.

Automatically generated entries must have a persistent source/status that distinguishes them from manual entries.

Recommended states:

- Planned
- Auto-set
- Manually logged
- Day off

The application must visually distinguish these states using the approved UI conventions.

Manual: green confirmation indicator.

Auto-set: subtle amber background and automatic-entry icon.

Planned: neutral indicator.

Day off: subdued appearance.

The backend must enforce:

1. Idempotent automatic generation.
2. No duplicate records for the same scheduled shift.
3. Safe recovery after downtime.
4. Correct handling of overnight shifts.
5. Correct handling of daylight-saving transitions and timezone changes.
6. Manual edits take precedence over automatic schedules.
7. Explicitly marked days off are never recreated automatically.
8. Schedule changes must not silently rewrite historical entries.
9. A user can correct an automatically generated entry at any time.
10. Each entry preserves its origin and modification history.

A manual correction to an auto-set entry should display as manually corrected while retaining the original automatic source in its audit metadata.

Automatic logging must operate on the server and must not depend on the user opening the PWA.

Provide tests for scheduler restarts, duplicate execution and concurrent workers.

---

# 6. DAILY TIMESHEET

The home screen must show daily records with:

- Weekday name
- Calendar date
- Shift start and end time
- Net hours worked
- Estimated gross earnings
- Entry source/status

Every daily entry must be interactive.

Tapping a day should open a mobile-friendly editing interface.

Users must be able to:

- Create a shift.
- Edit start time.
- Edit end time.
- Adjust unpaid breaks.
- Confirm an automatically generated shift.
- Mark a day as off.
- Restore the scheduled shift.
- Review historical entries.

Support multiple shifts on the same day without corrupting totals.

Use a proper underlying shift identifier rather than assuming there can only be one record per workplace per date.

Calculate durations using actual timestamps and timezone-aware logic.

Financial amounts must use Decimal, not binary floating-point arithmetic.

Preserve the applicable hourly rate on historical entries so later rate changes do not recalculate old earnings incorrectly.

Use audit records or equivalent history for meaningful changes.

---

# 7. WEEKLY, FORTNIGHTLY AND MONTHLY REPORTING

The dashboard must provide three primary views:

- Week
- Fortnight
- Month

Weekly and fortnightly views must respect the selected workplace's configured workweek start and pay-period anchor where applicable.

For example, a Wednesday-start workplace displays Wednesday through Tuesday for its weekly view.

A fortnightly pay period must align with its actual 14-day cycle, not an arbitrary pair of weeks.

Monthly reporting must use actual calendar-month boundaries.

Do not use a fixed 28-day month.

Allow navigation to previous and next periods.

Display:

- Total recorded hours
- Total estimated gross earnings
- Hourly rate where applicable
- Number of manual entries
- Number of automatic entries
- Individual daily records

The main earnings card must update accurately when:

- Switching workplaces
- Switching reporting periods
- Navigating dates
- Editing shifts
- Marking days off
- Changing applicable pay settings

Also provide a simple combined All Workplaces overview.

Combined reporting must use common calendar date ranges, while each workplace retains its own independent pay-cycle calculations.

---

# 8. PAYDAY AND PAY-CYCLE CONFIGURATION

Support weekly, fortnightly and monthly payment schedules.

Store an appropriate pay-cycle anchor and payday rule for each workplace.

Show the next expected payday and estimated unpaid earnings.

Paydays must be calculated using the workplace's own configuration.

Distinguish estimated earnings from confirmed payments.

Do not imply that a user has been paid simply because a scheduled payday has passed.

Implement a lightweight way to mark a pay period as paid, with a payment date and optional actual received amount.

Keep this simple and integrated into the existing mobile UI.

Do not turn the application into a full accounting or payroll platform.

---

# 9. UI/UX IMPLEMENTATION

Reproduce the approved HTML reference as faithfully as possible.

Visual priorities:

- Mobile-only design emphasis
- Premium, minimal aesthetic
- Warm off-white backgrounds
- Deep emerald primary accents
- High-contrast charcoal text
- Amber auto-set indicators
- Rounded cards
- Subtle borders
- Comfortable touch targets
- Clear typographic hierarchy
- Fixed or sticky mobile bottom navigation
- Light and dark mode
- Smooth modal and bottom-sheet interactions

The primary navigation remains:

Home | Workplaces | Settings

Do not add unnecessary navigation sections.

The user should be able to understand their hours and earnings immediately upon opening the app.

Maintain readable contrast in both themes.

Use responsive sizing, safe-area insets and proper mobile viewport handling.

---

# 10. PERFORMANCE AND PERCEIVED SPEED

Optimise for extremely fast interaction on ordinary Android and iOS phones, including slower devices and mobile networks.

Implement performance improvements where technically justified.

**Initial loading**

- Small HTML payloads.
- Compiled and minified production assets.
- Efficient font loading with system-font fallback.
- Minimal blocking JavaScript.
- Critical CSS where useful.
- Appropriate HTTP caching.
- Gzip or Brotli compression.

**Skeleton loading**

Create skeleton placeholders matching the geometry of:

- Earnings summary card
- Daily timesheet rows
- Workplace cards
- Reporting views

Only display skeletons when meaningful loading is occurring.

Do not introduce artificial loading delays.

**Loading indicators**

Provide:

- Lightweight inline button loaders.
- Submission-in-progress states.
- Save confirmation feedback.
- Nonblocking background-sync indicators.
- Appropriate error and retry states.

Prevent double submissions.

**Optimistic UI**

Use optimistic updates for safe operations such as marking a shift or editing an entry.

If the server rejects an operation, restore the previous state and show a clear error.

Do not display a financial change as permanently saved before the server confirms it.

**Lazy loading**

- Load historical records on demand.
- Avoid downloading unlimited timesheet history.
- Prefetch adjacent reporting periods when useful.
- Use paginated or bounded database queries.
- Avoid unnecessary full-page refreshes.
- Minimise DOM replacement and layout shifts.

**Animations**

Implement subtle, polished animations for:

- Period switching
- Navigation changes
- Card appearance
- Modal opening/closing
- Loading-state transitions
- Button feedback
- Saving and confirmation

Use CSS transforms and opacity where possible.

Target smooth 60 FPS interactions on typical mobile hardware.

Respect `prefers-reduced-motion`.

Do not use animation libraries unless clearly necessary.

**Backend performance**

- Proper database indexes.
- Efficient aggregate queries.
- Avoid N+1 queries.
- Use connection pooling.
- Query only the requested date ranges.
- Avoid loading complete account histories for dashboard calculations.
- Use targeted HTMX partial updates.

Performance must be measured rather than merely claimed.

---

# 11. PWA REQUIREMENTS

Implement a fully installable PWA.

Include:

- Valid web app manifest
- App icons
- Standalone display mode
- Appropriate theme colours
- Service worker
- Offline application shell
- Network status indication
- Versioned static asset caching
- Update notification when a new version is available

For offline use:

- Display previously cached timesheets.
- Permit safe offline shift edits where feasible.
- Queue pending edits locally.
- Synchronise them when connectivity returns.
- Handle conflicts explicitly.
- Prevent duplicate entries during replay.

Use a durable client-side storage mechanism such as IndexedDB for queued offline operations.

Do not use localStorage as the authoritative financial database.

Implement clear rules for offline edits, revision conflicts and server reconciliation.

Do not cache authentication secrets or sensitive account responses in a shared public cache.

Test PWA installation, service-worker updates and offline behaviour.

---

# 12. DATABASE AND DATA INTEGRITY

Design a properly normalised PostgreSQL schema.

Include models for:

- Users
- Workplaces
- Workplace schedules
- Schedule revisions/history
- Shift entries
- Shift revisions/audit records
- Pay-period configurations
- Payment confirmations
- Offline synchronisation/idempotency records where required

Use migrations for all schema changes.

Include appropriate constraints, unique keys, indexes and foreign keys.

Ensure:

- All records are scoped to the authenticated user.
- Historical shift earnings remain reproducible.
- Work-hour calculations are deterministic.
- Concurrent writes cannot create duplicate shifts.
- Manual edits cannot be overwritten by background automation.
- Deleting or archiving workplaces does not destroy financial history.

Document the database schema and relationships.

---

# 13. SECURITY REQUIREMENTS

Implement:

- CSRF protection
- Secure session management
- Password hashing
- Rate limiting
- Input validation
- Output escaping
- Authorisation checks
- Protection against IDOR
- Safe database transactions
- Parameterised queries
- Security headers
- Environment-based secret management
- Production HTTPS configuration
- Secure logging without exposed credentials

Do not trust client-submitted earnings totals.

Calculate authoritative totals on the server.

Test unauthorised access to another user's workplaces, timesheets and payment records.

---

# 14. TESTING AND QUALITY ASSURANCE

Do not stop after implementing the UI or database.

Build and run automated tests.

At minimum, cover:

**Authentication**

- Registration
- Login/logout
- Duplicate phone/email
- Password validation
- Account isolation

**Workplaces**

- Create/edit/archive
- Three-workplace limit
- Concurrent workplace creation
- Independent schedules
- Different workweek starting days

**Timesheets**

- Manual logging
- Auto-set logging
- Editing automatic entries
- Marking days off
- Restoring schedules
- Overnight shifts
- Unpaid breaks
- Multiple shifts in one day

**Reporting**

- Weekly totals
- Fortnightly boundaries
- Calendar-month boundaries
- Multiple workplaces
- Rate changes
- Decimal precision
- Historical earnings

**Automatic scheduler**

- Missed shifts
- Downtime recovery
- Duplicate job execution
- Concurrent execution
- Daylight-saving changes
- Manual override protection

**Frontend**

- Every button works.
- Every form validates.
- Every navigation action works.
- Light and dark modes work.
- Modals open and close correctly.
- Loading indicators terminate.
- Errors are displayed.
- No dead controls or placeholder actions remain.

**PWA**

- Installation
- Offline display
- Offline edit queue
- Reconnection synchronisation
- Conflict handling
- Cache updates

Use Playwright for browser-based interaction testing where available.

Test realistic mobile viewport sizes.

Include performance and accessibility checks.

Do not claim a test passed unless it was actually executed.

---

# 15. DEVELOPMENT AND EXECUTION PROCESS

Work in deliberate phases, but continue through implementation without stopping for approval after every phase.

Phase 1: Analyse the attached HTML reference and finalise the functional specification.

Phase 2: Design the database, backend modules, scheduling rules and API/HTMX contracts.

Phase 3: Implement authentication, database models, migrations and workplace management.

Phase 4: Implement shift logging, automatic scheduling, pay calculations and reporting.

Phase 5: Reproduce the approved mobile UI with functional backend integration.

Phase 6: Add loading states, transitions, optimisation and PWA support.

Phase 7: Implement and execute automated tests.

Phase 8: Audit functionality, security, database integrity, performance and UI fidelity.

Phase 9: Repair identified defects and rerun affected tests.

Phase 10: Package the complete project and provide deployment instructions.

Do not stop after planning or scaffolding.

Where a decision is not fully specified, choose a maintainable default, document it and proceed unless it materially affects security or financial correctness.

---

# 16. REQUIRED DELIVERABLES

Provide:

1. Complete application source code.
2. Database models and migrations.
3. Working frontend templates and compiled assets.
4. PWA manifest, icons and service worker.
5. Automatic scheduling mechanism.
6. Dockerfile and Docker Compose configuration.
7. PostgreSQL configuration.
8. Nginx production configuration.
9. Environment variable example file.
10. Seed/demo data script.
11. Automated test suite.
12. README with installation instructions.
13. Developer documentation explaining the project structure.
14. Database schema documentation.
15. Instructions for extending features.
16. Deployment instructions for Windows with Docker Desktop.
17. Deployment instructions for Ubuntu VPS.
18. Test execution report.
19. Known limitations and unverified functionality.

Provide a downloadable ZIP archive containing the complete project.

The README must contain exact commands to:

- Install dependencies.
- Configure environment variables.
- Start PostgreSQL.
- Run migrations.
- Start the application.
- Run the scheduler.
- Run tests.
- Build production assets.
- Deploy the application.
- Update the application safely.

---

# 17. INFRASTRUCTURE LIMITATIONS

If Docker, PostgreSQL, a browser automation environment or external services are unavailable in your execution environment:

- Still implement their complete integration.
- Execute all tests supported by the environment.
- Identify which tests are blocked.
- Provide exact commands to execute the blocked tests on my Windows computer or Ubuntu VPS.
- Do not claim blocked tests passed.
- Do not substitute a mock database as evidence that PostgreSQL concurrency tests succeeded.

Continue implementation rather than stopping because infrastructure is unavailable.

---

# 18. FINAL ACCEPTANCE CRITERIA

The project is ready for delivery only when:

- The approved visual design has been reproduced closely.
- All visible buttons and forms have working behaviour.
- User registration and authentication work.
- Three independent workplace profiles are supported.
- Organisation-specific working days and week starts work.
- Automatic logging functions independently of the browser.
- Manual entries and automatic entries are visually distinguishable.
- Shift editing and correction work.
- Weekly, fortnightly and monthly calculations are correct.
- Historical earnings remain accurate after rate changes.
- Paydays and pay periods work.
- The PWA is installable.
- Loading and animation behaviour is smooth.
- Relevant security controls are implemented.
- Automated tests have been run where infrastructure permits.
- The application can be deployed using the supplied instructions.

If any requirement is incomplete or unverified, identify it explicitly in the final report.

Do not claim production readiness without supporting verification.

**Begin by inspecting the attached approved HTML reference. Then implement the complete application, test it, repair defects and deliver the finished project.**
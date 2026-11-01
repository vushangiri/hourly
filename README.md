# Hourly

Mobile-first personal work-hours and gross-earnings tracker. Flask, PostgreSQL, SQLAlchemy, Alembic, Jinja, small vanilla JavaScript, IndexedDB and a service worker. The supplied approved reference is retained in `reference/approved.html`; its CSS forms the basis of the application.

**Delivery status:** implemented source with partial verification, not a production-certified release. Read `docs/TEST_REPORT.md` before using real records. PostgreSQL, Docker, SMTP delivery and real-device PWA installation were unavailable in the build environment. Database/concurrency tests are included but must run on your machine. No SQLite database or mocked database results are substituted.

## Windows — Docker Desktop

Install Docker Desktop with Linux containers and Docker Compose v2. Extract this folder, open PowerShell inside it, and run:

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

Edit `.env`. Put the generated value in `SECRET_KEY`; generate another hex value for `POSTGRES_PASSWORD`. Keep `COOKIE_SECURE=0` and `PUBLIC_URL=http://localhost:8081` for local use. Do not use the placeholder values.

```powershell
docker compose build
docker compose up -d db
docker compose run --rm migrate
docker compose up -d web scheduler nginx
docker compose logs --tail=50 web scheduler
```

Open **http://localhost:8081** and register an account. Host port `8081` lets this stack run alongside another app using `8080` (or `80`/`443`). Flask, Nginx and PostgreSQL keep their internal container ports because separate Compose projects have isolated networks. The database is persistent in the `pgdata` named volume. The application starts empty; creating an automatic workplace starts scheduling from its creation date, not from invented past shifts.

Run one scheduler pass manually:

```powershell
docker compose run --rm web flask --app wsgi scheduler --once
```

Run PostgreSQL integration and concurrency tests in a **separate disposable test database**:

```powershell
docker compose --profile test up --build --abort-on-container-exit --exit-code-from tests tests
```

This runs unit, security and PostgreSQL tests. The separate opt-in browser test skips until configured below. Test services never use the production `pgdata` volume.

Optional demo account (no artificial shift earnings):

```powershell
docker compose run --rm -e DEMO_PASSWORD="choose-a-long-demo-password" web flask --app wsgi seed-demo
```

Sign in as `demo@example.com`. Change the demo password through Settings before any shared use.

## Ubuntu VPS — HTTPS deployment

Install Docker Engine, Compose v2, Nginx and Certbot using the official instructions for your Ubuntu release. Upload the extracted project to `/opt/hourly` and restrict `.env` to the operator.

```bash
cd /opt/hourly
cp .env.example .env
python3 -c 'import secrets; print(secrets.token_hex(32))'
chmod 600 .env
```

Set independent secrets, `COOKIE_SECURE=1`, and `PUBLIC_URL=https://hourly.your-domain.com`. Configure SMTP if password recovery is required. The default Compose proxy publishes port **8081** on all host interfaces. For this host Nginx HTTPS setup, change the Compose port mapping to `127.0.0.1:8081:80`; do not expose PostgreSQL or Gunicorn publicly.

```bash
docker compose build
docker compose up -d db
docker compose run --rm migrate
docker compose up -d web scheduler nginx
```

Point your domain at the VPS. Obtain a certificate using your normal Nginx/Certbot flow. Adapt `deploy/host-https.conf` with your hostname and certificate paths, install it in `/etc/nginx/sites-available/hourly`, enable it and validate:

```bash
sudo ln -s /etc/nginx/sites-available/hourly /etc/nginx/sites-enabled/hourly
sudo nginx -t
sudo systemctl reload nginx
curl -fsS https://hourly.your-domain.com/health
```

The TLS configuration expects certificates to exist. For a new certificate, configure the port-80 vhost first, run `sudo certbot --nginx -d hourly.your-domain.com`, then reconcile the generated configuration with the supplied HTTPS example. Keep normal OS, image and dependency security updates in place.

## Local Python development

Python 3.12+ and a real PostgreSQL database are required. Docker can provide the database, or use a separately installed PostgreSQL server.

```bash
python -m venv .venv
# Linux/macOS:
. .venv/bin/activate
# PowerShell instead:
# .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

Set environment variables (the Flask app does not auto-load `.env` outside Docker):

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export DATABASE_URL='postgresql+psycopg://hourly:YOUR_PASSWORD@localhost:5432/hourly'
export COOKIE_SECURE=0
export PUBLIC_URL=http://localhost:8000
python -m alembic upgrade head
python scripts/build_assets.py
python -m flask --app wsgi run --port 8000
# In a second terminal, with the same environment:
python -m flask --app wsgi scheduler
```

PowerShell equivalents use `$env:SECRET_KEY = '...'`, `$env:DATABASE_URL = '...'`, etc. The development server is not for public deployment; Compose uses Gunicorn.

## Tests

```bash
python -m pytest -q
# Real database tests outside Compose; NEVER point this at an account database:
export TEST_DATABASE_URL='postgresql+psycopg://hourly:YOUR_PASSWORD@localhost:5432/hourly_test'
python -m pytest tests/test_postgres.py -q
```

PowerShell:

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://hourly:YOUR_PASSWORD@localhost:5432/hourly_test'
python -m pytest tests/test_postgres.py -q
```

The PostgreSQL fixture drops and recreates its schema and refuses databases without `test` in the name. Do not run it in parallel against one shared test database. CI validates the initial migration before running the integration suite.

Real browser/PWA test, against a running disposable deployment:

```bash
python -m playwright install chromium
export BROWSER_TEST_URL=http://localhost:8081
python -m pytest tests/test_browser.py -q
```

PowerShell:

```powershell
python -m playwright install chromium
$env:BROWSER_TEST_URL = 'http://localhost:8081'
python -m pytest tests/test_browser.py -q
```

This creates a QA account, saves shifts, checks navigation/theme, goes offline, queues a shift, reconnects and checks sync. It uses the real API. It does not test an iPhone/Android OS installation prompt. Test that manually on your target devices over HTTPS using `docs/ACCEPTANCE.md`.

## Password reset

Set `SMTP_HOST`, `SMTP_PORT` (default 587), `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`, and the correct HTTPS `PUBLIC_URL`. STARTTLS is required. Reset tokens expire after 30 minutes, can be used once, are stored only as SHA-256 digests, and invalidate old sessions. The token travels in the link fragment and is removed from the page URL before submission. No reset success is fabricated when SMTP is unconfigured.

## Safe updates and backups

Before upgrading, back up PostgreSQL and test restoration to a separate database. In PowerShell avoid piping binary dumps through text redirection:

```bash
docker compose exec db pg_dump -U hourly -d hourly -Fc -f /tmp/hourly-backup.dump
docker compose cp db:/tmp/hourly-backup.dump ./hourly-backup.dump
```

Store backups securely outside the project directory. Then:

```bash
docker compose stop web scheduler
docker compose build
docker compose run --rm migrate
docker compose up -d web scheduler nginx
docker compose logs --tail=100 web scheduler
```

Keep the prior image/source and backup until the upgrade is verified. Destructive Alembic downgrade is intentionally disabled. Never use `docker compose down -v` on a database containing real records. Run `docker compose down` to stop without deleting the volume.

For each asset release, update `VERSION` in `hourly/static/sw.js`. The app offers an update after the new worker installs; pending edits must be resolved first. Do not simply replace a cached asset and expect installed PWAs to pick it up immediately.

## Project map

- `hourly/models.py`: PostgreSQL tables and constraints.
- `hourly/domain.py`: deterministic dates, timezones, periods and Decimal calculations.
- `hourly/services.py`: transactional workplace, shift, scheduler and reporting use cases.
- `hourly/web.py`: authenticated HTTP endpoints and reset delivery.
- `hourly/__init__.py`: request/session security and SQLAlchemy lifecycle.
- `hourly/cli.py`: independent scheduler and explicit demo seed.
- `hourly/templates/`, `hourly/static/`: approved mobile appearance and interactive client.
- `migrations/`: immutable initial DDL snapshot and migration environment.
- `tests/`: pure, HTTP boundary, PostgreSQL/concurrency and real-browser tests.
- `deploy/`: reverse proxy and HTTPS examples.
- `docs/`: rules, API, schema, test evidence and release acceptance.

See `docs/ENGINEERING.md` to extend the app and understand the concurrency/offline contract.

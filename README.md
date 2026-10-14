# Spandan

AI-assisted doctor appointment booking and private chamber management for patients, doctors, assistants, and administrators.

[Open Spandan](https://spandan.cuetinsights.dev) · [Report an issue](https://github.com/sakawatkabir13/spandan/issues) · [Architecture](docs/ARCHITECTURE.md)

## Features

- **Patient accounts:** email OTP registration, password recovery, profile completion, medical history, and private medical reports.
- **Appointments:** doctor discovery, chamber and specialty filters, online and staff bookings, dependent bookings, rescheduling, cancellation, and waitlists.
- **Live queues:** serial allocation, check-in and consultation states, real-time updates, and polling fallback.
- **Doctor and chamber management:** professional profiles, multiple chambers, recurring schedules, closures, delegated assistant permissions, and analytics.
- **Medical records:** encrypted PDF/image uploads, patient-controlled sharing, and appointment-based doctor access. Assistants and administrators cannot access clinical records.
- **Billing:** hosted Stripe checkout, payment reconciliation, receipts, cash recording, and authorized refunds. Stripe uses sandbox credentials and test cards; transactions do not move real funds.
- **Account controls:** role-based access, authenticator MFA, audit events, session revocation, and personal-data export/deletion workflows.
- **AI assistance:** specialty recommendations using Groq `openai/gpt-oss-120b`, emergency screening, and a local fallback when the provider is unavailable.

AI recommendations provide general information and do not diagnose or prescribe.

## Technology

| Component | Stack |
| --- | --- |
| Frontend | React, TypeScript, Vite, Tailwind CSS, TanStack Query |
| Backend | FastAPI, Python, SQLAlchemy, Pydantic |
| Database | PostgreSQL 16, Alembic migrations |
| Delivery | Docker Compose, Nginx, GitHub Actions |
| Checks | Pytest, Ruff, Vitest, TypeScript, Playwright |

## Configuration files

There are two independent stacks. Do not combine their Compose files.

| File | Purpose |
| --- | --- |
| `docker-compose.yml` | Local development with source hot reload |
| `docker-compose.prod.yml` | Production images, private services, health checks, bounded logs, and persistent storage |
| `.env.example` | Tracked template for local `.env` |
| `.env.production.example` | Tracked template for private production `.env.production` |

Actual environment files contain deployment settings and secrets and are excluded from Git. Example files contain placeholders only. A separate VPS overlay is no longer required: production defaults preserve the existing `spandan_pgdata` and `spandan_backend_uploads` volumes and expose the frontend at `127.0.0.1:8082` for the host HTTPS proxy.

## Local development

Install Docker with Compose v2 or newer, then:

```bash
git clone https://github.com/sakawatkabir13/spandan.git
cd spandan
cp .env.example .env
docker compose up --build -d
```

- Frontend: <http://localhost:5173>
- API documentation: <http://localhost:8000/docs>
- Readiness: <http://localhost:8000/health/ready>

Startup applies database migrations. It does not automatically create accounts or publish shared login credentials. Register through the application; email verification requires SMTP configuration. The development database uses local-only credentials and a separate Compose project from production.

Configure `SMTP_PASSWORD` privately to use Gmail delivery. Use the 16-character Gmail app password without spaces. Configure `GROQ_API_KEY` to enable hosted AI assistance; without it, local recommendations remain available.

Local environment settings are passed to the backend. Only the frontend API URL is passed to Vite; server credentials must never use the `VITE_` prefix.

```bash
docker compose logs -f backend
docker compose exec backend alembic upgrade head
docker compose down
```

`down` preserves named volumes. Do not use `down -v` unless you intend to erase the stack's stored data.

## Production deployment

Create the private production configuration:

```bash
cp .env.production.example .env.production
chmod 600 .env.production
```

Set the database credentials and matching URL, independent JWT and medical-record encryption secrets, Groq key, public URLs, allowed hosts, and integration credentials. Placeholder values must be replaced before startup.

Production binds the frontend to `HTTP_LISTEN_HOST=127.0.0.1` and `HTTP_LISTEN_PORT=8082`. Configure the host Nginx HTTPS proxy to forward to that address. The backend and database have no published host ports. A different network topology can override the listen address and port explicitly.

For a first deployment:

```bash
docker compose -p spandan --env-file .env.production -f docker-compose.prod.yml config --quiet
docker compose -p spandan --env-file .env.production -f docker-compose.prod.yml up --build -d --wait
```

For subsequent releases:

```bash
sh ops/release.sh
```

The release script builds images tagged with the Git revision, creates an encrypted snapshot, applies migrations, verifies readiness, and restores the previous runtime if verification fails. It requires the existing stack to be running for the pre-release backup. `sh ops/rollback.sh` restores the preceding recorded runtime without downgrading the database.

Existing installations can use the production file alone. Retire any old `docker-compose.vps.yml` and remove it from custom commands or scheduled jobs after updating the repository. Preserve the production environment, existing database/upload volume names, backup key, and medical-record encryption key.

### Email and payments

Gmail uses `smtp.gmail.com`, port `587`, STARTTLS, and `community.cuetinsights@gmail.com` as the configured sender. Store the app password only in `SMTP_PASSWORD`.

For hosted checkout, configure `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` from the same Stripe sandbox. The webhook endpoint is:

```text
https://spandan.cuetinsights.dev/api/v1/payments/webhook
```

Subscribe to `checkout.session.completed`, `checkout.session.async_payment_succeeded`, and `refund.updated`. Checkout status is verified with Stripe; return URL parameters cannot mark a payment as paid. Live Stripe keys are rejected.

After changing backend environment values, recreate the backend using the current release tag:

```bash
RELEASE_TAG=$(cat .runtime/current-release) docker compose -p spandan --env-file .env.production -f docker-compose.prod.yml up -d --no-deps backend
```

### Logs and maintenance

```bash
docker compose -p spandan --env-file .env.production -f docker-compose.prod.yml logs --tail=100 -f backend
sh ops/run-backup.sh
sh ops/maintenance.sh
python3 ops/monitor.py
```

Run backups daily, maintenance every minute, and monitoring every five minutes using the server scheduler. The scripts use the stable production container names. Container logs rotate at 10 MB with three retained files per service.

Encrypted snapshots are stored in `.runtime/backups`. Keep `.runtime/backup.key` separately and test recovery into an isolated database before a live restore. Optional off-site delivery requires configured storage credentials.

## Patient medical records

Patients can review medical history and upload PDF, JPEG, PNG, or WebP reports, up to 5 MB per file, 25 files, and 100 MB per patient. Sharing starts disabled. Eligible booked doctors can access shared records; cancelled/absent appointments and sessions older than 30 days are excluded. Account-holder records are never shared through a dependent's appointment.

Files are encrypted under `UPLOAD_DIR/.medical`, excluded from public file serving, and checked for authorization on every download. Preserve `MFA_ENCRYPTION_KEY`, or the fallback `JWT_SECRET_KEY` used when records were created: replacing the encryption secret without migrating existing files makes those files unreadable. Encrypted upload snapshots include these reports.

## Development checks

Backend, from `backend/`:

```bash
uv sync --frozen --extra dev
uv run ruff check .
uv run pytest -q
```

Frontend, from `frontend/`:

```bash
npm ci
npm run lint
npm test
npm run build
```

PostgreSQL migration/concurrency checks and browser workflows run in CI using isolated test databases. Fixed credentials in automated tests are test fixtures, not published application accounts. See [backend setup](backend/README.md) for PostgreSQL verification.

## Repository layout

```text
backend/                    API, models, migrations, scripts, and tests
frontend/                   Application, browser tests, and Nginx configuration
ops/                        Release, rollback, backup, and monitoring tools
docs/ARCHITECTURE.md        Architecture reference
.github/workflows/ci.yml    Automated checks
docker-compose.yml         Local development stack
docker-compose.prod.yml    Production stack
.env.example               Local configuration template
.env.production.example    Production configuration template
```

Report suspected vulnerabilities privately to community.cuetinsights@gmail.com. Never include passwords, API keys, patient information, or private environment files in issues or commits.

## Contributors and license

- [Mohammad Sakawat Kabir](https://github.com/sakawatkabir13) — project lead and full stack.
- [Abdur Rashid Raj](https://github.com/Asimpleman420) — frontend and patient flows.
- [Olid Hussan Opu](https://github.com/olid-opu) — authentication, dashboards, and administrator flows.

Licensed under the [MIT License](LICENSE).

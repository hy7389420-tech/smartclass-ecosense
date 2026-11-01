# SmartClass EcoSense Backend

FastAPI backend for SmartClass EcoSense, including catalog CRUD and CV event
ingestion.

## Setup (Windows PowerShell)

From the repository root:

```powershell
py -3.12 -m venv backend\.venv-backend
backend\.venv-backend\Scripts\python.exe -m pip install --upgrade pip
backend\.venv-backend\Scripts\python.exe -m pip install -r backend\requirements.txt
if (-not (Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }
```

## Run the API

```powershell
Set-Location backend
.\.venv-backend\Scripts\python.exe -m uvicorn app.main:app --reload
```

- Liveness: <http://127.0.0.1:8000/health>
- Database readiness: <http://127.0.0.1:8000/ready>
- Interactive API docs: <http://127.0.0.1:8000/docs>

`/health` checks that the app process responds. `/ready` runs a small database
query and returns HTTP 503 with a safe error message if the database is
unavailable.

To regenerate the checked-in OpenAPI schema from the backend directory:

```powershell
.\.venv-backend\Scripts\python.exe -c "import json; from pathlib import Path; from app.main import app; Path(r'..\docs\api\openapi.json').write_text(json.dumps(app.openapi(), indent=2) + '\n', encoding='utf-8')"
```

## Test and lint

From the repository root:

```powershell
Set-Location backend
.\.venv-backend\Scripts\python.exe -m pytest
.\.venv-backend\Scripts\python.exe -m ruff check .
.\.venv-backend\Scripts\python.exe -m ruff format --check .
```

Configuration is read from environment variables and `backend/.env`. Never put
real credentials or secrets in `.env.example`. The complete backend variable
inventory is kept in [`backend/.env.example`](./.env.example); the root
[`.env.example`](../.env.example) also has optional Docker Compose database
settings.

## Docker and optional PostgreSQL

Docker Compose runs the API as a non-root user and persists its default SQLite
database in a named volume. The PostgreSQL service is opt-in and has a separate
persistent volume. The root CV camera key is not passed to the API container.

From the repository root, prepare the two local configuration files:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }
```

For the default SQLite setup:

```powershell
docker compose up --build -d backend
docker compose ps
docker compose logs backend
```

The API is bound to `127.0.0.1:8000`; `/ready` is the container health check.
Migrations run before Uvicorn starts. The `backend_data` volume survives
`docker compose down`; `docker compose down --volumes` permanently deletes
both database volumes.

To opt into PostgreSQL, set a unique `POSTGRES_PASSWORD` and the matching
`DATABASE_URL` in the root `.env` (URL-encode any special password characters):

```text
POSTGRES_PASSWORD=<local-secret>
DATABASE_URL=postgresql+psycopg://ecosense:<local-secret>@postgres:5432/ecosense
```

Start PostgreSQL and wait until it is healthy before starting the API:

```powershell
docker compose --profile postgres up -d postgres
docker compose ps
docker compose up --build -d backend
```

The PostgreSQL port is not published to the host. The Compose profile and
driver are provided for PostgreSQL configuration, but a PostgreSQL server,
Docker image build, and PostgreSQL migration run were not available to verify
in this environment. SQLite remains the locally tested database; don't treat
PostgreSQL compatibility as runtime-certified until that check is run.
SQLite-specific setup currently includes `check_same_thread=False` and
`PRAGMA foreign_keys=ON` in the SQLite engine path, plus Alembic batch rendering
for SQLite migrations. A source scan found no other obvious SQLite-only SQL,
but that is not proof of PostgreSQL runtime compatibility.

Compose reads backend application settings from `backend/.env`; its
`DATABASE_URL` is overridden by the root `.env` value or the Compose SQLite
default above. The root `.env` is used only for Compose interpolation and is
not mounted into the API container.

## Environment variables

Use `backend/.env.example` as the complete variable-name and default-value
reference. Important runtime settings are:

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `development` | Application mode; production applies stricter checks |
| `LOG_LEVEL` | `INFO` | Application logging threshold |
| `DATABASE_URL` | `sqlite:///./ecosense.db` locally | SQLAlchemy URL; Compose uses a named-volume SQLite path unless overridden |
| `JWT_SECRET_KEY` | Blank in template | Required strong secret in production; development generates a process-local value |
| `CORS_ALLOWED_ORIGINS` | Local Vite origins | Exact browser origins, comma-separated |
| `LOCAL_TIMEZONE` | `Asia/Kolkata` | Local date boundaries and naive timestamp interpretation |
| `REQUIRE_CAMERA_KEY` | `true` | Require registered camera credentials for event ingestion |
| `MAX_REQUEST_BODY_BYTES` | `1048576` | Request size ceiling |
| `REQUEST_RATE_LIMIT_REQUESTS` / `REQUEST_RATE_LIMIT_WINDOW_SECONDS` | `120` / `60` | In-process global request limit |
| `RETENTION_DAYS` | `90` | Default data-retention horizon |
| `AI_ASSISTANT_ENABLED` | `false` | Feature flag for the aggregate HOD assistant |

Other environment variables and their defaults cover login/event limits,
camera health, simulator retries, analytics thresholds, alert thresholds, and
activity-estimate weights and cutoffs. Set them in `backend/.env`; they are
validated by application settings at startup.

## Database

After installing dependencies, from the repository root:

```powershell
Set-Location backend
.\.venv-backend\Scripts\python.exe -m alembic upgrade head
.\.venv-backend\Scripts\python.exe -m scripts.seed_demo
```

Schema changes must be created as Alembic revisions and applied with
`alembic upgrade head`. The demo seed creates sample records only; it does not
create user accounts or passwords. See [DATABASE.md](../docs/DATABASE.md) for
the initial tables and relationships.

## Authentication and roles

Apply migrations before creating users. Create the first administrator with:

```powershell
Set-Location backend
.\.venv-backend\Scripts\python.exe -m scripts.create_admin --email admin@example.edu
```

The script prompts for a password unless `ADMIN_PASSWORD` is provided through
the environment. Passwords must be 12 to 128 characters; no default password
is used. Sign in at `POST /auth/login` to receive a 15-minute bearer token.
Send it as `Authorization: Bearer <access_token>` to protected APIs. `/health`,
`/ready`, `/auth/login`, and camera-key-authenticated event ingestion remain
available without a user token.

Set `JWT_SECRET_KEY` to a randomly generated value of at least 32 characters
for production. When blank in development, a process-local random secret is
generated; tokens become invalid after restarting the server. Login rate
limiting is process-local and is intended for this MVP, not a multi-worker
deployment.
Set JWT_SECRET_KEY in backend/.env (use a long random value, never commit it). Without it, a new secret is generated on every start and everyone is logged out after a restart.

Student accounts require an explicit `users.student_id` mapping. Existing
accounts are intentionally left unmapped by the migration, and an unmapped
Student receives `403` for student-data endpoints. HOD scope is mapped through
the department on that user's `faculty` profile. Faculty access follows
`faculty_class_assignments`; access is checked in the backend for each
requested object.

Authentication settings:

| Variable | Default | Purpose |
|---|---:|---|
| `JWT_SECRET_KEY` | Generated for local development | JWT signing secret; production requires 32+ characters |
| `JWT_ACCESS_TOKEN_MINUTES` | `15` | Short-lived access-token lifetime |
| `AUTH_LOGIN_MAX_ATTEMPTS` | `5` | Login attempts per client IP in the time window |
| `AUTH_LOGIN_WINDOW_SECONDS` | `60` | In-memory rate-limit window |

## Security hardening

`CORS_ALLOWED_ORIGINS` is a comma-separated list of exact HTTP(S) origins.
The defaults support the local React development server; production should set
only its actual frontend origins. Wildcards, paths and embedded credentials
are rejected. CORS credentials are enabled only for those exact origins.

Request bodies default to a 1 MiB maximum (`MAX_REQUEST_BODY_BYTES`). The
process-local limiter allows 120 requests per minute globally, with separate
30-per-minute buckets for `/auth/*` and `/events*` by client IP. Login keeps
its stricter existing 5-attempt window. These in-memory limits are not shared
between workers or servers.

API responses include `nosniff`, frame denial, a strict referrer policy and
`no-store` caching headers. Validation, HTTP and unexpected errors use a
common safe error envelope. Unexpected failures are logged by exception type
only, without echoing exception text to callers.

Production requires a non-default `JWT_SECRET_KEY` with at least 32
characters. Configure it through a secret manager or environment; never commit
it to source control. Security boundaries and remaining limitations are
documented in [SECURITY.md](../docs/backend/SECURITY.md).

## Optional HOD assistant

`POST /ai/ask` is available only to ADMIN and HOD accounts. It is disabled by
default; set `AI_ASSISTANT_ENABLED=true` to enable it. The current version uses
deterministic, rule-based intent detection and existing aggregate analytics. It
does not call an LLM, run model-generated SQL, or return individual student
records. Questions outside the supported set and requests for individual
student data are politely refused.

Supported questions cover highest average outside time by class, this week's
room utilization, underutilized rooms, unusual activity yesterday, average
occupancy of a named room, and this-month versus last-month aggregate trends.
See [API_CONTRACT.md](../docs/API_CONTRACT.md) for request and response
examples.

## Reports and retention

Authenticated staff can download a lecture report in JSON or CSV; students
can export only their own record. Daily/weekly summaries are scoped to the
user's role and use `LOCAL_TIMEZONE` for date boundaries. Engagement fields
are explicitly marked as estimates and reports include a limitations note.
PDF export is not included because no PDF library is currently installed or
needed for the JSON/CSV MVP.

`RETENTION_DAYS` defaults to 90. The admin API
`POST /admin/retention/run` defaults to a dry-run; send `{"dry_run": false}`
only after reviewing candidate counts to delete eligible events, activity
windows, and insights. The script is also safe by default:

```powershell
Set-Location backend
.\.venv-backend\Scripts\python.exe -m scripts.retention
.\.venv-backend\Scripts\python.exe -m scripts.retention --execute
```

Each run writes an audit entry. This job does not delete attendance records or
audit logs; the retention policy explains the resulting history limitation.

### Scheduling retention

Automatic scheduling is NOT enabled by default. Run the dry-run first and review
the candidate counts before enabling deletion. Deletion is irreversible.

From the repository root, the dry-run command is:

```powershell
Set-Location backend
.\.venv-backend\Scripts\python.exe -m scripts.retention
```

The real deletion command is:

```powershell
Set-Location backend
.\.venv-backend\Scripts\python.exe -m scripts.retention --execute
```

Example Windows Task Scheduler command to run the real deletion daily at
02:00, with the scheduled working directory set to the repository's
`backend` folder:

```text
<repo>\backend\.venv-backend\Scripts\python.exe -m scripts.retention --execute
```

Configure the daily task with `schtasks.exe /Create /SC DAILY /ST 02:00`
and set its working directory to `<repo>\backend`.

The following cron entry is Linux-only; its virtual environment path differs
from Windows and is `./.venv-backend/bin/python`. Adjust the repository path
and Python executable for the server:

```cron
0 2 * * * cd /path/to/SmartClass_EcoSystem_Project/backend && ./.venv-backend/bin/python -m scripts.retention --execute >> /var/log/ecosense-retention.log 2>&1
```

## Manual review and camera health

Staff with access to a lecture can review flagged events at `GET /review/events`.
Corrections require a reason, are appended as linked `MANUAL_CORRECTION` events,
and recompute attendance without overwriting the source event. The
`GET /audit-logs` endpoint is ADMIN-only.

Camera clients send `POST /cameras/{id}/heartbeat` with `X-Camera-Key`.
`GET /alerts` refreshes camera health and creates deduplicated camera-offline,
low-confidence-spike and unusual-exit alerts. A later heartbeat resolves the
open offline alert. No heartbeat or offline state creates a fabricated presence
event.

| Variable | Default | Purpose |
|---|---:|---|
| `CAMERA_OFFLINE_SECONDS` | `120` | Time since a heartbeat before camera-offline state |
| `LOW_CONFIDENCE_ALERT_WINDOW_MINUTES` / `LOW_CONFIDENCE_ALERT_MIN_EVENTS` | `5` / `3` | Low-confidence event spike window and threshold |
| `UNUSUAL_EXIT_ALERT_WINDOW_MINUTES` / `UNUSUAL_EXIT_ALERT_MIN_EVENTS` | `5` / `3` | Exit activity window and threshold |

CRUD request and response shapes are documented in
[API_CONTRACT.md](../docs/API_CONTRACT.md).

## Camera event ingestion

Apply the database migration and create or locate a classroom before
registering a camera. From the `backend` directory, generate a camera key:

```powershell
.\.venv-backend\Scripts\python.exe -m scripts.create_camera --classroom-id 1 --name "Door Camera"
```

The script prints the API key once. Save it securely; the database stores only
its SHA-256 hash. Send it in the `X-Camera-Key` header when calling
`POST /events` or `POST /events/batch`. Camera keys are required by default;
`REQUIRE_CAMERA_KEY=false` is intended only for isolated local development.

The CV module's `ENTRY`/`EXIT` JSONL can be imported without editing or running
the CV pipeline. From the `backend` directory, run:

```powershell
.\.venv-backend\Scripts\python.exe -m scripts.import_events_jsonl ..\cv\data\events.jsonl
```

When `REQUIRE_CAMERA_KEY=true`, the importer prompts for the camera key. It
uses the same validation and event service as the API, and commits the file as
one transaction. A malformed or invalid line reports its line number and
rolls back the import.

For an API-level camera-free simulation, start a lecture and send a realistic
stream through `POST /events/batch`. At least four student codes from the
selected class are required:

```powershell
.\.venv-backend\Scripts\python.exe -m scripts.simulate `
  --classroom-id 1 `
  --lecture-id 12 `
  --lecture-start "2026-10-25T10:00:00+05:30" `
  --duration-minutes 60 `
  --student-codes "STUDENT_A,STUDENT_B,STUDENT_C,STUDENT_D,STUDENT_E"
```

The first four codes simulate normal presence, one exit, multiple exits with a
derived return, and absence; extra codes receive normal-entry events. An
additional `UNKNOWN` event is flagged for review. The simulator writes to
`data/simulated_events.jsonl` before sending, prompts securely for a camera key
unless `ECOSENSE_CAMERA_KEY` is set, and retries transient failures using
`SIMULATOR_*` settings. See [CV_INTEGRATION.md](../docs/CV_INTEGRATION.md) for
the full payload, response and offline-queue contract. The CV sender now
appends locally before posting and keeps pending events available across backend
outages. Physical camera-to-backend validation remains pending.

Event-ingestion settings in `backend/.env`:

| Variable | Default | Purpose |
|---|---:|---|
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Exact allowed browser origins; comma-separated |
| `MAX_REQUEST_BODY_BYTES` | `1048576` | Maximum request body size (1 MiB) |
| `REQUEST_RATE_LIMIT_REQUESTS` / `REQUEST_RATE_LIMIT_WINDOW_SECONDS` | `120` / `60` | Global per-IP in-memory request limit |
| `SIMULATOR_REQUEST_TIMEOUT_SECONDS` | `10` | API simulator request timeout |
| `SIMULATOR_RETRY_ATTEMPTS` | `3` | Bounded API simulator retries after the first attempt |
| `SIMULATOR_RETRY_BACKOFF_SECONDS` | `1` | Base exponential delay for transient API failures |
| `AUTH_RATE_LIMIT_REQUESTS` | `30` | Additional `/auth/*` per-IP limit per configured request window |
| `EVENT_RATE_LIMIT_REQUESTS` | `30` | Additional `/events*` per-IP limit per configured request window |
| `REQUIRE_CAMERA_KEY` | `true` | Require a registered camera key |
| `EVENT_TIME_GRACE_SECONDS` | `300` | Allowed distance outside lecture time |
| `MIN_EVENT_CONFIDENCE` | `0.5` | Lower confidence is saved for review |
| `MAX_EVENT_BATCH_SIZE` | `100` | Maximum events in one batch (up to `1000`) |
| `CAMERA_OFFLINE_SECONDS` | `120` | Maximum time since camera activity before dashboards show "Camera Offline" |
| `RETENTION_DAYS` | `90` | Age threshold for event, activity-window, and insight cleanup |
| `UNDERUTILIZED_CUTOFF_PERCENT` | `40` | Utilization below this value is classified as underutilized |
| `OVERUTILIZED_CUTOFF_PERCENT` | `90` | Utilization above this value is classified as overutilized |
| `INSIGHT_WINDOW_MINUTES` | `5` | Exit-anomaly bucket size |
| `INSIGHT_MIN_EXITS` | `3` | Minimum exits required to flag an anomaly bucket |
| `INSIGHT_MIN_BUCKETS` | `3` | Minimum lecture buckets required for anomaly analysis |
| `INSIGHT_MIN_HISTORY` | `3` | Completed same-class lectures required for a trend |
| `INSIGHT_HISTORY_LECTURES` | `5` | Maximum prior lectures considered for trend comparison |
| `ACTIVITY_MAX_BATCH_SIZE` | `100` | Maximum windows accepted per `POST /activity` request |
| `ACTIVITY_MIN_WINDOW_SECONDS` / `ACTIVITY_MAX_WINDOW_SECONDS` | `1` / `300` | Accepted activity window duration |
| `ACTIVITY_MOVEMENT_MIN` / `ACTIVITY_MOVEMENT_MAX`, `ACTIVITY_FRONT_MIN` / `ACTIVITY_FRONT_MAX`, `ACTIVITY_VOICE_MIN` / `ACTIVITY_VOICE_MAX` | `0` / `1` | Normalization ranges for ratio signals |
| `ACTIVITY_AUDIO_MIN_DBFS` / `ACTIVITY_AUDIO_MAX_DBFS` | `-120` / `0` | Audio level normalization range |
| `ACTIVITY_MOVEMENT_WEIGHT` / `ACTIVITY_INACTIVITY_WEIGHT` / `ACTIVITY_HEAD_WEIGHT` / `ACTIVITY_VOICE_WEIGHT` / `ACTIVITY_AUDIO_WEIGHT` | `0.30`, `0.20`, `0.20`, `0.20`, `0.10` | Movement, inactivity, head-front, voice, audio signal weights |
| `ACTIVITY_MIN_SIGNALS` | `2` | Signals required to calculate an estimate |
| `ACTIVITY_LOW_CUTOFF` / `ACTIVITY_HIGH_CUTOFF` | `0.35` / `0.65` | Estimate label boundaries |
| `ACTIVITY_LOW_RUN_WINDOWS` / `ACTIVITY_PEAK_COUNT` | `3` / `3` | Low-run minimum and returned peak count |
| `ACTIVITY_DECLINE_LAST_WINDOWS` / `ACTIVITY_DECLINE_MIN_WINDOWS` | `3` / `6` | Decline window count and minimum history |
| `ACTIVITY_DECLINE_THRESHOLD` | `0.20` | Minimum baseline-to-recent estimate drop |
| `ACTIVITY_VOICE_LOW_THRESHOLD` / `ACTIVITY_VOICE_MIN_WINDOWS` | `0.20` / `3` | Low aggregate voice-activity rule threshold and sample count |
| `ACTIVITY_MOVEMENT_SPIKE_THRESHOLD` / `ACTIVITY_NOISE_THRESHOLD_DBFS` | `0.60` / `-35` | R4 movement/audio evidence thresholds |
| `ACTIVITY_MAX_SUGGESTIONS` | `4` | Maximum rule-based suggestions per lecture read |

The eight-lecture, 60-student simulated insight sample can be loaded from the
`backend` directory after database setup:

```powershell
.\.venv-backend\Scripts\python.exe -m sample_data.generate_sample
```

It is idempotent and reports the lecture ID containing the simulated exit
spike. Use `GET /insights/{lecture_id}` to generate and store insights for it.

Activity windows can be sent to `POST /activity` as one JSON object or an array.
The API stores numeric aggregate features only. Engagement estimates and
suggestions state that they are based on observable indicators. An ADMIN or
assigned FACULTY user can record a suggestion decision; each re-decision
appends an authenticated actor to the decision log. HOD users can read the
history only within their mapped department.

See [API_CONTRACT.md](../docs/API_CONTRACT.md) for request fields, lifecycle,
attendance, dashboard, analytics, filters, response statuses, and error behavior.

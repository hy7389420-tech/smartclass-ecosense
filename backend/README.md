# SmartClass EcoSense Backend

FastAPI backend for SmartClass EcoSense, including catalog CRUD and CV event
ingestion.

## Setup (Windows PowerShell)

From the repository root:

```powershell
py -3.12 -m venv backend\.venv-backend
backend\.venv-backend\Scripts\python.exe -m pip install --upgrade pip
backend\.venv-backend\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
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

## Test and lint

From the repository root:

```powershell
Set-Location backend
.\.venv-backend\Scripts\python.exe -m pytest
.\.venv-backend\Scripts\python.exe -m ruff check .
.\.venv-backend\Scripts\python.exe -m ruff format --check .
```

Configuration is read from environment variables and `backend/.env`. Never put
real credentials or secrets in `.env.example`.

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
Send it as `Authorization: Bearer <token>` to protected APIs. `/health`,
`/ready`, `/auth/login`, and camera-key-authenticated event ingestion remain
available without a user token.

Set `JWT_SECRET_KEY` to a randomly generated value of at least 32 characters
for production. When blank in development, a process-local random secret is
generated; tokens become invalid after restarting the server. Login rate
limiting is process-local and is intended for this MVP, not a multi-worker
deployment.

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

Event-ingestion settings in `backend/.env`:

| Variable | Default | Purpose |
|---|---:|---|
| `REQUIRE_CAMERA_KEY` | `true` | Require a registered camera key |
| `EVENT_TIME_GRACE_SECONDS` | `300` | Allowed distance outside lecture time |
| `MIN_EVENT_CONFIDENCE` | `0.5` | Lower confidence is saved for review |
| `MAX_EVENT_BATCH_SIZE` | `100` | Maximum events in one batch (up to `1000`) |
| `CAMERA_OFFLINE_SECONDS` | `120` | Maximum time since camera activity before dashboards show "Camera Offline" |
| `UNDERUTILIZED_CUTOFF_PERCENT` | `40` | Utilization below this value is classified as underutilized |
| `OVERUTILIZED_CUTOFF_PERCENT` | `90` | Utilization above this value is classified as overutilized |
| `INSIGHT_WINDOW_MINUTES` | `5` | Exit-anomaly bucket size |
| `INSIGHT_MIN_EXITS` | `3` | Minimum exits required to flag an anomaly bucket |
| `INSIGHT_MIN_BUCKETS` | `3` | Minimum lecture buckets required for anomaly analysis |
| `INSIGHT_MIN_HISTORY` | `3` | Completed same-class lectures required for a trend |
| `INSIGHT_HISTORY_LECTURES` | `5` | Maximum prior lectures considered for trend comparison |
| `ACTIVITY_MAX_BATCH_SIZE` | `100` | Maximum windows accepted per `POST /activity` request |
| `ACTIVITY_MIN_WINDOW_SECONDS` / `ACTIVITY_MAX_WINDOW_SECONDS` | `1` / `300` | Accepted activity window duration |
| `ACTIVITY_MOVEMENT_MIN/MAX`, `ACTIVITY_FRONT_MIN/MAX`, `ACTIVITY_VOICE_MIN/MAX` | `0` / `1` | Normalization ranges for ratio signals |
| `ACTIVITY_AUDIO_MIN_DBFS` / `ACTIVITY_AUDIO_MAX_DBFS` | `-120` / `0` | Audio level normalization range |
| `ACTIVITY_*_WEIGHT` | `0.30`, `0.20`, `0.20`, `0.20`, `0.10` | Movement, inactivity, head-front, voice, audio signal weights |
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

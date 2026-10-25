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
| `CAMERA_ONLINE_WINDOW_SECONDS` | `120` | How recent an ingested event must be for the dashboard to show a camera as online |
| `UNDERUTILIZED_CUTOFF_PERCENT` | `40` | Utilization below this value is classified as underutilized |
| `OVERUTILIZED_CUTOFF_PERCENT` | `90` | Utilization above this value is classified as overutilized |

See [API_CONTRACT.md](../docs/API_CONTRACT.md) for request fields, lifecycle,
attendance, dashboard, analytics, filters, response statuses, and error behavior.

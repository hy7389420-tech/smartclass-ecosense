# SmartClass EcoSense

SmartClass EcoSense is an AI-assisted sustainable classroom presence and resource
optimization system for observing classroom occupancy, entry and exit activity,
room utilization, and aggregate teaching support signals. It combines presence
events with computer vision and audio inputs, then presents the resulting
information through a FastAPI backend and React dashboard. The MVP also uses a
camera-free simulator so the complete API and dashboard flow can be tested
locally.

## Architecture

- **Computer vision (CV):** Optional camera-based signals for movement, person
  presence, sustained presence, head pose, and event delivery.
- **Audio:** Optional aggregate classroom audio indicators. Raw audio is not
  stored or displayed in the dashboard.
- **Backend:** Python and FastAPI provide authentication, classroom and lecture
  APIs, presence calculations, analytics, review workflows, audit logs, and
  camera health.
- **Frontend:** React and Vite display lecture context, presence KPIs, student
  status, review actions, suggestions, camera metadata, and alerts.
- **Storage:** SQLite is the MVP database. Raw video is not required and is not
  retained by the application.

## Windows setup

Run the following from the repository root in PowerShell.

### 1. Create and install the backend environment

```powershell
py -3.12 -m venv backend\.venv-backend
backend\.venv-backend\Scripts\python.exe -m pip install --upgrade pip
backend\.venv-backend\Scripts\python.exe -m pip install -r backend\requirements.txt
```

### 2. Create backend configuration

```powershell
if (-not (Test-Path backend\.env)) {
  Copy-Item backend\.env.example backend\.env
}
```

Set required local values such as the JWT secret and other camera settings in
`backend/.env`. Never commit real passwords, API keys, or camera keys.
Set JWT_SECRET_KEY in backend/.env (use a long random value, never commit it). Without it, a new secret is generated on every start and everyone is logged out after a restart.

### 3. Install frontend dependencies

```powershell
if (-not (Test-Path frontend\.env)) {
  Copy-Item frontend\.env.example frontend\.env
}
Set-Location frontend
npm install
Set-Location ..
```

## Run the application on Windows

Backend, from the repository root:

```powershell
cd backend
.\.venv-backend\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Backend URLs:

- Health: `http://127.0.0.1:8000/health`
- API documentation: `http://127.0.0.1:8000/docs`

Frontend, in a second terminal from the repository root:

```powershell
cd frontend
npm run dev
```

Open the frontend shown by Vite, normally `http://localhost:5173`.

## Verified features

- Human review workflow (resolve without correction and save human correction) was verified in the browser with audit log entries.

## Privacy and responsible use

- Raw video and continuous raw audio are not stored in the application data
  model. The dashboard uses required presence events and aggregate metadata.
- AI insights and suggestions are advisory. AI must never accuse, blame, rank,
  punish, or infer why a person left a classroom.
- Sensitive manual decisions receive human review and must use an audit log that
  records the correction, reviewer, time, and reason.
- Camera status describes recent system activity, not measured detection
  accuracy. Claims of accuracy or legal compliance should only be made after
  documented measurement and review.

## Sustainability

- [Simulated utilization examples from test fixtures](docs/UTILIZATION_EXAMPLE.md)
  show underutilized, balanced, overutilized, and insufficient-data endpoint
  responses. These examples are not measured data, and energy savings are
  `Not measured`.

## Known limitations

- The camera/CV module is offline in the demo; the demo uses seeded events.
- Live CV was tested with a webcam and detects entry/exit events; backend event delivery validation is still being finalized.
- After changing `LECTURE_ID`, clear the stale CV queue files
  `cv/data/events.jsonl` and `cv/data/events.delivery` together before
  restarting the CV module.
- Camera status describes recent system activity, not detection accuracy.
- Retention script and tests exist; automatic scheduling is documented but not enabled by default.
- No accuracy or energy-savings results have been measured yet.
- Repeated camera alerts are grouped into one entry with a count.
- Some integration states may depend on local configuration, a running backend,
  and valid demo data.
- Computer vision, face identity, and camera deployment remain subject to local
  ethical review and suitable consent policies.

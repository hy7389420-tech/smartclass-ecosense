# SmartClass EcoSense Frontend

The SmartClass EcoSense frontend is a React application built with Vite. It
shows presence dashboard information, lecture context, camera status and
alerts, aggregate activity, neutral suggestions, suggestion history, and
human-review actions.

## Windows setup

From the repository root:

```powershell
if (-not (Test-Path frontend\.env)) {
  Copy-Item frontend\.env.example frontend\.env
}
cd frontend
npm install
```

Keep secrets out of frontend environment files. Camera keys and backend
credentials must remain on the backend or in protected local backend
configuration.

## Run

```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173`. The frontend uses its configured API base URL,
normally `/api`, to communicate with the FastAPI backend on port 8000.

## Available commands

```powershell
npm run lint
npm run build
npm run preview
```

## Privacy and UI rules

- Camera panels display text and metadata only; do not add live video or raw
  frame display.
- Do not claim measured detection accuracy or energy savings.
- Alerts and suggestions must use neutral, observable wording.
- Human review is for verified corrections and resolution reasons. It must not
  accuse, rank, blame, or punish students or faculty.

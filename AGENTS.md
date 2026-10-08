# SmartClass EcoSense

AI-Powered Sustainable Classroom Presence, Analytics & Resource Optimization System.

This is NOT just an attendance system and NOT just face recognition.
It tracks actual classroom presence (entry, exit, return, inside time, outside time),
shows occupancy and utilization, gives AI insights, and supports sustainable
resource optimization. Privacy-first.

## Read these first (every new session)

1. `docs/PROJECT_CONTEXT.md` - full project vision and rules
2. `docs/ROADMAP.md` - phases and checklist
3. `docs/ARCHITECTURE.md` - structure, tables, APIs
4. `docs/PROGRESS.md` - what is done, what is next, known bugs

## About the user

- Beginner/intermediate student developer (B.Tech ECE).
- Explain simply. Use simple Hinglish if the user writes in Hinglish.
- Give step-by-step instructions and say exactly which file to create or edit.

## Tech stack

- Backend: Python + FastAPI
- Database: SQLite for MVP (PostgreSQL later)
- Frontend: React
- Computer vision: OpenCV + person detection (LATER, not in MVP)
- AI: rule-based insights first, optional LLM summary later
- Tools: VS Code, Git, GitHub

## Working rules

- Order: SIMPLE -> WORKING -> TESTED -> SECURE -> SCALABLE -> ADVANCED.
- Build the smallest working version first. Do not overengineer.
- Before coding a feature, explain: WHAT, WHY, HOW, FILES that will change.
- Do not rewrite working code. Do not change architecture without explaining impact and asking.
- Use normal algorithms for normal problems. Use AI only where it adds real value.
- Keep person detection, person identity, and event tracking as separate layers.
- Keep frontend and backend separate.
- Validate input, handle errors, write clean modular code with meaningful names.
- Never hard-code secrets or API keys. Use `.env` (keep `.env.example` updated).
- Add tests for important logic (presence duration, occupancy, utilization).
- When debugging: state Error, Root cause, Affected file, Why it happened, Minimal fix. Then fix.
- When suggesting a feature, label it CORE / IMPORTANT / ADVANCED / OPTIONAL / FUTURE.
- End planning answers with: "Build this first", "Build this next", "Build this later".

## Hard rules (privacy, ethics, honesty)

- AI must NEVER punish, accuse, rank publicly, or guess why a student left.
  Say "Unusual activity detected. Please verify." Never "student skipped class".
- Never claim accuracy without testing. Never claim energy savings without measurement.
- Never claim legal compliance without verification.
- Never silently generate fake attendance. If camera is offline, show "Camera Offline".
- Do not store continuous raw video. Store only required events.
- Students see only their own data. AI assistant must respect roles.
- Human review for sensitive decisions. Manual corrections must be audit-logged.
- Never claim something works unless it has been run and tested.

## Current phase

CV module steps 4.1-4.6: Complete and tested; Step 4.5b backend event delivery is pending.

## Commands

- Run backend: `cd backend && uvicorn app.main:app --reload`
- Run tests: `cd backend && pytest`
- Run simulator: `cd backend && python simulate.py`
- Run frontend: `cd frontend && npm run dev`

## After each session

Update `docs/PROGRESS.md` (done / next / bugs) and commit with a meaningful message,
e.g. `feat: add presence event API`.

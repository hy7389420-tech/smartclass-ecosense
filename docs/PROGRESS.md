# SmartClass EcoSense - Progress Log

Update this file at the END of every coding session (you or the AI agent).
A new chat/agent reads this first to know where to continue.

## Current status
- **Current phase:** CV Steps 4.1-4.6 and Steps A-F are implemented and unit tested; backend Phases 0-6 are implemented and tested.
- **Last updated:** 2026-10-25
- **Working right now:** Backend Phase 6 analytics and sustainability are complete and verified.
- **Next task:** With approval, start Backend Phase 7 anomaly, trend and insights; CV hardware validation remains pending.

## Backend status
- [x] Phase 0: isolated backend environment, FastAPI app, `/health`, database-checking `/ready`, structured logging, setup docs, and tests.
- [x] Phase 1: SQLAlchemy models for all prompt tables, SQLite foreign keys and session transactions, initial Alembic migration, repeatable demo seed, and database documentation.
- [x] Phase 2: paginated CRUD APIs for departments, classes, classrooms, students, and lectures; validation; API contract; and OpenAPI export.
- [x] Phase 3: pure presence calculation, event sequence derivation, and edge-case tests.
- [x] Phase 4: camera-key authenticated single/batch event ingestion, RETURN derivation, review flags, event filters, idempotency, JSONL import, API docs, and OpenAPI export.
- [x] Phase 5: idempotent lecture start/end lifecycle, finalized attendance records, live/final attendance APIs, student presence history, dashboard cards/table, review count, and recent-event camera status.
- [x] Phase 6: pure time-weighted occupancy analytics, lecture exit/outside metrics, classroom utilization/date filtering, no-data handling, configurable utilization labels, simulated neutral suggestions, and day/week/month outside-duration aggregation.
- [ ] Next: Phase 7 anomaly, trends and insights, after approval.
- Test result: 65 backend tests passed, including 8 analytics tests, 18 event-ingestion/import tests, 3 attendance/dashboard integration tests, 14 presence tests, and lifecycle-status validation. Ruff lint and format checks passed. Alembic fresh-database upgrade and schema-drift check passed; demo seed created 5 students and 1 lecture. Uvicorn CRUD list endpoint smoke test returned HTTP 200.
- Known tooling warning: Starlette's TestClient currently warns that its `httpx` integration is deprecated; tests still pass.
- Presence rule decision: count only observed time from the first ENTRY; the prompt's 10:02 ENTRY example therefore yields 46 inside minutes and 12 outside minutes. Some older project examples still say 48; update them when their scope is approved.
- Event ingestion: `REQUIRE_CAMERA_KEY=true`, 300-second grace window, minimum confidence 0.5, and max batch size 100 by default. Invalid sequences and uncertain events are persisted as review-required and excluded from calculations.
- Phase 4 event endpoint and JSONL importer tests pass. CV hardware validation and direct live delivery remain separate pending work; no CV files were changed for this phase.
- Phase 5 dashboard camera status is based on a registered camera's last successfully ingested event within 120 seconds by default; it is not an independent camera health probe. Attendance uses only active students and excludes flagged/unconfirmed events.
- Phase 6 analytics use valid confirmed events from active enrolled students and clip calculations to scheduled lecture time. Utilization suggestions are simulated only; zero-occupancy intervals are reported only within scheduled completed lectures and no energy savings are claimed.

## Done
- [x] Context files created (AGENTS.md, PROJECT_CONTEXT.md, ROADMAP.md, ARCHITECTURE.md, PROGRESS.md)
- [x] CV Step 4.1: webcam capture and live window
- [x] CV Step 4.2: YOLO person-only detection and bounding boxes
- [x] CV Step 4.3: ByteTrack IDs displayed on person boxes
- [x] CV Step 4.4: virtual line crossing and console ENTRY/EXIT
- [x] CV Step 4.5a: console and `cv/data/events.jsonl` event output
- [x] CV Step 4.6: manual track-ID-to-demo-student mapping
- [x] CV Step A: sustained-presence confirmation gates ENTRY/EXIT output
- [x] CV Step B: motion scoring and window inactivity aggregation
- [x] CV Step C: class-level head orientation estimate and recorded-video test script
- [x] CV Step D: in-memory audio level and energy-based voice activity features
- [x] CV Step E: merge numeric activity features and append activity_windows.jsonl
- [x] CV Step F: `python -m cv.session` orchestrates camera, CV features, microphone, and clean shutdown

## In progress
- Step 4.5b backend event delivery remains pending.

## Next (in order)
1. [ ] Manually validate the integrated camera/microphone session
2. [ ] Step 4.5b: send CV events to the backend (PENDING)

## Known bugs / issues
- Fixed: duplicate microphone chunk timestamps could trigger a crash in the audio window aggregator during `cv.session` shutdown. This was caused by multiple audio chunks arriving at the same `time.monotonic()` timestamp. The fix keeps them sorted and non-decreasing without inventing fake data.

## Decisions made
- SQLite for MVP, PostgreSQL later
- Simulator before camera
- Rule-based insights before any LLM
- Pehle Phase 0-4 (MVP), uske baad hi camera/AI advanced features

## Commands that work (add only after you have tested them)
- `.\.venv-cv\Scripts\python.exe -m pytest cv\tests\test_session.py` (5 passed)
- `.\.venv-cv\Scripts\python.exe -m cv.session` (available; live hardware validation pending)
- `.\.venv-cv\Scripts\python.exe -m pytest cv\tests\test_activity_windows.py` (5 passed)
- `.\.venv-cv\Scripts\python.exe -m pytest cv\tests audio\tests` (76 passed)
- `.\.venv-cv\Scripts\python.exe -m pip install -r audio\requirements.txt` (sounddevice 0.5.6 available)
- `.\.venv-cv\Scripts\python.exe -m pytest audio\tests\test_audio_features.py` (12 passed)
- `.\.venv-cv\Scripts\python.exe -m pip install -r cv\requirements.txt` (MediaPipe 1.1.1 installed)
- `New-Item -ItemType Directory -Force cv\data; Invoke-WebRequest -Uri 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task' -OutFile cv\data\face_landmarker.task` (model downloaded)
- `.\.venv-cv\Scripts\python.exe -m pytest cv\tests\test_sustained.py` (9 passed)
- `.\.venv-cv\Scripts\python.exe -m pytest cv\tests\test_motion.py` (7 passed)
- `.\.venv-cv\Scripts\python.exe -m pytest cv\tests\test_headpose.py` (11 passed)
- `.\.venv-cv\Scripts\python.exe -m cv.tools.test_headpose_video --help` (CLI help verified)

## Test status
- Sustained-presence tests: 9 passed; motion tests: 7 passed; head-pose tests: 11 passed; audio tests: 12 passed; activity-window tests: 5 passed; session tests: 5 passed; full CV + audio suites: 76 passed.
- Last test run: 2026-10-24

## Session log
| Date | What was done | Commit message |
|---|---|---|
| (date) | Created context files | docs: add project context files |

## Notes for the next session
- Read AGENTS.md, ROADMAP.md and ARCHITECTURE.md first.
- Work on ONE phase at a time. Explain WHAT, WHY, HOW, FILES before coding.

## CV module progress
- Step 4.1 webcam capture: implemented in `cv/capture.py`; camera index and window title are in `cv/config.py`.
- User confirmed Step 4.1 live webcam test works on 2026-10-08.
- User confirmed Step 4.2 person-only YOLO detection and live bounding boxes work on 2026-10-08.
- User confirmed Step 4.3 ByteTrack tracking IDs work on the webcam on 2026-10-08.
- Step 4.4 pure line-crossing logic, live line overlay and console-only ENTRY/EXIT reporting implemented; 10 fake-point tests and mocked capture integration check passed.
- Step 4.5a JSONL event sender implemented with console output; event schema and append behavior tests added.
- User confirmed Step 4.5a live webcam event logging works on 2026-10-08.
- Step 4.6 manual identity mapping implemented: click a visible person box, then press 1-5 to map the track ID to a demo student; unknown IDs are review-flagged in JSONL.
- Fixed repeated ENTRY/EXIT events caused by line-side jitter: the line counter now uses a configurable hysteresis band while preserving the 2-second cooldown.
- User confirmed CV module Steps 4.1-4.6 are complete and tested.
- Next CV task: Step 4.5b backend event delivery (PENDING).

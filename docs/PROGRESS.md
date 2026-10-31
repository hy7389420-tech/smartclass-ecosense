# SmartClass EcoSense - Progress Log

Update this file at the END of every coding session (you or the AI agent).
A new chat/agent reads this first to know where to continue.

## Current status
- **2026-10-31 checkpoint 9B verification:** Review requests include `lecture_id`; dashboard review badge now uses the scoped queue count so the pending-review count matches the human-review panel for each lecture. Backend outage coverage keeps suggestion history and camera alerts in separate error states. Frontend lint and production build passed; App.css required no change.
- **2026-10-31 checkpoint 9B:** Fixed independent frontend suggestion/alert loading failures by processing their errors even when the dashboard request fails. Added separate loading, empty, and error states; the review panel now always renders and shows “No events flagged for review” when empty. Review API requests now send `lecture_id` to the lecture-scoped backend queue. JWT/login behavior was unchanged. Frontend lint passed and production build passed.
- **2026-10-31 checkpoint 8:** Added text-only camera connection details and unresolved operational alerts using dashboard camera status and the existing scoped alerts endpoint. The UI separates loading, empty, and error states and makes clear that status is metadata, not detection accuracy; it does not stream or display video frames. Suggestion history and human review workflow were not changed.
- **2026-10-31 checkpoint 7:** Added suggestion decision history UI using the existing scoped history endpoint. The history panel has separate loading, empty, and error states and remains advisory-only; camera alerts and the human review workflow were not changed.
- **2026-10-31 checkpoint 6:** Added a human-review frontend panel for the existing scoped review queue. It lists current-lecture flagged events and supports reason-required correction and resolve-without-correction actions through the backend contract. No punish/accuse language, backend changes, suggestion-history changes, or camera-alert changes were made. Frontend lint passed; production build passed.
- **2026-10-31 checkpoint 5:** Lecture selector now includes lecture status; selected lecture also shows a live/scheduled/completed/cancelled badge and its local start/end date/time window. Changed only frontend/src/App.jsx, frontend/src/App.css, and docs/PROGRESS.md. Review workflow, suggestion history, and camera alerts remain untouched. Frontend lint passed; production build passed.
- **2026-10-31 smallest-two frontend fixes:** Added API error metadata (`code`, `Retry-After`) in frontend/src/services/api.js. Added overlap prevention for dashboard refresh and separate loading/no-data/error states for engagement in frontend/src/App.jsx. Added the engagement error style in frontend/src/App.css. Verified frontend lint, production build, dev HTTP 200, and clean whitespace checks.
- **2026-10-31 checkpoint 4:** Prioritized frontend integration fixes from docs/frontend/GAP_REPORT.md. Smallest-first plan: fix structured API errors and refresh overlap; improve engagement distinguishable loading/error/no-data states; add lecture status/time context; make needs-review actionable through scoped review APIs; add suggestion decision history; then add camera details/alerts as the optional operational layer. Awaiting user selection before frontend edits.
- **2026-10-31 checkpoint 3:** Frontend dev server is running on port 5173 and the login page loaded with HTTP 200; frontend production build passed. Core dashboard paths and field names were compared with API_CONTRACT and match, but authenticated browser dashboard visuals were not claimed because no local password/browser session was available. Added docs/frontend/GAP_REPORT.md without changing frontend files. Remaining browser flow items require an authenticated local session: lecture selector, KPI rendering, student table, Camera Offline state, and Needs-review badge.
- **2026-10-31 checkpoint 2:** Demo seed completed, camera 2 created for classroom 1, live lecture 6 created for the current time window, and the simulator delivered 8 accepted events plus 1 flagged UNKNOWN review event through `POST /events/batch`. Authenticated dashboard verification returned 5 total students, 4 present, 3 inside, 1 outside, 1 absent, 60% occupancy, Camera Online, and 1 pending review.
- **Presence formula verification:** targeted attendance tests passed (20 tests). The reference 10:02 entry, 10:30 exit, 10:42 return, and 11:00 lecture end produces 46 inside minutes, 12 outside minutes, 1 exit, and 1 return. This is consistent with counting time from first ENTRY rather than the full lecture start.
- **2026-10-30 integration fix:** Repaired the frontend authorization header, added a Vite `/api` reverse proxy to FastAPI, and started both services. Frontend build/lint pass; backend health and frontend proxy health both return HTTP 200.
- **2026-10-30 merge/runtime fix:** Fixed expired-token handling so the frontend returns to login on HTTP 401, removed duplicate-port startup ambiguity with strict Vite port 5173, and verified backend plus `/api` proxy health.
- **2026-10-30 login recovery:** Added an admin password-reset CLI that prompts with hidden input; frontend login now preserves the backend's invalid-credentials message instead of hiding the 401 cause.
- **2026-10-30 frontend foundation:** React/Vite frontend created with JWT login, lecture selection, auto-refreshing presence dashboard, student table, camera-offline banner, activity estimate chart, and neutral suggestion accept/reject/ignore actions. Build verification is in progress.
- **Current phase:** CV Steps 4.1-4.6 and Steps A-F are implemented and unit tested; backend Phases 0-15 and Week 6 Phases 1-2 (fusion and rule-based suggestions) are implemented and tested. Docker/PostgreSQL runtime checks remain unavailable.
- **Last updated:** 2026-10-27
- **Working right now:** Week 6 fusion and suggestion logic, sample generators, JSONL CLIs, and tests are verified. The frontend folder is absent, so the Phase 4 chart and panel were skipped. Physical camera/microphone and Docker/PostgreSQL runtime checks remain pending.
- **Next task:** Add the frontend before attempting the chart/panel phase. Separately, run the prepared physical camera session and Docker/PostgreSQL checks when those environments are available.

## Backend status
- [x] Phase 0: isolated backend environment, FastAPI app, `/health`, database-checking `/ready`, structured logging, setup docs, and tests.
- [x] Phase 1: SQLAlchemy models for all prompt tables, SQLite foreign keys and session transactions, initial Alembic migration, repeatable demo seed, and database documentation.
- [x] Phase 2: paginated CRUD APIs for departments, classes, classrooms, students, and lectures; validation; API contract; and OpenAPI export.
- [x] Phase 3: pure presence calculation, event sequence derivation, and edge-case tests.
- [x] Phase 4: camera-key authenticated single/batch event ingestion, RETURN derivation, review flags, event filters, idempotency, JSONL import, API docs, and OpenAPI export.
- [x] Phase 5: idempotent lecture start/end lifecycle, finalized attendance records, live/final attendance APIs, student presence history, dashboard cards/table, review count, and recent-event camera status.
- [x] Phase 6: pure time-weighted occupancy analytics, lecture exit/outside metrics, classroom utilization/date filtering, no-data handling, configurable utilization labels, simulated neutral suggestions, and day/week/month outside-duration aggregation.
- [x] Phase 7: configurable exit-spike detection, same-class outside-duration trends, privacy-preserving stored insights regenerated without duplication, and an idempotent 8-lecture/60-student simulated sample.
- [x] Phase 8: validated numeric activity-window ingestion; weighted class-level estimates with missing-signal handling, moving-average smoothing, statistically thresholded peaks, low runs and baseline/recent decline detection; neutral, evidence-backed R1-R6 teaching suggestions with append-only decision history.
- [x] Phase 9: Argon2id password hashing, short-lived JWT login/me/change-password, immediate token revocation after password changes, generic login errors and in-process rate limiting; protected routes with ADMIN/HOD/FACULTY/STUDENT scopes; explicit nullable unique `users.student_id` mapping; secure admin provisioning; authenticated append-only suggestion decision logs.
- [x] Phase 10: append-only manual correction events and audit snapshots; scoped review queue and resolution; camera heartbeat, offline detection and recovery; deduplicated neutral low-confidence/unusual-exit alerts; role-scoped alert resolution and ADMIN-only audit-log API.
- [x] Phase 11: role-scoped lecture and daily/weekly reports in JSON/CSV; report estimate/limitations notes; 90-day retention preview/deletion endpoint and CLI with audit entries; retention policy documentation.
- [x] Phase 12: exact-origin CORS validation, request body caps, per-IP rate limits, security headers, safe error envelopes/logging, production JWT secret checks, and dependency audit.
- [x] Phase 13: off-by-default ADMIN/HOD natural-language assistant with six rule-based aggregate intents, department-scoped queries, student-data refusals, API contract, and OpenAPI export. No LLM or generated SQL is used.
- [x] Phase 14 backend scope: documented the CV event API/retry contract, added an append-first camera-free API simulator and JSONL replay integration test, and reject events when a known student is not enrolled in the lecture's class.
- [x] Phase 15: added a slim non-root backend Docker image, Compose with persistent SQLite and an opt-in PostgreSQL service, a pinned Psycopg driver, fuller backend setup/environment/Docker documentation, a role-scoped API contract, and architecture notes. Docker/PostgreSQL runtime checks remain unavailable here.
- Test result (2026-10-27): full backend `pytest` passed (162 tests, 1 existing Starlette `TestClient`/httpx deprecation warning); Ruff check and formatting passed for changed files; `pip-audit -r requirements.txt` previously found no known vulnerabilities. OpenAPI export parsed successfully (42 paths, 68 schemas).
- Phase 15 isolated demo (2026-10-27): migrations, seed, admin login, camera provisioning, lecture lifecycle, simulator (7 accepted and 1 review-flagged), dashboard (5 students, 4 present, 2 inside, 2 outside, 1 absent, 40% occupancy, 1 pending review), insights, correction plus audit entry, report, and retention dry-run all passed against a temporary SQLite database. Temporary database and JSONL files were removed.
- Week 6 Phases 1-2 (2026-10-27): configurable null-aware fusion, two-window default smoothing, statistical peaks/low runs/decline, a 12-window sample generator, and JSONL CLIs are implemented. R1-R6 suggestions now include numeric/time evidence, signals used, a neutral estimate note, pending status, deduplication and severity/cap ordering. Focused suggestion/activity tests passed (16); full backend suite passed (162). The sample suggestion CLI returned R1, R3 and R5. Existing decision API/storage was preserved with a compatibility mapping for persisted severity values. Frontend chart/panel and LLM wording were skipped because `frontend/` is absent.
- CV Step 4.5b validation: focused sender tests passed (17); `cv/tests` passed (71); full `cv/tests` plus `audio/tests` passed (84). Ruff check/format and Pylance syntax checks passed. A controlled local API test delivered and verified one event through the sender. Physical camera-to-backend validation has not been run.
- End-to-end simulator demo (2026-10-25): upgraded the local database to Alembic head, ran the idempotent seed, created a current-time scheduled lecture and temporary camera/admin credentials, then ran `scripts.simulate`. The API accepted 8 events and stored 1 `UNKNOWN` event for review. Authenticated `GET /dashboard/2` returned total=5, present=4, inside=2, outside=2, absent=1, occupancy=40%, pending_review_count=1. Swagger `/docs` loaded with the dashboard route. Temporary admin and camera credentials were removed; the completed demo lecture and event data remain in the local database, and the JSONL stream remains in `backend/data/simulated_events.jsonl`.
- CV Step 4.5b (2026-10-25): append-first JSONL outbox sender with background HTTP delivery, `.env` configuration, retry/checkpoint behavior, tests, and controlled local API verification.
- Live camera setup (2026-10-27): created root `.env` from `.env.example` with the camera key held only in `.env`; created admin and camera for classroom 1; verified five active demo students are enrolled in class 1; created and started lecture 4 for the current time. Waiting for the user to run the physical webcam test. Do not copy the camera key into chat or terminal commands.
- Known tooling warning: Starlette's TestClient currently warns that its `httpx` integration is deprecated; tests still pass.
- Auth limitation: login rate limiting is process-local and keyed by client IP; multi-worker/production deployments need a shared limiter. Blank development JWT secrets are generated per process; configure a strong `JWT_SECRET_KEY` in production.
- Phase 12 limitation: global/auth/event rate limits are process-local and use direct client IP; reverse-proxy deployments need infrastructure controls or trusted-proxy handling. No penetration or load test was run.
- Phase 13 limitation: the assistant is deterministic intent matching, not an LLM; it supports only the six documented aggregate questions, and date ranges use `LOCAL_TIMEZONE`. Answers depend on the completeness of stored finalized events and attendance data.
- Phase 14/4.5b limitation: CV now has append-first event delivery with a persistent local archive and checkpoint; the local API path was verified with a synthetic event, but physical camera/microphone validation remains pending. Delivery retries are bounded per cycle; events remain available for replay.
- Phase 15 limitation: Docker, Docker Compose, PostgreSQL, and `psql` are unavailable in this environment. The Compose YAML parses, but image build, container startup, PostgreSQL connection, and PostgreSQL Alembic migration have not been tested. The Psycopg requirement is declared, but its local package download timed out; SQLite tests and demo do not require it. SQLite-specific connection settings and Alembic batch rendering are explicitly guarded; static search is not proof of full PostgreSQL compatibility.
- Mapping decision: legacy accounts stay `student_id=NULL`; no email/name matching is performed. HOD department scope uses the department on the HOD's linked `faculty` profile; missing scope mappings are denied.
- Phase 10 correction provenance: keep the flagged source row unchanged except its review status; append a linked `MANUAL_CORRECTION` row whose effective `correction_event_type` participates in presence/analytics. Every review and alert resolution records actor, reason, and before/after values.
- Camera health thresholds: `CAMERA_OFFLINE_SECONDS=120`; low-confidence and unusual-exit alerts default to 3 events in a 5-minute window. Alert refresh is performed on `GET /alerts` and camera heartbeats; no background scheduler is configured.
- Phase 11 retention limitation: the 90-day job removes presence events, activity windows, and insights only. Attendance records and audit logs (which may contain correction snapshots) are retained; no scheduler is configured. PDF export was not added because no lightweight PDF library is already installed; JSON/CSV are supported.
- Presence rule decision: count only observed time from the first ENTRY; the prompt's 10:02 ENTRY example therefore yields 46 inside minutes and 12 outside minutes. Some older project examples still say 48; update them when their scope is approved.
- Event ingestion: `REQUIRE_CAMERA_KEY=true`, 300-second grace window, minimum confidence 0.5, and max batch size 100 by default. Invalid sequences and uncertain events are persisted as review-required and excluded from calculations.
- Phase 4 event endpoint and JSONL importer tests pass. CV hardware validation and direct live delivery remain separate pending work; no CV files were changed for this phase.
- Phase 5 dashboard camera status now uses the Phase 10 `CAMERA_OFFLINE_SECONDS` heartbeat/activity freshness threshold. Attendance uses only active students and excludes flagged/unconfirmed events.
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
- Phase 15 approval; Docker/PostgreSQL runtime validation needs an environment with those tools. Physical CV camera/microphone testing also remains pending.

## Next (in order)
1. [ ] Manually validate the integrated camera/microphone session
2. [ ] Run the Docker image and optional PostgreSQL migration/API checks when the required runtime is available

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
| 2026-10-25 | Backend Phase 9 authentication, role scopes, student mapping, and decision logs | feat(backend): add auth and role-based access |
| 2026-10-25 | Backend Phase 14 CV integration contract, simulator, replay tests, and live API/dashboard demo | Not committed |
| 2026-10-27 | Prepared `.env`, admin, camera and live lecture for physical CV validation; awaiting webcam run | Not committed |

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
- Next CV task: run the prepared live camera/microphone session and verify its generated events; synthetic Step 4.5b API delivery is implemented and tested.

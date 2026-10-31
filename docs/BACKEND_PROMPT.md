# BACKEND PROMPT: SmartClass EcoSense (zero to advanced)

> Paste everything below the line into VS Code + Copilot Chat (Agent mode) or Antigravity.
> Scope: ONLY `backend/` (plus backend docs). Other modules (cv/, audio/, frontend/) have their own prompt files.
> Save a copy as `docs/prompts/BACKEND_PROMPT.md` in the repo.

---

BUILD mode. Read AGENTS.md, docs/MASTER_PROMPT.md, docs/ARCHITECTURE.md, docs/ROADMAP.md, docs/SCHEDULE.md and docs/CV_SPEC.md first.

## GOAL
Build the complete SmartClass EcoSense backend from zero to advanced: FastAPI + SQLAlchemy + Alembic, SQLite for development (PostgreSQL-ready via DATABASE_URL), event ingestion from the CV module, presence engine, dashboard and attendance APIs, analytics and sustainability, anomaly and trend insights, engagement fusion and teaching suggestions with a teacher decision log, authentication and role-based access, manual correction with audit log, camera health and alerts, reports, data retention, security hardening, Docker, tests and API documentation.

## SCOPE AND OWNERSHIP (important: this file will be merged with other module prompts)
- You may create or edit ONLY: `backend/`, `docs/backend/`, `docs/API_CONTRACT.md`, `docs/DATABASE.md`, `docs/CV_INTEGRATION.md`, and the status lines in `docs/PROGRESS.md` and `AGENTS.md`.
- Do NOT edit `cv/`, `audio/`, `frontend/`. If a change there is needed (for example the CV event sender calling the backend), write the exact change in `docs/CV_INTEGRATION.md` and ask me before touching anything.
- Frontend will be built from `docs/API_CONTRACT.md`, so keep it accurate (export the OpenAPI schema into `docs/api/openapi.json` at the end of every phase that changes endpoints).

## WORKING RULES
1. Work in PHASES 0 to 15. For each phase: (a) explain WHAT, WHY, HOW, FILES in simple Hinglish and list exact PowerShell commands, (b) implement, (c) run tests and report pass counts, (d) give me the manual test steps and a ready commit message, (e) STOP and wait for my "Approved". Never start the next phase on your own.
2. If you are blocked, an instruction is ambiguous, a library API is unclear, or a choice has real consequences (data loss, security, schema change after data exists), ASK ME one clear question with 2-3 options and your recommendation. For small choices pick a sensible default, write it in docs/backend/DECISIONS.md and tell me.
3. Use a separate virtual environment `.venv-backend` (not .venv-cv). Pin versions in `backend/requirements.txt` after installing. Check current library docs before using an API; do not guess signatures.
4. Layering: routes (thin) -> services (business logic) -> repositories or models. Pure logic (presence, analytics, anomaly, trend, fusion, suggestions) must not import FastAPI, SQLAlchemy or any camera/model library, so it is unit-testable with fake data.
5. All thresholds, weights, windows, limits and cutoffs live in `backend/app/config.py` (pydantic settings, overridable by env). No magic numbers in logic.
6. Secrets only in `.env` (never committed). Keep `.env.example` complete, with no real values.
7. Every endpoint: Pydantic request and response models, input validation, consistent error format `{ "error": { "code", "message" } }`, no stack traces or internals in responses, proper status codes, pagination (limit/offset with a max) on list endpoints.
8. Time: store everything in UTC. Accept ISO 8601; a timestamp WITHOUT timezone is interpreted in `LOCAL_TIMEZONE` (default Asia/Kolkata) then converted to UTC. Return ISO 8601 with offset.
9. Privacy: store only events and numeric features. Never store video, images, raw audio or transcripts. No per-student attention or engagement score. Student-level data is returned only to authorized roles.
10. Honesty: never claim accuracy, energy savings, legal compliance or learning improvement. All engagement outputs say "estimate based on observable indicators". AI/insight wording is neutral: "Unusual activity detected. Please verify." NEVER generate words like skipped, bunked, intentionally, lazy, bored, distracted, attentive, attention score, emotion. Add one shared helper `assert_neutral_text()` and a test that scans every template.
11. Label each item CORE / IMPORTANT / ADVANCED / OPTIONAL / FUTURE. End every reply with "Build this first / next / later".
12. Tests: pytest, one test file per service and per router. Keep a running count. A phase is not done until its tests pass. Never claim something works unless you ran it.
13. After each approved phase: update `docs/PROGRESS.md` (done / next / bugs) and the implementation-status section of `docs/MASTER_PROMPT.md` (only what was actually run and tested).

## CV EVENT CONTRACT (what the existing cv/ module already writes to cv/data/events.jsonl, one JSON per line)
`student_id` (string such as a demo student code, or "UNKNOWN"), `classroom_id`, `lecture_id`, `event_type` ("ENTRY" or "EXIT" only), `timestamp` (ISO), `confidence` (0..1), `source` ("camera"), `flagged_for_review` (true for UNKNOWN), `presence_confirmed` (true once sustained presence is added).
Important: the camera only emits ENTRY and EXIT. The BACKEND derives RETURN: an ENTRY that follows an EXIT of the same student in the same lecture is stored as RETURN.
Backend must accept this payload as-is (extra unknown fields ignored, not rejected), and also accept optional `client_event_id` for idempotency.

## DATA MODEL (create with SQLAlchemy models + Alembic migrations)
departments, classes (section/year), classrooms (name, capacity), students (student_code unique, roll_no, name, class_id), faculty (user link, department), users (email unique, password_hash, role, is_active, created_at), faculty_class_assignments, lectures (classroom_id, class_id, subject, faculty_id, start_time, end_time, status), cameras (classroom_id, name, api_key_hash, last_seen_at, status), presence_events (id, client_event_id nullable unique-per-lecture, lecture_id, classroom_id, student_id nullable, student_code_raw, event_type [ENTRY/EXIT/RETURN/LECTURE_START/LECTURE_END/MANUAL_CORRECTION], timestamp_utc, confidence, source, flagged_for_review, review_status, presence_confirmed, created_at), attendance_records (lecture_id, student_id, status, first_entry, last_exit, inside_minutes, outside_minutes, exit_count, return_count, computed_at), activity_windows (lecture_id, window_start, window_end, movement_level, inactivity_seconds, front_facing_ratio nullable, audio_level_db_mean nullable, voice_activity_ratio nullable, source), insights (lecture_id, kind, text, evidence_json, created_at), suggestions (lecture_id, rule_id, title, text, evidence_json, severity, status, created_at), suggestion_decisions (suggestion_id, decision, decided_by, decided_at, note), audit_logs (id, actor_user_id, action, entity_type, entity_id, before_json, after_json, reason, created_at), alerts (kind, severity, message, classroom_id, lecture_id, camera_id, created_at, resolved_at), system_settings (key, value).
Indexes on (lecture_id, timestamp_utc), (lecture_id, student_id), and foreign keys. Soft rules enforced in services, hard constraints in the DB.

---

## PHASE 0: Project setup and /health  [CORE]
- Run a repo check first and tell me in 3 lines what already exists (backend/, cv/, docs/, git status).
- Create `backend/` structure: `app/{main.py,config.py,database.py,models/,schemas/,routes/,services/,repositories/,core/}`, `tests/`, `scripts/`, `sample_data/`, `requirements.txt`, `.env.example`, `pytest.ini`.
- Config via pydantic-settings; logging (structured, no secrets, no PII beyond ids); `GET /health` (liveness) and `GET /ready` (checks DB).
- Add ruff (lint/format) and a `make`-less command list in `backend/README.md`.
- Test: /health and /ready via TestClient.
- Done when: `uvicorn app.main:app --reload` runs and tests pass.

## PHASE 1: Database, models, migrations  [CORE]
- SQLAlchemy 2.x models for ALL tables above, Alembic initial migration, `DATABASE_URL` default `sqlite:///./ecosense.db`, SQLite foreign keys ON, session dependency, transaction handling.
- `scripts/seed_demo.py`: 1 department, 1 class, 1 classroom (capacity 60), 5 demo students (codes matching the CV demo students: Student A to E), 1 lecture today 10:00 to 11:00. No passwords here.
- `docs/DATABASE.md` with the schema table list and relationships.
- Tests: models create, constraints (unique student_code, FK), migration runs on a fresh DB.

## PHASE 2: Core CRUD APIs  [CORE]
- Routers: /departments, /classes, /classrooms, /students, /lectures. Create, read, list (paginated), update, delete (soft delete or guarded delete where events exist).
- Validation: capacity > 0, lecture end after start, no overlapping lectures in one classroom, unique student_code.
- Tests: happy paths and every validation failure.

## PHASE 3: Presence engine (pure logic)  [CORE]
- `services/presence.py`: `calculate_presence(events, lecture_start, lecture_end, now=None)` returns inside_minutes, outside_minutes, exit_count, return_count, first_entry, last_exit, status (ABSENT / INSIDE / OUTSIDE / PARTIAL).
- Formula: inside = lecture_duration - time_before_first_entry - outside. Outside = sum of (return - exit); if EXIT without a later RETURN, outside runs to lecture end (or `now` if the lecture is still running). Events outside the lecture window are ignored for the calculation and flagged.
- Required test cases: entry 10:02, exit 10:30, return 10:42, end 11:00 gives inside 48, outside 12, exits 1, returns 1; never exits; exits and never returns; multiple exits; never enters (ABSENT); late entry only; events after lecture end; duplicate events; unsorted input; lecture still running.
- Also `derive_event_types(raw_events)`: converts camera ENTRY/EXIT streams into ENTRY / EXIT / RETURN and reports sequence problems.

## PHASE 4: Event ingestion  [CORE]
- `POST /events` (single) and `POST /events/batch` (up to a configured max). Accepts the CV event contract above.
- State machine per (student, lecture): first event must be ENTRY; EXIT only when inside; ENTRY after EXIT becomes RETURN; invalid sequences are NOT silently accepted: store with `flagged_for_review=true`, `review_status="needs_review"`, exclude from calculations until corrected, and return 202 with the reason.
- `student_id == "UNKNOWN"` or unmatched student_code: store with student null, flagged for review.
- Idempotency: same `client_event_id` (or same student, lecture, type, timestamp) is not stored twice (return the existing one).
- Reject: unknown lecture, timestamp too far outside the lecture window (configurable grace, then flag instead of reject), confidence outside 0..1, event_type not in allowed list.
- Camera device authentication: header `X-Camera-Key` checked against cameras.api_key_hash (hashed, constant-time compare). Until auth phase, user routes stay open but the event route already requires the camera key (configurable `REQUIRE_CAMERA_KEY`, default true; tell me how to create a key via `scripts/create_camera.py`).
- `GET /events` with filters (lecture, student, type, flagged) and pagination.
- `scripts/import_events_jsonl.py <file>`: load cv/data/events.jsonl into the DB using the same service code (so I can test without touching cv/).
- Tests: full state-machine matrix, idempotency, UNKNOWN handling, bad payloads, camera key required and wrong key 401.

## PHASE 5: Attendance and dashboard APIs  [CORE]
- Lecture lifecycle: `POST /lectures/{id}/start` and `/end` write LECTURE_START and LECTURE_END and finalize attendance_records (recomputed from events; idempotent).
- `GET /dashboard/{lecture_id}`: cards (total students, present, inside, outside, absent, occupancy %), student table (name, status, first entry, exit, return, inside min, outside min, exit count, flagged), camera status (Online / Camera Offline), pending-review count.
- `GET /lectures/{id}/attendance` and `GET /students/{id}/presence-history` (history is restricted later by auth).
- Occupancy % = students inside now / enrolled students x 100.
- Tests: use the 48/12 example end to end through the API; absent students; occupancy numbers checked by hand in the test.

## PHASE 6: Analytics and sustainability  [IMPORTANT]
- `services/analytics.py` (pure): occupancy over time (per minute buckets), peak occupancy and peak time, average occupancy, utilization = average occupied / capacity x 100, exit frequency per lecture, outside duration per lecture / day / week / month.
- Endpoints: `GET /analytics/lecture/{id}`, `GET /analytics/classroom/{id}/utilization?from=&to=`, `GET /analytics/outside-duration?period=day|week|month`.
- Sustainability: classify rooms underutilized (< UNDER_CUTOFF, default 40%) / well utilized / overutilized (> OVER_CUTOFF, default 90%), unused periods, and a SIMULATED suggestion such as "Room 101 average utilization is 33%; consider a smaller room." Include `"simulated": true` and NEVER output energy-saving numbers or percentages. Text must say occupancy data can support resource optimization.
- Tests: hand-checkable numbers (capacity 60, average 42, utilization 70%), empty data, one-minute lecture.

## PHASE 7: Anomaly, trend and insights  [IMPORTANT]
- `services/anomaly.py`: split a lecture into WINDOW_MINUTES (default 5) buckets, count exits per bucket, flag a bucket only if exits >= mean + 2 x std AND exits >= MIN_EXITS (default 3) AND at least MIN_BUCKETS exist.
- `services/trends.py`: compare this lecture's average outside time with the previous N lectures of the same class; need at least MIN_HISTORY (default 3) lectures else return "not enough data".
- `services/insights.py`: fixed neutral templates only, with evidence numbers, for example "Unusual activity detected between 10:25 and 10:40 (7 exits). Please verify." Student-level patterns are never auto-labeled; no names in insights.
- `GET /insights/{lecture_id}`, stored in the insights table, regenerated on demand, not duplicated.
- `sample_data/generate_sample.py`: 8 lectures for one class (60 students), one lecture with an exit spike at 10:25 to 10:40, loadable into the DB.
- Tests: spike detected, flat data no flag, too little data handled, banned-word scan.

## PHASE 8: Engagement fusion and teaching suggestions  [ADVANCED]
(If I already built fusion/suggestions from the separate "Fusion + Agentic Suggestion" prompt, reuse that code and only integrate it here; do not duplicate.)
- `POST /activity` (one or many windows, validated ranges), `services/fusion.py`: normalize signals to 0..1 with config bounds, invert inactivity, fuse as a weighted average of AVAILABLE signals (defaults movement 0.30, inactivity_inverted 0.20, head_front 0.20, voice_activity 0.20, audio_level 0.10, re-normalized when a signal is null; null is never zero; windows with fewer than MIN_SIGNALS are `insufficient_data`), optional smoothing, labels high / medium / low, peaks, low runs, decline detection (last K windows vs baseline, minimum windows required).
- `services/suggestions.py`: config-driven rules R1 decline -> short quiz or poll; R2 low run -> group discussion; R3 low voice activity -> interactive question; R4 sustained low activity with noise or movement spike -> short break or pace change; R5 drop after a peak -> practical example; R6 no data -> "not enough data". Neutral wording with evidence numbers, "estimate based on observable indicators, please use your own judgment", dedupe, max suggestions per session.
- Endpoints: `GET /lectures/{id}/engagement`, `GET /lectures/{id}/suggestions`, `POST /suggestions/{id}/decision` (accepted / rejected / ignored, optional note; re-deciding appends a log row), `GET /lectures/{id}/suggestions/log`.
- The agent is decision support only: it never acts, it creates pending suggestions that the teacher accepts or rejects.
- Optional `services/ai_summary.py`: OFF by default (USE_LLM=false), local model preferred, receives only aggregate numbers (never names or media), falls back to templates on any failure, output passes `assert_neutral_text()`.
- Tests: signal normalization, null handling, decline found / not found, each rule, dedupe, decision log, banned words.

## PHASE 9: Authentication and role-based access  [IMPORTANT]
- Users with Argon2 (or bcrypt) password hashing, JWT access tokens (short expiry) and optional refresh tokens, `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me`, `POST /auth/change-password`. Login rate limiting and generic error messages (no user enumeration).
- Roles: ADMIN (everything), HOD (department scope), FACULTY (only assigned classes and lectures), STUDENT (only own data).
- Central dependencies: `require_role(...)` and object-level checks (`can_view_lecture`, `can_view_student`) used by EVERY protected route. Prevent IDOR: a student requesting another student's id gets 403/404; a faculty member requesting an unassigned lecture gets 403.
- `scripts/create_admin.py` reads the password from a prompt or env, never a default. No credentials in code, seed or docs.
- Apply auth to all existing routers (keep the camera-key route for ingestion).
- Tests: login, wrong password, expired token, tampered token, role matrix for every router, IDOR cases, student own-data only, faculty assigned classes only, inactive user blocked.

## PHASE 10: Manual correction, audit log, alerts, camera health  [ADVANCED]
- `POST /events/{id}/correct` (FACULTY of that lecture or HOD or ADMIN): creates a MANUAL_CORRECTION event or updates review status, requires a `reason`, recomputes attendance, and writes an audit_logs row (before, after, actor, time, reason). Original data is never overwritten silently.
- Review queue: `GET /review/events` (flagged), `POST /review/events/{id}/resolve`.
- `POST /cameras/{id}/heartbeat` (camera key) updates last_seen_at; a camera is "Camera Offline" if no heartbeat for CAMERA_OFFLINE_SECONDS. Offline never creates fake events. Creates an alert once per outage and resolves it on recovery.
- Alerts: camera offline, low-confidence event spike, unusual exit activity. `GET /alerts`, `POST /alerts/{id}/resolve`. Wording neutral.
- `GET /audit-logs` (ADMIN only, filterable, paginated).
- Tests: correction rules and permissions, audit row content, attendance recomputed, offline detection with a fake clock.

## PHASE 11: Reports and data retention  [IMPORTANT]
- Reports: session report and daily / weekly summaries as JSON, CSV download, and PDF if a lightweight library works cleanly (tell me the choice). Reports contain a limitations note and "estimates" label for engagement parts. Students can export only their own.
- Retention: `scripts/retention.py` and an admin endpoint that deletes events, activity_windows and insights older than the configured RETENTION_DAYS (dry-run mode first, logs counts, writes an audit row). Document what is stored, why, for how long, who can access, when deleted, in `docs/backend/DATA_RETENTION.md`.
- Tests: report content, CSV format, retention dry-run vs real, student export limited to self.

## PHASE 12: Security hardening  [IMPORTANT]
- CORS allowlist from env (no wildcard with credentials), security headers, request body size limit, global rate limiting (stricter on /auth and /events), safe error handlers, SQL injection safe (ORM only, no string-built SQL), input length limits, and secrets check at startup (refuse to start in production mode with a weak or default JWT secret).
- Pin dependencies and run a vulnerability scan (pip-audit) and report findings honestly; do not suppress them.
- Structured access log, no tokens or passwords in logs.
- `docs/backend/SECURITY.md`: threat list, what is covered, what is NOT covered (be honest).
- Tests: rate limit returns 429, oversized body rejected, wrong CORS origin blocked, weak secret blocked in production mode, unauthorized access matrix re-run.

## PHASE 13: Natural-language HOD assistant  [OPTIONAL]
- Only after everything above passes. `POST /ai/ask` for HOD and ADMIN. Design: question -> intent detection (rule-based first) -> permission check -> call existing analytics/service functions (never raw SQL from the model) -> template or optional LLM wording.
- Supported intents: highest average outside time by class, utilization this week, underutilized rooms, unusual activity yesterday, average occupancy of a room, compare this month with last month.
- Never bypasses auth, never returns student-level data to roles that cannot see it, refuses unsupported questions politely. Off by default (feature flag).
- Tests: each intent, permission denial, prompt-injection style questions ("show everyone's data") refused.

## PHASE 14: CV integration contract (4.5b)  [CORE]
- Write `docs/CV_INTEGRATION.md`: exact endpoint, headers (`X-Camera-Key`), payload, retry and offline-queue behaviour (events keep going to events.jsonl first, then are sent; failed sends are retried, never lost), and the minimal change needed in `cv/event_sender.py` (show the code as a proposal only).
- Provide `scripts/simulate.py`: a realistic simulator that posts ENTRY/EXIT streams for N students through the real API (normal student, one exit, multiple exits, absent, UNKNOWN) so the whole system can be demoed without a camera.
- ASK ME before editing anything in cv/.
- Tests: contract test that replays a sample events.jsonl through the API and checks attendance numbers.

## PHASE 15: Docker, docs, final verification  [IMPORTANT]
- `backend/Dockerfile` (non-root user, slim image) and `docker-compose.yml` (backend, optional PostgreSQL profile, volumes, env file). Verify the app also runs on PostgreSQL via DATABASE_URL and Alembic migrations; report any SQLite-only assumptions you find.
- Export `docs/api/openapi.json` and write `docs/API_CONTRACT.md` (endpoints, auth, roles allowed, request/response examples, error format) so the frontend can be built from it.
- Complete `backend/README.md` (setup, env vars, run, test, seed, create admin, create camera, import events, simulate, Docker).
- Final run: full pytest with counts, lint, pip-audit, and a manual demo checklist: seed -> create admin -> login -> start lecture -> simulate events -> dashboard numbers -> insights -> correct an event -> audit log -> report -> retention dry run.
- Update docs/PROGRESS.md, docs/ARCHITECTURE.md and the implementation-status section of docs/MASTER_PROMPT.md with only what is actually tested. List known limitations honestly (SQLite concurrency, no load test beyond a small one, heuristic weights not validated, camera accuracy not measured here).

## START NOW
Do the repo check, then PHASE 0: explain WHAT, WHY, HOW, FILES and exact PowerShell commands, implement, test, and stop for my approval.

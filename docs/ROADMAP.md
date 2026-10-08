# SmartClass EcoSense - Build Roadmap

Rule: SIMPLE -> WORKING -> TESTED -> SECURE -> SCALABLE -> ADVANCED.
Finish Phase 0-4 first. That is the working MVP. Do not jump ahead.
Tick boxes as you finish. Keep `docs/PROGRESS.md` in sync.

Labels: CORE / IMPORTANT / ADVANCED / OPTIONAL / FUTURE

---

## Phase 0 - Setup  [CORE]
**Goal:** Tools and repo ready.
- [ ] Install Python 3.11+, Node.js, Git, VS Code
- [ ] Create GitHub repo `smartclass-ecosense`
- [ ] Create folder structure (see ARCHITECTURE.md)
- [ ] Create `README.md`, `.gitignore`, `.env.example`
- [ ] Backend virtual environment + `requirements.txt` (fastapi, uvicorn, sqlalchemy, pydantic, pytest)
- [ ] `GET /health` endpoint returns OK
**Done when:** `uvicorn app.main:app --reload` runs and /health works.

## Phase 1 - Backend + Database  [CORE]
**Goal:** Store classrooms, students, lectures, events.
- [ ] `database.py` (SQLite connection)
- [ ] `models.py` (students, classrooms, lectures, presence_events)
- [ ] `schemas.py` (input validation)
- [ ] Create/list endpoints for students, classrooms, lectures
**Done when:** you can create a classroom, students and a lecture through the API.

## Phase 2 - Presence Logic  [CORE]  (most important)
**Goal:** Turn events into inside time, outside time, exit count.
- [ ] `POST /events` (ENTRY, EXIT, RETURN, validation: no EXIT before ENTRY etc.)
- [ ] `services/presence.py` -> `calculate_presence(events, lecture_start, lecture_end)`
- [ ] `tests/test_presence.py`
  - [ ] Example: entry 10:02, exit 10:30, return 10:42, end 11:00 -> inside 48, outside 12, exits 1
  - [ ] Student never exits
  - [ ] Student exits and never returns
  - [ ] Multiple exits
  - [ ] Student never enters (absent)
**Done when:** all presence tests pass.

## Phase 3 - Simulator  [CORE]
**Goal:** Test the full system without a camera.
- [ ] `simulate.py` creates ~10 students and sends fake events
- [ ] Include: normal student, one exit, multiple exits, absent student
**Done when:** running the simulator fills the database with correct events.

## Phase 4 - Dashboard  [CORE]
**Goal:** See results in a browser.
- [ ] `GET /dashboard/{lecture_id}` returns cards + student table data
- [ ] React app: StatCards (Total, Inside, Outside, Absent, Occupancy)
- [ ] StudentTable (Name, Status, Entry, Exit, Return, Inside, Outside)
- [ ] Auto refresh every few seconds
**Done when:** run simulator -> dashboard shows correct numbers.

> MVP COMPLETE after Phase 4. Commit, tag `v0.1-mvp`, and record a short demo video.

---

## Phase 5 - Utilization + Sustainability  [IMPORTANT]
- [ ] `services/analytics.py`: occupancy %, average/peak occupancy, utilization %
- [ ] Mark rooms underutilized / well utilized / overutilized
- [ ] Utilization chart on dashboard
- [ ] Simulated "resource suggestion" (e.g. "Room 101 at 33% utilization, consider a smaller room")
- [ ] No energy-saving numbers unless measured
**Done when:** dashboard shows utilization per room with a clear label.

## Phase 6 - Login + Roles  [IMPORTANT]
- [ ] `routes/auth.py`, password hashing, JWT
- [ ] Roles: HOD and FACULTY first (STUDENT, ADMIN later)
- [ ] Faculty sees only assigned classes
- [ ] Tests: unauthorized access and role escalation are blocked
**Done when:** wrong role gets 403.

## Phase 7 - AI Insights  [IMPORTANT]
- [ ] `services/insights.py`: rule-based first
  - [ ] Outside activity higher than previous lectures
  - [ ] Many exits in the same time window
  - [ ] Occupancy trend over weeks
- [ ] Optional: LLM turns numbers into a readable summary (API key in `.env`)
- [ ] Wording always neutral: "Unusual activity detected. Please verify."
**Done when:** dashboard shows an insights panel with neutral wording.

## Phase 8 - Computer Vision  [ADVANCED]
- [ ] `cv/detector.py`: webcam frames -> person detection (OpenCV + a detection model)
- [ ] Tracking + line-crossing for ENTRY/EXIT
- [ ] Start with COUNTING only. No face recognition yet.
- [ ] Send events to the same `POST /events` (source = "camera")
- [ ] Confidence score + "Camera Offline" state
- [ ] Do not save raw video
**Done when:** walking through a line on the webcam creates an event on the dashboard.

## Phase 9 - Manual Correction + Audit Log  [ADVANCED]
- [ ] Faculty/HOD can correct an event
- [ ] `audit_logs`: original, correction, who, when, reason
- [ ] Low-confidence events flagged for review

## Phase 10 - Demo + Documentation  [CORE for competition]
- [ ] Rehearsed demo story (enter -> exit -> return -> dashboard -> insight -> utilization)
- [ ] Slides (14 slides: title, problem, existing system, solution, how it works, architecture,
      AI, privacy and security, sustainability, demo, innovation, future scope, business, conclusion)
- [ ] Honest limitations slide (what is simulated, what is tested)
- [ ] README with setup + screenshots

---

## Later (do not start until the above works)
- [ADVANCED] Identity association (QR/RFID or approved face recognition), PostgreSQL, Docker
- [OPTIONAL] Natural-language HOD assistant (must respect roles), n8n notifications, reports export
- [FUTURE] Mobile app (Kotlin), edge AI, IoT/smart lighting/HVAC, multi-classroom, multi-campus, SaaS

## Build order summary
- **Build this first:** Phase 0, 1, 2
- **Build this next:** Phase 3, 4, then 5, 6, 7
- **Build this later:** Phase 8, 9, then identity, edge AI, IoT, mobile

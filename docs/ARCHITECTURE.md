# SmartClass EcoSense - Architecture

Keep this file updated. If you change the architecture, record why at the bottom (Decision Log).

## 1. High-level flow

```
Camera / Webcam / Simulator
        |
        v
Computer Vision (LATER)  -> person detection -> tracking
        |
        v
Event Engine (ENTRY / EXIT / RETURN)
        |
        v
Backend API (FastAPI)  <-- auth, validation
        |
        v
Database (SQLite for MVP, PostgreSQL later)
        |
        +--> Analytics (occupancy, utilization)
        +--> Insights (rule-based, optional LLM summary)
        |
        v
Dashboard (React)
```

MVP uses the **simulator** instead of the camera. The rest of the flow stays the same,
so the camera can be plugged in later without changing the backend.

Three layers must stay separate:
1. PERSON DETECTION (is a person there?)
2. PERSON IDENTITY (who is it? replaceable: QR, RFID, approved face recognition)
3. EVENT TRACKING (entry, exit, return, durations)

## 2. Folder structure

```
smartclass-ecosense/
├── AGENTS.md
├── README.md
├── .gitignore
├── .env.example
├── docs/
│   ├── PROJECT_CONTEXT.md
│   ├── ROADMAP.md
│   ├── ARCHITECTURE.md
│   └── PROGRESS.md
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, includes routers
│   │   ├── database.py        # DB engine and session
│   │   ├── models.py          # Database tables
│   │   ├── schemas.py         # Pydantic request/response models
│   │   ├── routes/
│   │   │   ├── students.py
│   │   │   ├── classrooms.py
│   │   │   ├── lectures.py
│   │   │   ├── events.py      # POST /events
│   │   │   ├── dashboard.py   # GET /dashboard/{lecture_id}
│   │   │   └── auth.py        # Phase 6
│   │   ├── services/
│   │   │   ├── presence.py    # CORE: duration calculation
│   │   │   ├── analytics.py   # occupancy, utilization
│   │   │   └── insights.py    # rule-based insights, optional LLM
│   │   └── cv/
│   │       └── detector.py    # Phase 8
│   ├── tests/
│   │   ├── test_presence.py
│   │   └── test_analytics.py
│   ├── simulate.py            # fake event generator
│   └── requirements.txt
└── frontend/
    └── src/
        ├── App.jsx
        ├── components/        # StatCards, StudentTable, UtilizationChart, InsightsPanel
        └── services/api.js
```

## 3. Database tables (MVP)

**students**: id, roll_no, name, class_name

**classrooms**: id, name (e.g. "Room 101"), capacity

**lectures**: id, classroom_id, class_name, subject, teacher_name, start_time, end_time

**presence_events**: id, student_id, classroom_id, lecture_id, event_type, timestamp, confidence, source, created_at
- event_type: ENTRY, EXIT, RETURN, LECTURE_START, LECTURE_END, MANUAL_CORRECTION
- source: "simulator", "camera", "manual"
- confidence: 0.0 to 1.0 (simulator uses 1.0)

Later: users (roles), audit_logs, alerts, cameras, system_settings.

## 4. Event rules (validation)
- First event for a student in a lecture must be ENTRY.
- EXIT is allowed only when the student is currently inside.
- RETURN is allowed only after an EXIT.
- Timestamps must be inside the lecture window (or flagged for review).
- Invalid sequences are rejected or flagged, never silently accepted.

## 5. Presence calculation (core logic)

Given the events of one student in one lecture:
- inside_minutes = lecture_duration - time_before_entry - outside_minutes
- outside_minutes = sum of (RETURN time - EXIT time). If the student never returns, outside runs until lecture end.
- exit_count = number of EXIT events
- return_count = number of RETURN events
- status: ABSENT (no ENTRY), INSIDE, OUTSIDE (currently exited)

Example: lecture 10:00-11:00, ENTRY 10:02, EXIT 10:30, RETURN 10:42
-> inside 48, outside 12, exits 1, returns 1.

Occupancy % = students inside now / students enrolled x 100
Utilization % = average occupied / room capacity x 100

## 6. API endpoints (MVP)

| Method | Path | Purpose |
|---|---|---|
| GET | /health | Check server |
| POST / GET | /students | Create / list students |
| POST / GET | /classrooms | Create / list classrooms |
| POST / GET | /lectures | Create / list lectures |
| POST | /events | Record ENTRY / EXIT / RETURN |
| GET | /dashboard/{lecture_id} | Cards + student table data |
| GET | /analytics/utilization | Room utilization (Phase 5) |
| GET | /insights/{lecture_id} | Insights (Phase 7) |
| POST | /auth/login | Login (Phase 6) |
| GET | /reports/lectures/{id} | Scoped session report as JSON or CSV (Phase 11) |
| GET | /reports/summaries | Scoped daily/weekly summaries as JSON or CSV (Phase 11) |
| POST | /admin/retention/run | ADMIN-only 90-day retention preview/deletion (Phase 11) |
| POST | /ai/ask | Optional, feature-flagged aggregate HOD assistant (Phase 13) |

## 7. Roles (Phase 6)
ADMIN (everything), HOD (department), FACULTY (assigned classes only), STUDENT (own data only).
Check the role on every protected endpoint. Never trust the frontend to hide data.
Phase 9 uses an explicit nullable, unique `users.student_id` foreign key for
Student ownership. Existing users remain unmapped, and a missing mapping is
denied with `403`; no identity is inferred from email or name. HOD department
scope is resolved from the department on its linked `faculty` profile. A
missing HOD/faculty scope record is denied rather than widened.

## 8. Privacy and security rules in the design
- No raw video stored. Only events.
- Secrets in `.env`, never in code or Git.
- Input validated with Pydantic.
- Audit log for every manual correction and resolution, including actor, time, before/after state and reason.
- AI insights use neutral wording and never name a reason or punishment.
Phase 10 stores corrections as linked append-only events. Review resolution
does not change the original event or silently include it in calculations.
Phase 11 retention deletes events, activity windows, and insights older than
90 days by default; attendance records and audit logs are not in this job's
scope. The retention API defaults to a dry-run.

## 9. Failure handling
- Camera offline -> show "Camera Offline", create no fake events.
- Low confidence -> flag for manual review.
- Database error -> return a clear error, do not crash silently.

## 10. Decision Log
| Date | Decision | Reason |
|---|---|---|
| (start) | SQLite for MVP, PostgreSQL later | Simpler setup for a beginner |
| (start) | Simulator before camera | Test backend and dashboard first |
| (start) | Rule-based insights before LLM | Normal logic where AI is not needed |
| 2026-10-25 | Argon2id passwords, short-lived signed JWTs, explicit object-level RBAC | Protect backend APIs and prevent cross-student or cross-class data access |
| 2026-10-25 | Student-user mapping is nullable and unique; no automatic identity matching | Preserve privacy and prevent accidental account-to-student linking |
| 2026-10-25 | Corrections are linked `MANUAL_CORRECTION` events; review rows are never overwritten | Preserve provenance and recompute attendance from auditable effective events |
| 2026-10-25 | Phase 11 exports JSON/CSV and uses a 90-day, dry-run-first retention policy | Provide usable reports without a new PDF dependency and preview permanent deletion |
| 2026-10-25 | Phase 13 HOD questions use deterministic intents, existing analytics, role-scoped aggregates, and an off-by-default feature flag | Provide privacy-bounded assistance without LLM-generated queries or unsupported claims |

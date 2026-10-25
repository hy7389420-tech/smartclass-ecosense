# SmartClass EcoSense Database (MVP foundation)

SQLite is the development database. `DATABASE_URL` can point SQLAlchemy at a
PostgreSQL database later. Alembic owns schema changes; do not rely on
`Base.metadata.create_all()` to update an existing database.

All event and lecture timestamps use timezone-aware SQLAlchemy `DateTime`
columns. Application services must normalize timestamps to UTC before storing
them. The demo seed interprets its 10:00-11:00 schedule in `LOCAL_TIMEZONE`
(default `Asia/Kolkata`) and converts it to UTC.

## Tables

| Table | Purpose and main relationships |
|---|---|
| `departments` | Department directory; parent of classes and faculty. |
| `classes` | Class name, section, year, and owning department. |
| `classrooms` | Room name and positive seating capacity. |
| `students` | Unique student code and roll number within a class. |
| `users` | Unique email, Argon2 password hash, role, active status, optional unique `student_id` mapping, and token version for access-token revocation. |
| `faculty` | Faculty profile linked to a user and department. |
| `faculty_class_assignments` | Many-to-many assignments between faculty and classes. |
| `lectures` | Class, classroom, optional faculty, subject, UTC schedule, and status. |
| `cameras` | Camera identity and API-key hash for a classroom. |
| `presence_events` | Entry/exit/return, lecture and manual-correction events; corrections retain their source event ID and effective event type. |
| `attendance_records` | Per-student, per-lecture calculated presence totals. |
| `activity_windows` | Aggregate numeric activity features for a lecture window. |
| `insights` | Neutral lecture-level insight text and JSON evidence. |
| `suggestions` | Lecture-level teaching suggestions and status. |
| `suggestion_decisions` | Append-only teacher decisions linked to a suggestion and user. |
| `audit_logs` | Actor, action, entity, before/after JSON, reason, and timestamp; used for corrections and operational resolutions. |
| `alerts` | Camera/classroom/lecture alerts and resolution timestamp; one unresolved alert per incident key is created by the service. |
| `system_settings` | Key/value settings. |

## Integrity and indexes

Foreign keys are enabled for every SQLite connection. The schema enforces
unique emails, student codes, classroom names, faculty/user links, assignment
pairs, one user per mapped student (multiple unmapped `NULL` values are
allowed), lecture/student attendance pairs, and per-lecture client event IDs
(multiple `NULL` client IDs remain valid). It also validates room capacity,
lecture/window time order, presence confidence, and constrained status values.

Presence events have indexes on `(lecture_id, timestamp_utc)` and
`(lecture_id, student_id)` for the event stream and student history queries.
Manual corrections are appended as `MANUAL_CORRECTION` events with
`correction_of_event_id` pointing to the reviewed event and
`correction_event_type` describing the effective ENTRY/EXIT/RETURN used in
attendance calculations. Original event data remains intact.
Service-level rules such as overlapping lecture prevention and event sequence
validation belong in later service/API phases.

## Create schema and seed demo records

From the repository root in PowerShell:

```powershell
Set-Location backend
.\.venv-backend\Scripts\python.exe -m alembic upgrade head
.\.venv-backend\Scripts\python.exe -m scripts.seed_demo
```

The seed is idempotent, creates one demo department, one B.Tech class, a
60-seat Demo Room 101, five students (`STUDENT_A` through `STUDENT_E`, matching
the CV demo mapping), and one scheduled lecture for today from 10:00 to 11:00
in `LOCAL_TIMEZONE`. It does not create accounts or passwords.

The Phase 9 migration leaves every existing user with `student_id=NULL` and
sets `token_version=0`. Map student accounts only through an explicit,
verified student ID; the migration never matches email or name. HOD accounts
derive their department scope from a corresponding `faculty` profile.

## Retention

`RETENTION_DAYS` defaults to 90. The Phase 11 retention job deletes old
`presence_events`, `activity_windows`, and `insights` rows by their event
timestamp, window end, and creation timestamp respectively. A correction link
from a retained correction to an expired source event is detached before
deletion so database foreign keys remain valid. Attendance records and audit
logs are intentionally outside this job's deletion scope and are retained;
see [DATA_RETENTION.md](./backend/DATA_RETENTION.md) for the full policy and
current limitations.

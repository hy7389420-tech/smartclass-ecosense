# SmartClass EcoSense API Contract

Backend API is served by FastAPI. Interactive request/response schemas are also
available at `/docs`. Except for `/health`, `/ready`, and `/auth/login`,
application endpoints require a JWT bearer token. Camera event ingestion uses
its existing `X-Camera-Key` authentication; `GET /events` requires a user token.
The generated schema is available at [openapi.json](./api/openapi.json).

## Common behavior

- List endpoints accept `limit` (default `20`, range `1-100`) and `offset`
  (default `0`, minimum `0`).
- List responses have `items`, `total`, `limit`, and `offset`.
- Create returns `201`; reads and updates return `200`; successful deletes
  return `204`.
- Missing records return `404`. Duplicate/foreign-key/delete-guard conflicts
  return `409`. Invalid payloads or query parameters return `422`.
- Errors use `{ "error": { "code": "...", "message": "..." } }`. Internal
  database details are not returned.
- Request bodies larger than `MAX_REQUEST_BODY_BYTES` return `413`.
  Rate-limited requests return `429` with a `Retry-After` header. HTTP and
  unexpected server errors use the same safe error envelope.
- Delete is guarded by database foreign keys: records referenced by other data
  cannot be removed.
- Lecture timestamps accept ISO 8601. A timestamp without an offset is treated
  as `LOCAL_TIMEZONE` (default `Asia/Kolkata`), converted to UTC, and returned
  with a UTC offset.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/auth/login` | Verify credentials and return a short-lived JWT |
| `GET` | `/auth/me` | Read the authenticated account |
| `POST` | `/auth/change-password` | Change password and revoke existing access tokens |
| `POST` | `/suggestions/{id}/decision` | Append an authenticated teacher decision |
| `GET` | `/lectures/{lecture_id}/suggestions/log` | Read the scoped decision history |
| `POST` | `/events/{id}/correct` | Correct a review event and recompute attendance |
| `GET` | `/review/events` | List events awaiting manual review |
| `POST` | `/review/events/{id}/resolve` | Resolve a review item without including it in calculations |
| `POST` | `/cameras/{id}/heartbeat` | Update camera health using its camera key |
| `GET` | `/alerts` | List role-scoped operational alerts |
| `POST` | `/alerts/{id}/resolve` | Resolve an alert with a reason |
| `GET` | `/audit-logs` | Filterable, paginated audit history (ADMIN only) |
| `GET` | `/reports/lectures/{lecture_id}` | Session report JSON or CSV; students receive only their own record |
| `GET` | `/reports/summaries?period=daily|weekly&date=YYYY-MM-DD` | Scoped daily/weekly summaries as JSON or CSV |
| `POST` | `/admin/retention/run` | ADMIN-only retention preview or deletion; preview is default |
| `POST` | `/ai/ask` | Optional, feature-flagged aggregate HOD assistant (ADMIN/HOD only) |

| Resource | Create | List | Read one | Update | Delete |
|---|---|---|---|---|---|
| Departments | `POST /departments` | `GET /departments` | `GET /departments/{id}` | `PUT /departments/{id}` | `DELETE /departments/{id}` |
| Classes | `POST /classes` | `GET /classes` | `GET /classes/{id}` | `PUT /classes/{id}` | `DELETE /classes/{id}` |
| Classrooms | `POST /classrooms` | `GET /classrooms` | `GET /classrooms/{id}` | `PUT /classrooms/{id}` | `DELETE /classrooms/{id}` |
| Students | `POST /students` | `GET /students` | `GET /students/{id}` | `PUT /students/{id}` | `DELETE /students/{id}` |
| Lectures | `POST /lectures` | `GET /lectures` | `GET /lectures/{id}` | `PUT /lectures/{id}` | `DELETE /lectures/{id}` |
| Events | `POST /events` and `POST /events/batch` | `GET /events` | - | - | - |
| Analytics | - | `GET /analytics/lecture/{id}`; `GET /analytics/classroom/{id}/utilization`; `GET /analytics/outside-duration` | - | - | - |
| Insights | - | `GET /insights/{lecture_id}` | - | - | - |
| Activity | `POST /activity` | - | - | - | - |
| Engagement | - | `GET /lectures/{id}/engagement`; `GET /lectures/{id}/suggestions` | - | - | - |
| HOD assistant | `POST /ai/ask` | - | - | - | - |

### Optional HOD assistant

The endpoint is disabled unless `AI_ASSISTANT_ENABLED=true`. It accepts
`{"question":"Which rooms are underutilized?"}` and returns a response with
`status` (`answered` or `refused`), a supported `intent` (or `null`), and a
plain-language `answer`. Question length is limited to 500 characters.

Example response:

```json
{
  "status": "answered",
  "intent": "underutilized_rooms",
  "answer": "Rooms below the configured utilization threshold: Room 101: 18.0%. This is occupancy-based and does not claim energy savings."
}
```

Supported aggregate intents:

- Highest average outside time by class (all completed attendance history).
- Room utilization for the current local calendar week.
- Underutilized rooms based on completed lecture history and the configured
  utilization cutoff.
- Unusual exit activity for yesterday using the configured exit-spike rules.
- Average occupancy for a named room across completed lectures.
- Current month versus previous month average occupancy, utilization, and
  outside time.

The feature uses deterministic intent matching and existing analytics logic;
it does not call an LLM or execute generated SQL. It is restricted to ADMIN and
HOD roles, and every data query is limited to the user's permitted class scope.
Student-level data requests and unsupported questions receive a polite
`refused` response. It returns aggregates only and does not claim that
occupancy estimates are measured energy savings.
When disabled, the endpoint returns `503` with error code
`AI_ASSISTANT_DISABLED`.

Additional attendance endpoints:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/lectures/{id}/start` | Start a scheduled lecture |
| `POST` | `/lectures/{id}/end` | End a live lecture and finalize attendance |
| `GET` | `/lectures/{id}/attendance` | Read live or finalized student attendance |
| `GET` | `/dashboard/{lecture_id}` | Read attendance cards, student table and camera/review status |
| `GET` | `/students/{id}/presence-history` | Read that student's finalized lecture attendance |

### Reports and data retention

Reports are available only to authenticated users. ADMIN can access all
lectures; HOD and FACULTY are restricted to their class/department assignments.
STUDENT exports contain only the mapped student's attendance record and do not
include class totals or engagement estimates.

Session reports are available as JSON or CSV:

```text
GET /reports/lectures/{lecture_id}?format=json
GET /reports/lectures/{lecture_id}?format=csv
```

Daily and weekly summaries use the configured `LOCAL_TIMEZONE`; a week runs
Monday through Sunday. If omitted, `date` defaults to today in that timezone.
CSV is the default spreadsheet-friendly export only when `format=csv` is set.
PDF is not currently provided because no PDF library is part of the backend
dependencies. Session report engagement is labeled
`estimate based on observable indicators`; every report includes a
limitations note.

Retention uses `RETENTION_DAYS` (default `90`). It purges expired presence
events, activity windows, and insights. A retained correction whose source
event expires has its source link cleared; counts are reported in the audit
entry. The endpoint defaults to dry-run and requires an explicit `dry_run:
false` to delete:

```http
POST /admin/retention/run
Authorization: Bearer <admin-token>
Content-Type: application/json
```

```json
{"dry_run": true}
```

The response gives `cutoff_at`, candidate counts, delete counts, and
correction-link count. Attendance records and audit logs are not deleted by
this retention task; see [data-retention policy](./backend/DATA_RETENTION.md).

Create and update use the same complete resource body (`PUT` replaces the
editable fields):

```json
{
  "department_id": 1,
  "name": "B.Tech",
  "section": "A",
  "year": 1
}
```

Classroom capacity must be positive. Student codes are unique. Lecture end
must be after lecture start, and overlapping lectures in the same classroom
are rejected. Deleting records referenced by classes, students, lectures, or
events is rejected with `409 CONFLICT`.

## Event ingestion

Every `POST /events` and `POST /events/batch` request requires the
`X-Camera-Key` header by default. Create the key for an existing classroom
using the instructions in [backend/README.md](../backend/README.md). The API
stores only the SHA-256 hash; the generated key is printed once. Set
`REQUIRE_CAMERA_KEY=false` only for isolated local development.

`POST /events` accepts camera `ENTRY` and `EXIT` events. Timestamps must be
ISO 8601 with a timezone; values without an offset are treated as
`LOCAL_TIMEZONE` (default `Asia/Kolkata`) and normalized to UTC. Extra payload
fields are ignored so the existing CV event contract remains compatible.
Example:

```json
{
  "student_id": "STUDENT_A",
  "classroom_id": 1,
  "lecture_id": 1,
  "event_type": "ENTRY",
  "timestamp": "2030-01-01T10:02:00Z",
  "confidence": 0.92,
  "source": "camera",
  "flagged_for_review": false,
  "presence_confirmed": true,
  "client_event_id": "optional-stable-event-id"
}
```

The backend derives `RETURN` when an `ENTRY` follows a valid `EXIT` for the
same student and lecture. Unknown students, client-flagged events,
unconfirmed presence, low confidence, timestamps within the configured grace
period but outside lecture hours, and invalid sequences are stored with
`flagged_for_review=true` and `review_status="needs_review"`; flagged events
are excluded from presence calculations. Events outside the grace window,
unknown lectures, and classroom/lecture mismatches are rejected.

| Outcome | Status |
|---|---:|
| New valid event | `201` |
| Event saved for review | `202` |
| Idempotent retry (same client ID or student/type/timestamp) | `200` |
| Missing/invalid camera key | `401` |
| Camera assigned to a different classroom | `403` |
| Unknown lecture | `404` |
| Invalid event, classroom mismatch, or batch size | `422` |

`POST /events/batch` accepts a non-empty JSON array with at most
`MAX_EVENT_BATCH_SIZE` items (default `100`, configurable up to `1000`). The
whole request is one transaction: if any item is rejected, none of the batch
is stored. Its response includes per-event results and accepted, flagged, and
duplicate counts.

`GET /events` supports `lecture_id`, `student_id`, `event_type`, and
`flagged_for_review` filters, plus the common `limit` and `offset` pagination
parameters. Event timestamps are listed in ascending order. Results are
restricted to the authenticated user's role and scope; a student can only query
their own events.

## Authentication and role scope

Send `Authorization: Bearer <access_token>` to protected endpoints. Login uses
JSON with `email` and `password`; invalid email/password pairs return the same
generic `401` response. Access tokens expire after 15 minutes by default.
Login attempts are rate-limited in-process. Passwords use Argon2id. A password
change increments the user's token version, so previously issued access tokens
stop working immediately.

| Role | Read scope | Write scope |
|---|---|---|
| `ADMIN` | All backend resources | Catalog administration |
| `HOD` | Its mapped department and classes | No catalog writes |
| `FACULTY` | Assigned classes/lectures and their students | Lecture lifecycle and activity windows for assigned lectures |
| `STUDENT` | Own student record, presence history and events | No writes |

A `STUDENT` account without a `users.student_id` mapping receives `403` and
cannot access student data. Mapping is explicit; existing users remain
unmapped after migration and no matching by email/name is attempted. HOD scope
uses the department on the user's `faculty` profile; an HOD account without
that profile is denied rather than given broader access.

Create an initial administrator from the `backend` directory with
`python -m scripts.create_admin --email admin@example.edu`. The script prompts
for a password (12+ characters); alternatively provide `ADMIN_PASSWORD` via
the environment. There is no default credential. Set `JWT_SECRET_KEY` to a
random secret of at least 32 characters in production; in local development an
ephemeral secret is generated when the setting is blank.

## Lecture lifecycle, attendance and dashboard

`POST /lectures/{id}/start` changes a scheduled lecture to `live` and records
one `LECTURE_START` event. Repeating the request while it is live is
idempotent. Starting a completed or cancelled lecture, or ending a lecture
that is not live, returns `409`. A new lecture must be created as
`scheduled`; use the lifecycle endpoints instead of CRUD updates to mark it
live or completed.

`POST /lectures/{id}/end` records `LECTURE_END`, marks the lecture completed,
and recomputes one `attendance_records` row for each active student enrolled
in the lecture's class. Repeating the end request recomputes the rows from
events without duplicating the lifecycle event. Flagged or unconfirmed events
are excluded. Attendance includes `ABSENT`, `INSIDE`, or `OUTSIDE` status,
first entry/last exit, inside/outside minutes, and exit/return counts.

`GET /lectures/{id}/attendance` returns the same attendance summary and records;
while the lecture is running, it calculates a current snapshot, and after
completion it returns the finalized records. `GET /students/{id}/presence-history`
lists that student's finalized records, newest lecture first.

`GET /dashboard/{lecture_id}` returns cards for total enrolled, present,
inside, outside, absent, and occupancy percentage, plus the student table,
camera status, and pending-review event count. Occupancy is
`inside / active enrolled students * 100`; when there are no enrolled students
it is `0`. Camera status is `Online` only when a registered camera has sent
activity within `CAMERA_OFFLINE_SECONDS` (default `120`); otherwise it is
`Camera Offline`. Camera health is checked when alerts are requested or a
heartbeat arrives; there is no background scheduler.

Attendance durations are calculated only from observed presence after the
first entry. For example, a 10:00-11:00 lecture with entry at 10:02, exit at
10:30 and return at 10:42 yields 46 inside minutes and 12 outside minutes.

## Analytics and sustainability

- `GET /analytics/lecture/{id}` returns per-minute time-weighted occupancy,
  average and peak occupancy, peak time, utilization, valid exit count,
  outside minutes, and zero-occupancy intervals. Flagged/unconfirmed events
  and events for students not actively enrolled in the lecture's class are
  excluded. Events are integrated only within the scheduled lecture window.
  The lecture must be completed; an active or scheduled lecture returns `409`
  rather than reporting future scheduled minutes as empty occupancy.
- `GET /analytics/classroom/{id}/utilization?from=YYYY-MM-DD&to=YYYY-MM-DD`
  aggregates completed lectures, optionally selecting lectures by their
  scheduled start date in UTC. Average occupancy is weighted by lecture
  duration; utilization is average occupancy divided by classroom capacity.
  The response includes peak data, valid exit count, zero-occupancy intervals
  within scheduled lecture time, and a neutral resource-planning suggestion.
- `GET /analytics/outside-duration?period=day|week|month` aggregates finalized
  outside minutes from completed lectures, grouped by scheduled lecture start
  date in UTC. Week buckets start Monday. Outside duration is summed across
  students; `lecture_count` counts distinct lectures in each bucket.

Utilization labels are `underutilized` below
`UNDERUTILIZED_CUTOFF_PERCENT` (default `40`), `well_utilized` between and
including the cutoffs, and `overutilized` above
`OVERUTILIZED_CUTOFF_PERCENT` (default `90`). If no completed lecture data is
available, the label is `no_data`, not `underutilized`. The two cutoff values
must be within `0-100`, and the overutilized cutoff must be greater than the
underutilized cutoff.

Utilization suggestions are explicitly simulated and include
`"simulated": true`; they do not estimate energy or cost savings. The text
states that occupancy data can support resource optimization. Zero-occupancy
intervals only describe observed gaps inside scheduled completed lectures;
they do not infer that an unscheduled room was physically unused.

## Anomaly, trend and insights

`GET /insights/{lecture_id}` is available only for a completed lecture. Each
request recomputes and replaces that lecture's stored insight rows, so repeated
requests do not accumulate duplicates. The response is a JSON array containing
`id`, `lecture_id`, `kind`, neutral `text`, numeric `evidence_json`, and
`created_at`. Exit anomalies count valid confirmed exits in
`INSIGHT_WINDOW_MINUTES` buckets (default `5`) and flag only buckets meeting the
mean-plus-two-standard-deviations and minimum-exit thresholds. Trend comparison
uses prior completed lectures of the same class; fewer than
`INSIGHT_MIN_HISTORY` (default `3`) usable lectures yields a "not enough
historical data" insight. Generated text contains aggregate numeric evidence
only and never includes student names or claims why someone left.

Thresholds are configurable with `INSIGHT_WINDOW_MINUTES`,
`INSIGHT_MIN_EXITS` (default `3`), `INSIGHT_MIN_BUCKETS` (default `3`),
`INSIGHT_MIN_HISTORY` (default `3`), and `INSIGHT_HISTORY_LECTURES`
(default `5`).

## Activity windows, engagement estimates and teaching suggestions

`POST /activity` accepts one numeric activity window or an array of windows.
Each window identifies a lecture and has a start/end timestamp, optional
movement, inactivity, front-facing, audio-level and voice-activity features,
and a source label. Windows must be 1-300 seconds by default, fit wholly inside
a live or completed lecture, and not overlap another window for that lecture.
Allowed sources are `camera+mic`, `simulated`, and `manual`.
The maximum batch size is `ACTIVITY_MAX_BATCH_SIZE` (default `100`). Repeating
identical data for the same lecture/window start is idempotent; different data
for an existing start conflicts. A bad batch is rolled back in full. Missing
signals remain null. The schema has no raw video, image, audio or transcript
fields, and stores only numeric aggregate features.

Example single-window request:

```json
{
  "lecture_id": 12,
  "window_start": "2030-01-01T10:00:00+05:30",
  "window_end": "2030-01-01T10:01:00+05:30",
  "movement_level": 0.32,
  "inactivity_seconds": 18,
  "front_facing_ratio": 0.76,
  "audio_level_db_mean": -42.5,
  "voice_activity_ratio": 0.21,
  "source": "camera+mic"
}
```

The response includes `stored_count`, `duplicate_count`, and the stored
`windows`. New data and exact retries return `200`; missing lecture returns
`404`; a different retry or overlapping window returns `409`; invalid values
or oversized/empty batches return `422`.

`GET /lectures/{id}/engagement` returns per-window class-level estimates,
labels (`high`, `medium`, `low`, or `insufficient_data`), available-signal
counts, the average estimate, peaks, low runs and decline evidence. The
response includes the limitation note `"estimate based on observable
indicators"`. Each available signal is normalized and its configured weight
renormalized across available signals; a window with fewer than
`ACTIVITY_MIN_SIGNALS` (default `2`) is marked `insufficient_data`. Inactivity
is inverted as a ratio of the window duration. The default weights are
movement `0.30`, inactivity `0.20`, front-facing `0.20`, voice activity
`0.20`, and audio level `0.10`. No smoothing is applied in this version.
Response metrics also include available and insufficient window counts,
aggregate voice activity, maximum movement indicator, average audio level,
and whether an earlier peak dropped before the latest configured windows.

`GET /lectures/{id}/suggestions` generates and stores deduplicated pending
suggestions for rules R1-R6. These are teacher decision support only: they do
not take action, rank students, or make claims about learning or reasons for
behavior. All suggestion text is checked by the shared neutral-text guard.
Signal bounds, weights, label cutoffs, decline windows, rule thresholds and
suggestion limits are configurable with `ACTIVITY_*` settings; see
`backend/.env.example`.

Suggestion rows contain `rule_id`, `title`, neutral `text`, numeric
`evidence_json`, `severity`, `status` (initially `pending`), and `created_at`.
Repeated reads do not create another row for the same rule and lecture.

`POST /suggestions/{id}/decision` accepts `accepted`, `rejected`, or `ignored`
and an optional note (maximum 1000 characters). Only ADMIN or a FACULTY member
assigned to the suggestion's lecture can decide. Each decision appends a
`suggestion_decisions` row with the authenticated actor; changing a prior
decision adds another history row and updates the current suggestion status.
The decision-history endpoint is limited to ADMIN, HOD, or assigned FACULTY
members for that lecture. Student accounts cannot read or decide class-level
suggestions.

## Manual review, corrections, alerts and camera health

`GET /review/events` lists flagged events with `review_status="needs_review"`,
scoped to the caller's department/classes. Faculty assigned to a lecture,
department HOD, or ADMIN can correct an event with
`POST /events/{id}/correct`. The request requires a reason and an event type
(`ENTRY` or `EXIT`), timestamp, and student ID when the original event has no
known student. The backend checks the lecture time, class membership, role
scope, and event sequence. It marks the review item resolved, appends a
`MANUAL_CORRECTION` event with the effective `correction_event_type`, stores
before/after snapshots in `audit_logs`, and recomputes attendance. The original
event data is not overwritten. A correction that does not fit the event
sequence or lecture roster is rejected. A review item can instead be resolved
without accepting it through `POST /review/events/{id}/resolve`; the original
flag remains, so it stays excluded from calculations.

`POST /cameras/{id}/heartbeat` requires `X-Camera-Key`. A heartbeat marks the
matching camera online and resolves its open offline alert. `GET /alerts`
refreshes camera status and creates one open alert per outage, plus neutral
low-confidence and unusual-exit spike alerts once their configured thresholds
are reached. Offline state never creates a presence event. Alert reads and
resolution are scoped to ADMIN, HOD department, or assigned Faculty; resolving
requires a reason. `GET /audit-logs` is ADMIN-only and accepts `entity_type`,
`actor_user_id`, `limit`, and `offset`.

Phase 10 thresholds are configurable with `CAMERA_OFFLINE_SECONDS`,
`LOW_CONFIDENCE_ALERT_WINDOW_MINUTES`, `LOW_CONFIDENCE_ALERT_MIN_EVENTS`,
`UNUSUAL_EXIT_ALERT_WINDOW_MINUTES`, and `UNUSUAL_EXIT_ALERT_MIN_EVENTS`.

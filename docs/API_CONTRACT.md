# SmartClass EcoSense API Contract

Backend API is served by FastAPI. Interactive request/response schemas are also
available at `/docs`. Current CRUD endpoints are unauthenticated; authentication
and role checks are a later phase and must be added before deployment. Event
ingestion is protected separately with a camera API key.
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
- Delete is guarded by database foreign keys: records referenced by other data
  cannot be removed.
- Lecture timestamps accept ISO 8601. A timestamp without an offset is treated
  as `LOCAL_TIMEZONE` (default `Asia/Kolkata`), converted to UTC, and returned
  with a UTC offset.

## Endpoints

| Resource | Create | List | Read one | Update | Delete |
|---|---|---|---|---|---|
| Departments | `POST /departments` | `GET /departments` | `GET /departments/{id}` | `PUT /departments/{id}` | `DELETE /departments/{id}` |
| Classes | `POST /classes` | `GET /classes` | `GET /classes/{id}` | `PUT /classes/{id}` | `DELETE /classes/{id}` |
| Classrooms | `POST /classrooms` | `GET /classrooms` | `GET /classrooms/{id}` | `PUT /classrooms/{id}` | `DELETE /classrooms/{id}` |
| Students | `POST /students` | `GET /students` | `GET /students/{id}` | `PUT /students/{id}` | `DELETE /students/{id}` |
| Lectures | `POST /lectures` | `GET /lectures` | `GET /lectures/{id}` | `PUT /lectures/{id}` | `DELETE /lectures/{id}` |
| Events | `POST /events` and `POST /events/batch` | `GET /events` | - | - | - |
| Analytics | - | `GET /analytics/lecture/{id}`; `GET /analytics/classroom/{id}/utilization`; `GET /analytics/outside-duration` | - | - | - |

Additional attendance endpoints:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/lectures/{id}/start` | Start a scheduled lecture |
| `POST` | `/lectures/{id}/end` | End a live lecture and finalize attendance |
| `GET` | `/lectures/{id}/attendance` | Read live or finalized student attendance |
| `GET` | `/dashboard/{lecture_id}` | Read attendance cards, student table and camera/review status |
| `GET` | `/students/{id}/presence-history` | Read that student's finalized lecture attendance |

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
parameters. Event timestamps are listed in ascending order.

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
it is `0`. Camera status is `Online` only when a registered camera has
successfully submitted an event within `CAMERA_ONLINE_WINDOW_SECONDS` (default
`120`); otherwise it is `Camera Offline`. This is an event-recency signal, not
a separate hardware health check.

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

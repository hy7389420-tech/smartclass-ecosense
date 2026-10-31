# CV-to-Backend Event Integration

This document defines the backend contract for CV Step 4.5b. The sender keeps
`cv/data/events.jsonl` as the durable archive and dispatches queued records to
the backend. The implementation has passed automated tests and a controlled
local API delivery test; it is not committed. Physical camera validation
remains pending.

## Endpoint and authentication

Send a single event to `POST /events`, or send an ordered list to
`POST /events/batch`.

Required request header:

```http
X-Camera-Key: <registered camera API key>
Content-Type: application/json
```

Create a camera key for the target classroom with
`python -m scripts.create_camera`. The database stores only its hash. Never put
the API key in the event payload, source code, JSONL file, or logs. The camera
must belong to the same classroom as the lecture.

From the repository root, copy `.env.example` to `.env`, then set
`ECOSENSE_CAMERA_KEY`, `CLASSROOM_ID`, and `LECTURE_ID`. The IDs must be
positive numeric IDs for an existing classroom and lecture. `API_BASE_URL`
defaults to `http://127.0.0.1:8000`.

## Event payload

```json
{
  "student_id": "STUDENT_A",
  "classroom_id": 1,
  "lecture_id": 12,
  "event_type": "ENTRY",
  "timestamp": "2026-10-25T10:02:00+05:30",
  "confidence": 0.92,
  "source": "camera",
  "flagged_for_review": false,
  "presence_confirmed": true,
  "client_event_id": "d74cf3a695e54487b4684604967ad6f1"
}
```

`event_type` is `ENTRY` or `EXIT`; the backend derives `RETURN` when an
`ENTRY` follows a valid `EXIT` for the same known student and lecture.
Timestamps must be ISO 8601 and should include a timezone offset. The backend
converts them to UTC. `UNKNOWN` identities must set
`flagged_for_review=true`; unknown identities are stored for review and are
excluded from attendance calculations. `presence_confirmed` should be true
only after the CV sustained-presence rule confirms the event.

`client_event_id` is optional for existing clients but recommended for safe
retries. Generate it once when the event is first created and reuse the same
value for every retry. It is unique per lecture. Replays without this field
still use the backend's timestamp/student/event duplicate check, but that
fallback is less reliable than a stable client ID.

Unknown additional payload fields are ignored for compatibility.

## Delivery responses

- `201 Created`: event or batch accepted.
- `202 Accepted`: event was stored but flagged for human review. This is a
  successful delivery; do not retry it as a transport failure.
- `200 OK`: the request was an idempotent duplicate. Treat it as delivered.
- `401`, `403`, `404`, `413`, or `422`: permanent request/configuration issue
  to surface and correct; do not silently discard or mark the event delivered.
- `429 Too Many Requests`: retry after the `Retry-After` delay.
- Network timeout or `5xx`: retry with bounded exponential backoff.

For batches, `accepted_count`, `flagged_count`, and `duplicate_count` account
for every submitted event. The default maximum is 100 events per batch; the
request body limit is 1 MiB.

## Append-first queue and retry contract

The JSONL event log remains the durable source of truth:

1. Assign a stable `client_event_id` and append the complete event as one JSON
   line to `cv/data/events.jsonl`.
2. Only after the append succeeds, make an HTTP delivery attempt. Capture must
   continue collecting local events if the API is offline.
3. Keep a separate delivery checkpoint/queue cursor at
   `cv/data/events.delivery`; never remove or rewrite source JSONL records.
   Advance the cursor only after a `200`, `201`, or `202` response.
4. On `429`, wait for `Retry-After`; network errors and `5xx` use bounded
   exponential retries. Each retry cycle is limited to three requests; an
   undelivered record remains pending and the worker retries after 30 seconds.
5. Other `4xx` responses are reported and remain pending. Automatic attempts
   pause until another event arrives or the CV process restarts; fix the camera
   key, classroom/lecture assignment, timestamp, or payload before delivery.
6. After a process restart, resume from the durable checkpoint and resend
   pending events with their original `client_event_id`. The API's idempotency
   behavior makes an accepted-but-unacknowledged retry safe.

Do not log API keys, authorization headers, raw images, or audio. Do not save
frames or audio to the retry queue. Only event JSON is queued.

The CV sender's delivery worker runs outside the camera-capture call, so
network delays do not block the frame loop. If the backend remains unavailable
when the CV process exits, the archive and checkpoint preserve the pending
events for a later restart. Only event JSON is sent; no frames or audio are
queued.

Controlled local integration test: the CV sender loaded its settings from a
temporary root `.env`, posted one ENTRY event to the running FastAPI backend,
and the matching `client_event_id` was verified in SQLite. The temporary `.env`,
camera, admin, lecture, and event were removed after the check. This did not
exercise a physical camera.

## Sender configuration and retry behavior

The root `.env.example` lists the CV sender settings:

| Variable | Default | Purpose |
|---|---:|---|
| `API_BASE_URL` | `http://127.0.0.1:8000` | Backend base URL |
| `ECOSENSE_CAMERA_KEY` | unset | Secret sent only in `X-Camera-Key` |
| `CLASSROOM_ID` / `LECTURE_ID` | unset | Positive numeric IDs required for API delivery |
| `CV_DELIVERY_RETRY_ATTEMPTS` | `3` | Attempts per delivery cycle, including the first |

Request timeout is 2 seconds. Retry backoff starts at 0.5 seconds and doubles;
`Retry-After` is honored up to 30 seconds. Missing credentials or IDs leaves
events archived locally and reports that delivery is not configured. After a
transient retry cycle fails, pending delivery is checked again every 30
seconds; permanent `4xx` failures pause until another event or a process
restart.

## Camera-free simulator

The backend simulator posts the same event contract to the real API. It needs
at least four active student codes enrolled in the selected class. In order,
the first four supplied students represent: normal entry, one exit, multiple
exits/return, and absent. Any additional students receive a normal entry. An
extra `UNKNOWN` event is generated and flagged for review.

From a PowerShell terminal in `backend\`, start the API in another terminal,
then run:

```powershell
.\.venv-backend\Scripts\python.exe -m scripts.simulate `
  --classroom-id 1 `
  --lecture-id 12 `
  --lecture-start "2026-10-25T10:00:00+05:30" `
  --duration-minutes 60 `
  --student-codes "STUDENT_A,STUDENT_B,STUDENT_C,STUDENT_D,STUDENT_E"
```

Set `ECOSENSE_CAMERA_KEY` in the process environment before running, or the
simulator prompts for the camera key without echoing it. `API_BASE_URL` can
override the default `http://127.0.0.1:8000`. Events are appended to
`backend/data/simulated_events.jsonl` before sending. If a permanent API error
occurs, the script reports it and leaves the JSONL available for correction
and replay with `python -m scripts.import_events_jsonl`.

The supplied classroom, lecture, and student codes must exist; the lecture
timestamps must match its scheduled interval. Start the lecture through the
authenticated lifecycle endpoint before checking the live dashboard. Complete
the lecture to finalize attendance. The simulator does not start or end a
lecture on the user's behalf.

Retry settings are configurable in `backend/.env`:

| Variable | Default | Purpose |
|---|---:|---|
| `SIMULATOR_REQUEST_TIMEOUT_SECONDS` | `10` | HTTP timeout per attempt |
| `SIMULATOR_RETRY_ATTEMPTS` | `3` | Retries after the first failed attempt |
| `SIMULATOR_RETRY_BACKOFF_SECONDS` | `1` | Base exponential delay in seconds |

## Automated contract test

`backend/tests/test_cv_integration.py` writes a sample JSONL event stream,
replays it through `POST /events/batch`, then ends the lecture and checks the
derived `RETURN`, inside/outside durations, absent student, and review-flagged
`UNKNOWN` event:

```powershell
Set-Location backend
.\.venv-backend\Scripts\python.exe -m pytest tests\test_cv_integration.py -q
```

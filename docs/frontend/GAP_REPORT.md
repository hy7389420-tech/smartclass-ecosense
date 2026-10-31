# Frontend vs API Gap Report

## Scope and verification method

Checkpoint 3 checked the React/Vite frontend against `docs/API_CONTRACT.md`
without changing frontend files.

Verified runtime state:

- Backend health returned HTTP 200.
- Frontend dev server returned HTTP 200 and rendered the login page after it
  was started with `npm run dev -- --host 127.0.0.1 --port 5173`.
- Frontend production build passed.
- The browser authenticated dashboard could not be opened in this checkpoint
  because no password or browser session was available and passwords are not
  requested in chat.
- The live dashboard response was verified directly through the authenticated
  backend API in Checkpoint 2.

## Dashboard flow

| Area | Frontend behavior | API contract | Result |
|---|---|---|---|
| Login | Reads email/password and stores `access_token` in `ecosense_token`. | `POST /auth/login` returns `access_token`. JWT must be sent for staff routes. | Match, runtime login depends on a configured local password. |
| Current user | Calls `GET /auth/me`. | Authenticated user route. | Match. |
| Lecture selector | Calls `GET /lectures?limit=100&offset=0`; selects a live lecture, otherwise the first lecture. | List envelope has `items`. | Match. |
| Dashboard | Calls `GET /dashboard/{lecture_id}` every 5 seconds. | Same dashboard path. | Match. |
| KPI cards | Reads all contract card fields. | `total_students`, `present`, `inside`, `outside`, `absent`, `occupancy_percent`. | Match. |
| Student table | Reads API `students`. Displays name/code, status, entry, exit, inside/outside minutes, and review flag. | `students` are `AttendanceStudentRead` rows. | Match field names. |
| Camera Offline | Displays the contract text when `camera_status` is `Camera Offline`. | Dashboard camera status has exactly `Online` or `Camera Offline`. | Match. |
| Needs-review badge | Displays `pending_review_count` as `pending review`; also displays `Required` per student. | Dashboard and student review fields exist. | Match, but no review-item action link is present. |
| Engagement | Calls `GET /lectures/{id}/engagement`. | Engagement returns windows, labels, average estimate, notes, and aggregate evidence. | Path and core fields appear compatible; chart renders estimates only. |
| Suggestions | Calls `GET /lectures/{id}/suggestions`; decisions call the decision endpoint. | Same read and decision routes. | Match. |

## API contract comparison

### Endpoints

- `POST /auth/login`
- `GET /auth/me`
- `GET /lectures?limit=100&offset=0`
- `GET /dashboard/{lecture_id}`
- `GET /lectures/{lecture_id}/engagement`
- `GET /lectures/{lecture_id}/suggestions`
- `POST /suggestions/{suggestion_id}/decision`

These frontend calls are present and use paths described in the API contract.

### Field names

The dashboard card/table code matches the API response fields verified against
the live lecture:

- Lecture: `lecture_id`, `lecture_status`
- Cards: `total_students`, `present`, `inside`, `outside`, `absent`,
  `occupancy_percent`
- Students: `student_id`, `student_code`, `name`, `status`, `first_entry`,
  `last_exit`, `inside_minutes`, `outside_minutes`, `exit_count`,
  `return_count`, `flagged`
- Status values handled by the frontend:
  `INSIDE`, `OUTSIDE`, `ABSENT`, `PARTIAL`

The backend contract also defines these statuses, so no student-status field
name mismatch was found.

### Authentication

The frontend stores the JWT as `ecosense_token` and sends the bearer token on
protected requests. The API contract requires a JWT bearer token for dashboard,
lecture, engagement, and suggestion reads. Camera key authentication belongs
only to camera ingestion routes and is not incorrectly exposed in the frontend.

### Error handling

The frontend API wrapper reads:

- `body.error.message`
- `body.detail`
- a fallback status-based message

This accepts the contract's `{ "error": { "code", "message" } }` envelope.
Errors are shown in the UI. HTTP 401 removes the token and reloads to login.

The wrapper does not render the structured API error `code` separately and does
not inspect `Retry-After`; both are contract-compatible omissions rather than
field-name mismatches.

## Gaps and missing behavior

1. **Authenticated browser flow was not verified**
   - Login page is visible and production build passes.
   - Dashboard flow depends on the user's configured local account password.
   - No credentials are stored by the frontend beyond the browser token.

2. **Camera Offline actionability is limited**
   - The offline banner is shown.
   - There is no last-seen time, camera identifier, heartbeat action, or alert
     navigation. These are not required by the dashboard contract.

3. **Needs-review is not a review workflow**
   - The total and flagged student rows are displayed.
   - The contract also provides review queue, correction, and resolve endpoints,
     which are not used by the dashboard frontend.

4. **Lecture completeness information is limited**
   - Lectures are shown by subject and ID.
   - Status/time information is not displayed in the selector, and errors for
     analytics routes that require completed lectures are not represented.

5. **Suggestion actions do not show decisions inline**
   - Accept, reject, and ignore reload the dashboard.
   - The API's decision history is not displayed or refreshed as a decision
     history view.

6. **Engagement API failure handling is silent**
   - Missing engagement is converted to `null` without exposing a detailed API
     error, except for the generic empty chart state.
   - A loading/error distinction would help separate "not enough data" from an
     API failure.

7. **Runtime auto-refresh**
   - The frontend refreshes dashboard data every 5 seconds while `lectureId`
     exists.
   - Multiple concurrent load calls can overlap if API latency exceeds 5
     seconds; no overlap prevention or request cancellation exists.

## Conclusion

The core dashboard request paths and response field names match
`docs/API_CONTRACT.md`. The strongest validated frontend state is the login
page and successful frontend build; the authenticated dashboard could not be
visually claimed because the account password/browser session was unavailable
in this checkpoint. Backend dashboard data for lecture 6 was already verified
through the API.

No frontend files were changed in Checkpoint 3.

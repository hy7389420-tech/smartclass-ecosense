# Backend Decisions

## Phase 8: activity fusion and decision logging

- Use the phase-specified weights: movement `0.30`, inverted inactivity `0.20`,
  front-facing ratio `0.20`, voice-activity ratio `0.20`, and audio level
  `0.10`. Re-normalize the denominator over available non-null signals.
- Normalize audio dBFS against `-120..0`, matching the CV/audio module's
  supported dBFS floor and full-scale ceiling. Inactivity is normalized as a
  fraction of each window's duration and inverted.
- Require two available signals before calculating an estimate. Label values
  below `0.35` as `low`, values from `0.35` to below `0.65` as `medium`, and
  values at or above `0.65` as `high`.
- Do not smooth windows in this version. Decline compares the last three
  usable windows with preceding usable windows and requires at least six
  usable windows. A low run requires three contiguous low windows.
- Accept activity windows from one second through five minutes by default.
  Store only numeric features; allow identical retries and reject overlaps.
- Per the user's approval, defer `POST /suggestions/{id}/decision` and the
  suggestion decision-history endpoint until Phase 9 authentication. Phase 9
  now records the authenticated user ID; every re-decision appends a history
  row and updates the current suggestion status. Never accept a client-supplied
  actor ID or create placeholder identities.

## Phase 9: authentication and access control

- Hash passwords with Argon2id and issue 15-minute HS256 JWTs by default.
  Blank development secrets are generated per process; production requires an
  explicit signing secret of at least 32 characters.
- Revoke existing access tokens when a password changes using a user token
  version. Keep the access token short-lived and require the account to remain
  active for every request.
- Enforce scopes on the server: students are mapped explicitly by nullable,
  unique `users.student_id`; faculty access follows class assignments; HOD
  department scope uses the department on its linked `faculty` profile.
- Rate-limit login requests in-process by client IP. This is suitable for the
  single-process MVP only; a multi-worker deployment needs a shared limiter.

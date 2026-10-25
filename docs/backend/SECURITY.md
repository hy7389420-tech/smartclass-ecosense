# Backend Security Notes

## Controls implemented in Phase 12

- **Authentication/authorization:** Short-lived signed JWTs, Argon2 password
  hashes, active-account checks, token-version revocation, and existing
  object-level ADMIN/HOD/FACULTY/STUDENT scope checks.
- **CORS:** Exact HTTP(S) origins from `CORS_ALLOWED_ORIGINS`; wildcard,
  credentials and paths inside origin entries are rejected. Credentialed
  cross-origin requests are limited to that allowlist.
- **Request size:** Requests are limited to `MAX_REQUEST_BODY_BYTES` (1 MiB by
  default). Declared and streamed bodies are both checked before route code
  processes them.
- **Rate limits:** In-memory per-client-IP limits apply globally and as
  additional buckets to auth and event paths. The existing login-specific
  limiter remains stricter.
- **Response headers:** API responses set `X-Content-Type-Options`,
  `X-Frame-Options`, `Referrer-Policy`, `X-Permitted-Cross-Domain-Policies`,
  and `Cache-Control: no-store`.
- **Errors/logging:** Validation, HTTP and unexpected errors return a common
  safe envelope. Unexpected exceptions are logged with exception type only;
  their details are not returned to clients.
- **Secrets:** Production startup rejects a short or recognizable default
  JWT secret. Runtime dependencies remain exact-version pinned in
  `backend/requirements.txt`.
- **Dependency audit:** `pip-audit -r requirements.txt` reported no known
  vulnerabilities after upgrading PyJWT to 2.15.0. This is a point-in-time
  result, not a guarantee that the application or future dependency versions
  are vulnerability-free.
- **Database queries:** Request-facing query code uses SQLAlchemy expressions
  and bound parameters; no user input is interpolated into SQL text.

## Important limitations

- Rate limiting is process-local, has no shared state across workers, and uses
  the direct client IP. Deployments behind a reverse proxy need trusted-proxy
  configuration before using forwarded client-IP headers; this prototype does
  not trust such headers.
- CORS is not authentication. Non-browser clients can call the API and must
  still pass authentication and role checks.
- TLS termination, firewall policy, secret rotation, backup security,
  monitoring/alerting, and production infrastructure hardening are outside
  this application change.
- The body cap is an application-layer limit; reverse proxies should enforce
  their own request and connection limits too.
- Existing password-change/login limits do not provide a distributed,
  persistent rate limiter.
- No load test or penetration test was run as part of this phase.
- The dependency audit result must be reviewed when dependencies change; an
  audit result does not certify the application as vulnerability-free.

## Configuration checklist

1. Set `APP_ENV=production`.
2. Provide a unique high-entropy `JWT_SECRET_KEY` of at least 32 characters
   through a secret manager or deployment environment.
3. Set `CORS_ALLOWED_ORIGINS` to the exact deployed frontend origins.
4. Keep event-camera keys private and use TLS at the deployment edge.
5. Review the 1 MiB body and rate limits against actual expected batch sizes.
6. Configure infrastructure-level throttling and persistent limits if running
   multiple workers or replicas.

# SmartClass EcoSense Data Retention Policy

## Current prototype policy

The configured retention period is **90 days** by default
(`RETENTION_DAYS=90`). An ADMIN can preview eligible records with
`POST /admin/retention/run` before explicitly requesting deletion. The script
`python -m scripts.retention` is also a dry-run unless `--execute` is supplied.
Each API or script run writes an audit entry with the cutoff and record counts.

| Data | Why it is stored | Access | Retention/deletion |
|---|---|---|---|
| Presence events | Calculate lecture attendance and preserve event provenance | ADMIN; HOD/FACULTY within class scope; students only their own allowed data | Deleted when `timestamp_utc` is older than the 90-day cutoff |
| Numeric activity windows | Class-level activity estimates and teacher decision support | ADMIN; HOD/FACULTY within class scope | Deleted when `window_end` is older than the 90-day cutoff |
| Insights | Neutral lecture-level insight text and JSON evidence | ADMIN; HOD/FACULTY within class scope | Deleted when `created_at` is older than the 90-day cutoff |
| Attendance records | Lecture attendance totals and presence history | ADMIN; HOD/FACULTY within scope; students only their own | **Not deleted by this job**; records can outlive the event history |
| Audit logs | Accountability for corrections, resolutions, and retention runs | ADMIN only | **Not deleted by this job** |

No video, images, raw audio, or speech transcripts are part of the retention
job. Activity values are estimates based on observable indicators, not proof
of attention or learning. A report is not a substitute for human review.

## Correction provenance

When an expired source event is referenced by a newer correction event, the
retention run clears that correction's `correction_of_event_id` before
deleting the source. This keeps the retained correction but removes its direct
link to expired event details. The run reports how many such links will be
detached; the audit log records the count.

## Limitations and review needed

- The job runs only when an ADMIN or operator invokes it; no scheduler is
  configured.
- Attendance records and audit logs have no automatic expiration. In
  particular, attendance records may retain derived student presence totals
  after the raw event is deleted. A future policy decision is needed if these
  derived records should also expire.
- Audit snapshots may retain identifiers and event details needed to document
  manual corrections even after the corresponding event is purged; audit-log
  retention needs a separate policy review.
- Deletion is permanent at the application/database level. Take any required
  institution-approved backups before using `--execute`.
- This prototype policy is not a legal-compliance claim. Confirm institutional
  policy and applicable requirements before deployment.

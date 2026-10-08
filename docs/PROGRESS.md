# SmartClass EcoSense - Progress Log

Update this file at the END of every coding session (you or the AI agent).
A new chat/agent reads this first to know where to continue.

## Current status
- **Current phase:** CV module (Steps 4.1-4.6) complete and tested; Step 4.5b backend event delivery is pending.
- **Last updated:** 2026-10-08
- **Working right now:** CV module is complete.
- **Next task:** Step 4.5b - connect the CV event sender to the backend (PENDING).

## Done
- [x] Context files created (AGENTS.md, PROJECT_CONTEXT.md, ROADMAP.md, ARCHITECTURE.md, PROGRESS.md)
- [x] CV Step 4.1: webcam capture and live window
- [x] CV Step 4.2: YOLO person-only detection and bounding boxes
- [x] CV Step 4.3: ByteTrack IDs displayed on person boxes
- [x] CV Step 4.4: virtual line crossing and console ENTRY/EXIT
- [x] CV Step 4.5a: console and `cv/data/events.jsonl` event output
- [x] CV Step 4.6: manual track-ID-to-demo-student mapping

## In progress
- Step 4.5b backend event delivery is pending.

## Next (in order)
1. [ ] Step 4.5b: send CV events to the backend (PENDING)

## Known bugs / issues
- (none yet)

## Decisions made
- SQLite for MVP, PostgreSQL later
- Simulator before camera
- Rule-based insights before any LLM
- Pehle Phase 0-4 (MVP), uske baad hi camera/AI advanced features

## Commands that work (add only after you have tested them)
- (none yet)

## Test status
- Presence tests: not written yet
- Last test run: never

## Session log
| Date | What was done | Commit message |
|---|---|---|
| (date) | Created context files | docs: add project context files |

## Notes for the next session
- Read AGENTS.md, ROADMAP.md and ARCHITECTURE.md first.
- Work on ONE phase at a time. Explain WHAT, WHY, HOW, FILES before coding.

## CV module progress
- Step 4.1 webcam capture: implemented in `cv/capture.py`; camera index and window title are in `cv/config.py`.
- User confirmed Step 4.1 live webcam test works on 2026-10-08.
- User confirmed Step 4.2 person-only YOLO detection and live bounding boxes work on 2026-10-08.
- User confirmed Step 4.3 ByteTrack tracking IDs work on the webcam on 2026-10-08.
- Step 4.4 pure line-crossing logic, live line overlay and console-only ENTRY/EXIT reporting implemented; 10 fake-point tests and mocked capture integration check passed.
- Step 4.5a JSONL event sender implemented with console output; event schema and append behavior tests added.
- User confirmed Step 4.5a live webcam event logging works on 2026-10-08.
- Step 4.6 manual identity mapping implemented: click a visible person box, then press 1-5 to map the track ID to a demo student; unknown IDs are review-flagged in JSONL.
- Fixed repeated ENTRY/EXIT events caused by line-side jitter: the line counter now uses a configurable hysteresis band while preserving the 2-second cooldown.
- User confirmed CV module Steps 4.1-4.6 are complete and tested.
- Next CV task: Step 4.5b backend event delivery (PENDING).

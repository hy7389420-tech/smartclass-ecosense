## Current status
- **Steps 4.1-4.6:** Complete and tested.
- **Step A - sustained presence:** Implemented and tested; ENTRY/EXIT output is gated on confirmation.
- **Step B - movement and inactivity:** Implemented and unit tested; frame capture integration is not part of this step.
- **Step C - head orientation estimate:** Implemented and unit tested; no recorded-video evaluation has been run.
- **Step D - audio features:** Implemented and unit tested with synthetic signals and a mocked microphone callback; live microphone hardware has not been tested.
- **Step E - activity-window aggregation:** Implemented and unit tested; writes merged numeric estimates to JSONL.
- **Step F - session integration:** Implemented and tested with fake camera, frame, and microphone inputs; live camera/microphone checklist remains pending.
- **Step 4.5b:** Sender implementation and controlled local API delivery test are complete; 17 focused sender tests and 84 CV/audio tests pass. Live test setup is ready; physical camera/API validation remains pending.

## Tested
- Environment: Python 3.12.3 virtual environment (`.venv-cv`), OpenCV 4.11.0, PyTorch 2.14.1+cpu, Ultralytics 8.4.174.
- Step C environment: MediaPipe 1.1.1 with the official Face Landmarker model; a synthetic blank-frame inference returned no faces.
- Step 4.1: live webcam capture and window.
- Step 4.2: YOLO person-only detection and live bounding boxes; a synthetic blank-frame inference returned no person boxes.
- Step 4.3: ByteTrack track IDs shown on the live webcam boxes.
- Step 4.4: live line crossing and console ENTRY/EXIT reporting; fake-point tests cover initial-side baseline, both directions, cooldown, independent track state, on-line points, and invalid configuration.
- Step 4.5a: live JSONL event logging; tests cover event schema, UTC ISO timestamps, append behavior, console output, and input validation.
- Step 4.6: manual track-ID-to-demo-student mapping and live interaction; tests cover assignments, unknown-ID review flagging, invalid keys, and mapped/unknown event payloads.
- The full CV unit test suite passes (54 tests), including near-line jitter suppression with a configurable hysteresis band.
- Step A: 9 focused tests pass for duration, mean confidence, gap resets, and invalid configuration; brief appearances do not confirm.
- Step B: 7 focused tests pass for identical/changed synthetic frames, frame preprocessing, and window movement/inactivity aggregation. The complete CV suite passes (43 tests).
- Step C: 11 focused tests pass for yaw classification, transformation-matrix yaw extraction, and window aggregates. No-face windows return a null front-facing ratio. The complete CV suite passes (54 tests).
- Manual video evaluation is still pending; the video command's `--help` interface was checked.
- Step D: 12 audio tests pass for silence, synthetic sine/noise, aggregation, validation, buffer capacity, and mocked microphone-unavailable/callback behavior. The audio callback retains only numeric measurements; no microphone hardware test was run.
- Step E: 5 tests pass for output fields, ISO window boundaries, null handling, JSONL append behavior, and invalid timestamps. Only aggregate numeric values are written.
- Step F: 5 integration tests pass for partial-window output, microphone-offline nulls, no fabricated empty windows, camera-offline handling, `q` shutdown, and resource cleanup.
- Full CV and audio suite after Step 4.5b: 84 tests pass. Hardware behavior has not yet been tested live.
- Step 4.5b: append events with a stable client ID to JSONL before background delivery; use the root `.env` camera key and numeric classroom/lecture IDs; keep failed deliveries pending behind a checkpoint. Tests cover append-before-POST, bounded retry, permanent rejection, offline retention, and restart replay. A controlled local API test stored and verified one event; physical camera operation has not been tested.
- Live camera preparation (2026-10-27): root `.env` copied from `.env.example`, camera key kept only there, backend running, classroom 1 camera configured, and live lecture 4 started with all five active demo students in class 1. Waiting for the user to run `python -m cv.session`.

## Limitations
- Camera index is currently `0`; change `CAMERA_INDEX` in `cv/config.py` if the webcam uses a different index.
- Line endpoints are normalized `(x, y)` coordinates from `0.0` to `1.0`; adjust `LINE_START` and `LINE_END` to position the line over the doorway.
- With the default endpoint order, negative-to-positive is ENTRY and positive-to-negative is EXIT. Reverse the endpoint order to reverse those labels.
- Cooldown is per track ID and defaults to 2 seconds.
- Line-crossing hysteresis defaults to 0.02 normalized frame distance; adjust `LINE_CROSSING_HYSTERESIS_DISTANCE` in `cv/config.py` if near-line detections still jitter.
- Track IDs can change after occlusion or tracker resets, so assignments are temporary.
- Occlusion can hide a person and interrupt detection or tracking.
- Bounding-box movement jitter near the virtual line can affect crossing detection despite the cooldown and hysteresis.
- Identity is manual only; a track ID is not automatically verified as a real student's identity.
- Demo student assignment uses keys `1`-`5`; click a visible person box first.
- Unknown track IDs are saved with `student_id="UNKNOWN"` and `flagged_for_review=true`.
- Until room/lecture configuration is implemented, saved events use `UNKNOWN` for classroom and lecture IDs.
- Runtime event log is `cv/data/events.jsonl`; `cv/data/` is ignored by the repository's existing ignore rules.
- Model: `yolo11n.pt`; Ultralytics downloads its weights on first run.
- ByteTrack supplies temporary tracking IDs, not student identity; IDs may change after occlusion or tracker resets.
- Detection quality has not been measured.
- Motion is a frame-difference estimate: camera shake, lighting changes, and missed frames can affect results. Large sample gaps are excluded from inactivity time.
- Head orientation is only an estimate from visible face landmarks. It needs visible faces and is weak for far-away or seated students; no accuracy has been measured. It must not be interpreted as attention or engagement.
- Head-pose model asset is stored locally at `cv/data/face_landmarker.task`; only the model and numeric estimates are kept, never frames or landmarks.
- Audio uses an energy threshold, not speech recognition; room noise and microphone gain can affect voice-activity estimates. No raw audio or transcript is saved. Live microphone behavior has not been tested.
- No frames or video are saved.

## Manual integrated-session checklist (not yet run)
- Start `python -m cv.session` with a working camera and microphone; confirm the existing camera window and controls appear.
- Press `q`; confirm the window closes, resources stop, and any valid partial activity window is appended.
- Keep a person visible for at least the configured sustained-presence duration, then cross the virtual line; verify an event is saved only after confirmation and has `presence_confirmed: true`.
- After a window completes (or a partial window is flushed on quit), inspect `cv/data/activity_windows.jsonl` for ISO boundaries, numeric class-level fields, the estimate note, and no raw media.
- Disconnect/deny camera access; confirm `Camera Offline` and no new event/activity record.
- Disable or disconnect the microphone while leaving the camera available; confirm `Microphone Offline` and `null` audio fields.
- Face estimates need visible faces; far-away/seated faces may not be detected. Do not interpret any output as attention or engagement.

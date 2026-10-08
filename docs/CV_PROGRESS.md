# CV Module Progress

## Current status
- **Steps 4.1-4.6:** Complete and tested.
- **Step 4.5b:** PENDING - send events to the backend.

## Tested
- Environment: Python 3.12.3 virtual environment (`.venv-cv`), OpenCV 4.11.0, PyTorch 2.14.1+cpu, Ultralytics 8.4.174.
- Step 4.1: live webcam capture and window.
- Step 4.2: YOLO person-only detection and live bounding boxes; a synthetic blank-frame inference returned no person boxes.
- Step 4.3: ByteTrack track IDs shown on the live webcam boxes.
- Step 4.4: live line crossing and console ENTRY/EXIT reporting; fake-point tests cover initial-side baseline, both directions, cooldown, independent track state, on-line points, and invalid configuration.
- Step 4.5a: live JSONL event logging; tests cover event schema, UTC ISO timestamps, append behavior, console output, and input validation.
- Step 4.6: manual track-ID-to-demo-student mapping and live interaction; tests cover assignments, unknown-ID review flagging, invalid keys, and mapped/unknown event payloads.
- The full CV unit test suite passes (23 tests), including near-line jitter suppression with a configurable hysteresis band.

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
- No frames or video are saved.

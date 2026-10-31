# CV Module Spec - SmartClass EcoSense

## Scope

Webcam -> person detection -> tracking -> virtual line crossing
-> sustained-presence check -> ENTRY/EXIT events -> EventSender.
Class-level movement, head-orientation and audio features are computed locally
and aggregated into activity windows. They are estimates, not proof of attention.

## NOT in scope (do not build)

Face recognition, backend, database, dashboard, AI insights,
multiple cameras, cloud, storing raw frames/video/audio, or speech transcripts.

## Pipeline

capture.py -> detector.py -> tracker.py -> line_counter.py
-> sustained.py -> identity.py (manual map) -> event_sender.py

`python -m cv.session` runs the camera pipeline with motion, head-orientation,
audio capture, and JSONL activity-window output.

## Rules

- Use Python + OpenCV + Ultralytics YOLO (person class only).
- Keep detection, identity and event logic in SEPARATE files.
- line_counter.py must be pure logic (no camera, no YOLO imports)
  so it can be unit-tested with fake points.
- Never save raw frames or video. Only events.
- Do not save raw audio, speech transcripts, face images, or landmarks. Store only events and aggregated numeric features.
- CV settings (camera index, thresholds, frame skip, and window length) in `cv/config.py`; audio settings in `audio/config.py`.
- EventSender: append events to `cv/data/events.jsonl` first, then dispatch to
  `POST /events` from a background worker when `.env` has a camera key and
  numeric classroom/lecture IDs. Pending events stay archived with a delivery
  checkpoint for retry after backend/network failure.
- Event schema: student_id, classroom_id, lecture_id, event_type
  (ENTRY/EXIT), timestamp (ISO), confidence, source="camera",
  flagged_for_review, presence_confirmed=true.
- Activity-window schema includes ISO window boundaries, classroom/lecture IDs,
  movement/inactivity, nullable front-facing/audio measurements, source, and
  the estimate note.
- If camera fails: print "Camera Offline". Never create fake events.
- Identity is a mapping track_id -> student_id (manual for demo).
  Click a person box to select its track, then press keys 1-5 to assign
  the demo students configured in config.py.
  Unknown track ID -> student_id = "UNKNOWN", flagged_for_review = true.
- Do not claim accuracy. Add a note in CV_PROGRESS.md of what was tested.
- Outputs from movement, head orientation, and audio are class-level estimates based on observable indicators, never individual attention scores.
- Camera or microphone failure must be reported and must not produce fabricated data.

## Known limitations (be honest)

Occlusion, lighting, ID switches, camera angle, crowding at the door.
Camera should face the door/entry line, not the whole classroom.

## Definition of done per step

4.1 live window | 4.2 person boxes | 4.3 stable IDs
4.4 console ENTRY/EXIT | 4.5a events.jsonl | 4.6 manual ID map

## Run and test

Activate `.venv-cv`, then run:

```powershell
.\.venv-cv\Scripts\python.exe -m pip install -r cv\requirements.txt
.\.venv-cv\Scripts\python.exe -m pip install -r audio\requirements.txt
.\.venv-cv\Scripts\python.exe -m cv.session
.\.venv-cv\Scripts\python.exe -m pytest cv\tests audio\tests
```

The MediaPipe model is downloaded separately to the ignored `cv\data\` directory:

```powershell
New-Item -ItemType Directory -Force cv\data
Invoke-WebRequest -Uri 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task' -OutFile cv\data\face_landmarker.task
```

For head-pose testing with a recorded video:

```powershell
.\.venv-cv\Scripts\python.exe -m cv.tools.test_headpose_video <recorded-video-path>
```

## folder structure 
smartclass-ecosense/
├── docs/
│   ├── CV_SPEC.md          ← agent ke liye CV ka scope (neeche likha hai)
│   └── CV_PROGRESS.md      ← CV ka alag progress log
└── cv/
    ├── session.py          # integrates camera, CV features and audio
    ├── config.py           # CV thresholds and window settings
    ├── capture.py          # camera UI, event pipeline and session hooks
    ├── detector.py         # person-only detection
    ├── tracker.py          # person tracking
    ├── line_counter.py     # pure line-crossing logic
    ├── sustained.py        # sustained-presence rule
    ├── motion.py           # pure motion scoring/window aggregation
    ├── motion_capture.py   # OpenCV motion preprocessing
    ├── headpose.py         # pure yaw and window aggregation
    ├── headpose_capture.py # MediaPipe wrapper
    ├── activity_windows.py # record validation and JSONL writer
    ├── identity.py
    ├── event_sender.py
    ├── tools/
    │   └── test_headpose_video.py
    ├── data/               # runtime JSONL/model assets (ignored)
    └── tests/
        └── unit and integration tests
audio/
    ├── config.py
    ├── audio_features.py   # pure numeric audio logic
    ├── audio_capture.py    # microphone wrapper
    ├── requirements.txt
    └── tests/
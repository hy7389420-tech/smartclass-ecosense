# CV Module Spec - SmartClass EcoSense

## Scope (ONLY this)

Webcam -> person detection -> tracking -> virtual line crossing
-> ENTRY/EXIT events -> EventSender. Nothing else.

## NOT in scope (do not build)

Face recognition, backend, database, dashboard, AI insights,
multiple cameras, cloud, saving video.

## Pipeline

capture.py -> detector.py -> tracker.py -> line_counter.py
-> identity.py (manual map) -> event_sender.py

## Rules

- Use Python + OpenCV + Ultralytics YOLO (person class only).
- Keep detection, identity and event logic in SEPARATE files.
- line_counter.py must be pure logic (no camera, no YOLO imports)
  so it can be unit-tested with fake points.
- Never save raw frames or video. Only events.
- All settings (camera index, line points, confidence, cooldown) in config.py.
- EventSender: console + data/events.jsonl now; POST /events later.
  Only this file changes when the backend is ready.
- Event schema: student_id, classroom_id, lecture_id, event_type
  (ENTRY/EXIT), timestamp (ISO), confidence, source="camera",
  flagged_for_review.
- If camera fails: print "Camera Offline". Never create fake events.
- Identity is a mapping track_id -> student_id (manual for demo).
  Click a person box to select its track, then press keys 1-5 to assign
  the demo students configured in config.py.
  Unknown track ID -> student_id = "UNKNOWN", flagged_for_review = true.
- Do not claim accuracy. Add a note in CV_PROGRESS.md of what was tested.

## Known limitations (be honest)

Occlusion, lighting, ID switches, camera angle, crowding at the door.
Camera should face the door/entry line, not the whole classroom.

## Definition of done per step

4.1 live window | 4.2 person boxes | 4.3 stable IDs
4.4 console ENTRY/EXIT | 4.5a events.jsonl | 4.6 manual ID map

## folder structure 
smartclass-ecosense/
├── docs/
│   ├── CV_SPEC.md          ← agent ke liye CV ka scope (neeche likha hai)
│   └── CV_PROGRESS.md      ← CV ka alag progress log
└── cv/
    ├── main.py             # sab ko jodta hai
    ├── config.py           # camera index, line coordinates, model naam, confidence
    ├── capture.py          # 4.1
    ├── detector.py         # 4.2
    ├── tracker.py          # 4.3
    ├── line_counter.py     # 4.4 (core logic)
    ├── event_sender.py     # 4.5
    ├── identity.py         # 4.6
    ├── requirements.txt
    ├── data/               # events.jsonl (.gitignore mein)
    └── tests/
        └── test_line_counter.py 
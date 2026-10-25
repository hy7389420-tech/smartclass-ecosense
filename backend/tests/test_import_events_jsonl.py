import json
from pathlib import Path

import pytest

from app.models import Camera
from app.services.camera_auth import hash_camera_key
from scripts.import_events_jsonl import import_events_jsonl

CAMERA_KEY = "jsonl-import-camera-key"


def test_importer_reuses_event_service_for_jsonl(
    client, session_factory, tmp_path: Path
):
    department = client.post("/departments", json={"name": "Engineering"}).json()
    class_group = client.post(
        "/classes",
        json={
            "department_id": department["id"],
            "name": "B.Tech",
            "section": "A",
            "year": 1,
        },
    ).json()
    classroom = client.post(
        "/classrooms",
        json={"name": "Room 101", "capacity": 60},
    ).json()
    client.post(
        "/students",
        json={
            "student_code": "STUDENT_A",
            "roll_no": "1",
            "name": "Student A",
            "class_id": class_group["id"],
        },
    )
    lecture = client.post(
        "/lectures",
        json={
            "classroom_id": classroom["id"],
            "class_id": class_group["id"],
            "subject": "Physics",
            "start_time": "2030-01-01T10:00:00Z",
            "end_time": "2030-01-01T11:00:00Z",
        },
    ).json()
    with session_factory.begin() as session:
        session.add(
            Camera(
                classroom_id=classroom["id"],
                name="Door Camera",
                api_key_hash=hash_camera_key(CAMERA_KEY),
            )
        )

    records = [
        {
            "student_id": "STUDENT_A",
            "classroom_id": classroom["id"],
            "lecture_id": lecture["id"],
            "event_type": "ENTRY",
            "timestamp": "2030-01-01T10:00:00Z",
            "confidence": 0.9,
            "source": "camera",
            "presence_confirmed": True,
            "ignored_extra_field": "accepted",
        }
    ]
    jsonl_path = tmp_path / "events.jsonl"
    jsonl_path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    with session_factory.begin() as session:
        summary = import_events_jsonl(jsonl_path, session, CAMERA_KEY)

    assert summary.accepted_count == 1
    assert summary.flagged_count == 0
    assert summary.duplicate_count == 0
    assert client.get(f"/events?lecture_id={lecture['id']}").json()["total"] == 1


def test_importer_rejects_invalid_json_with_line_number(
    client, session_factory, tmp_path
):
    classroom = client.post(
        "/classrooms",
        json={"name": "Room 101", "capacity": 60},
    ).json()
    with session_factory.begin() as session:
        session.add(
            Camera(
                classroom_id=classroom["id"],
                name="Door Camera",
                api_key_hash=hash_camera_key(CAMERA_KEY),
            )
        )
    jsonl_path = tmp_path / "bad_events.jsonl"
    jsonl_path.write_text("{not-json}\n", encoding="utf-8")

    with (
        pytest.raises(ValueError, match="Invalid JSON on line 1"),
        session_factory.begin() as session,
    ):
        import_events_jsonl(jsonl_path, session, CAMERA_KEY)

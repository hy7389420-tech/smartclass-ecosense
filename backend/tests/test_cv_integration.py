import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.models import Camera
from app.services.camera_auth import hash_camera_key
from scripts.simulate import (
    append_jsonl,
    build_event_stream,
    submit_event_batch,
)

CAMERA_KEY = "cv-integration-test-key"


def test_sample_jsonl_replays_through_events_api_and_derives_attendance(
    client, session_factory: sessionmaker[Session], tmp_path: Path
):
    department = client.post("/departments", json={"name": "CV Integration"}).json()
    class_group = client.post(
        "/classes",
        json={
            "department_id": department["id"],
            "name": "B.Tech",
            "section": "CV",
            "year": 1,
        },
    ).json()
    classroom = client.post(
        "/classrooms",
        json={"name": "CV Integration Room", "capacity": 60},
    ).json()
    student_codes = ["CV_NORMAL", "CV_ONE_EXIT", "CV_MULTI_EXIT", "CV_ABSENT"]
    for index, student_code in enumerate(student_codes, start=1):
        response = client.post(
            "/students",
            json={
                "student_code": student_code,
                "roll_no": str(index),
                "name": f"CV Student {index}",
                "class_id": class_group["id"],
            },
        )
        assert response.status_code == 201

    lecture_start = datetime.now(UTC).replace(second=0, microsecond=0) - timedelta(
        minutes=70
    )
    lecture_end = lecture_start + timedelta(minutes=60)
    lecture = client.post(
        "/lectures",
        json={
            "classroom_id": classroom["id"],
            "class_id": class_group["id"],
            "subject": "Integration Test",
            "start_time": lecture_start.isoformat(),
            "end_time": lecture_end.isoformat(),
        },
    ).json()
    with session_factory.begin() as session:
        session.add(
            Camera(
                classroom_id=classroom["id"],
                name="Integration Camera",
                api_key_hash=hash_camera_key(CAMERA_KEY),
            )
        )

    assert client.post(f"/lectures/{lecture['id']}/start").status_code == 200
    events = build_event_stream(
        classroom["id"],
        lecture["id"],
        lecture_start,
        60,
        student_codes,
    )
    sample_jsonl = tmp_path / "events.jsonl"
    append_jsonl(sample_jsonl, events)
    sample_payload = [
        json.loads(line)
        for line in sample_jsonl.read_text(encoding="utf-8").splitlines()
    ]

    response = client.post(
        "/events/batch",
        json=sample_payload,
        headers={"X-Camera-Key": CAMERA_KEY},
    )

    assert response.status_code == 202
    assert response.json()["accepted_count"] == 7
    assert response.json()["flagged_count"] == 1
    assert response.json()["duplicate_count"] == 0

    stored_events = client.get(f"/events?lecture_id={lecture['id']}").json()["items"]
    multiple_exit_types = [
        event["event_type"]
        for event in stored_events
        if event["student_code_raw"] == "CV_MULTI_EXIT"
    ]
    assert multiple_exit_types == ["ENTRY", "EXIT", "RETURN", "EXIT"]

    attendance = client.post(f"/lectures/{lecture['id']}/end").json()
    records = {record["student_code"]: record for record in attendance["records"]}
    assert attendance["finalized"] is True
    assert attendance["total_students"] == 4
    assert attendance["present"] == 3
    assert attendance["inside"] == 1
    assert attendance["outside"] == 2
    assert attendance["absent"] == 1
    assert records["CV_NORMAL"]["status"] == "INSIDE"
    assert records["CV_NORMAL"]["inside_minutes"] == 57
    assert records["CV_ONE_EXIT"]["status"] == "OUTSIDE"
    assert records["CV_ONE_EXIT"]["exit_count"] == 1
    assert records["CV_ONE_EXIT"]["outside_minutes"] == 30
    assert records["CV_MULTI_EXIT"]["status"] == "OUTSIDE"
    assert records["CV_MULTI_EXIT"]["exit_count"] == 2
    assert records["CV_MULTI_EXIT"]["return_count"] == 1
    assert records["CV_MULTI_EXIT"]["outside_minutes"] == 30
    assert records["CV_ABSENT"]["status"] == "ABSENT"


def test_simulator_retries_rate_limit_and_uses_retry_after(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    responses = iter(
        [
            httpx.Response(429, headers={"Retry-After": "2"}),
            httpx.Response(
                201,
                json={"accepted_count": 1, "flagged_count": 0, "duplicate_count": 0},
            ),
        ]
    )
    sleeps: list[float] = []
    monkeypatch.setattr("scripts.simulate.time.sleep", sleeps.append)
    client = httpx.Client(transport=httpx.MockTransport(lambda _: next(responses)))

    summary = submit_event_batch(
        client,
        "http://api.example.test/",
        CAMERA_KEY,
        [{"student_id": "CV_NORMAL"}],
        Settings(simulator_retry_backoff_seconds=0),
        tmp_path / "events.jsonl",
    )

    assert sleeps == [2.0]
    assert summary.accepted_count == 1
    client.close()


def test_simulator_retains_jsonl_and_surfaces_permanent_api_errors(tmp_path: Path):
    events = [{"student_id": "CV_NORMAL"}]
    jsonl_path = tmp_path / "events.jsonl"
    append_jsonl(jsonl_path, events)
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                401,
                json={
                    "error": {
                        "code": "INVALID_CAMERA_KEY",
                        "message": "Camera key is invalid.",
                    }
                },
            )
        )
    )

    with pytest.raises(RuntimeError, match="remain in"):
        submit_event_batch(
            client,
            "http://api.example.test",
            CAMERA_KEY,
            events,
            Settings(simulator_retry_attempts=0),
            jsonl_path,
        )

    assert jsonl_path.read_text(encoding="utf-8").splitlines() == [
        '{"student_id":"CV_NORMAL"}'
    ]
    client.close()

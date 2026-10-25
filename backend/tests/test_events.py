import pytest

from app.main import app
from app.models import Camera
from app.services.camera_auth import hash_camera_key

CAMERA_KEY = "test-camera-secret"


def event_payload(
    classroom_id: int,
    lecture_id: int,
    event_type: str = "ENTRY",
    timestamp: str = "2030-01-01T10:00:00Z",
    student_id: str = "STUDENT_A",
    client_event_id: str | None = None,
) -> dict:
    payload = {
        "student_id": student_id,
        "classroom_id": classroom_id,
        "lecture_id": lecture_id,
        "event_type": event_type,
        "timestamp": timestamp,
        "confidence": 0.9,
        "source": "camera",
        "presence_confirmed": True,
        "track_id": 17,
    }
    if client_event_id is not None:
        payload["client_event_id"] = client_event_id
    return payload


def create_camera_context(client, session_factory):
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
    student = client.post(
        "/students",
        json={
            "student_code": "STUDENT_A",
            "roll_no": "1",
            "name": "Student A",
            "class_id": class_group["id"],
        },
    ).json()
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
    return classroom, student, lecture


def test_camera_key_is_required_and_wrong_key_is_rejected(client):
    payload = event_payload(1, 1)

    missing = client.post("/events", json=payload)
    wrong = client.post(
        "/events",
        json=payload,
        headers={"X-Camera-Key": "incorrect"},
    )

    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "CAMERA_KEY_REQUIRED"
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "INVALID_CAMERA_KEY"


def test_openapi_documents_dynamic_ingestion_responses_and_camera_header():
    schema = app.openapi()
    single = schema["paths"]["/events"]["post"]
    batch = schema["paths"]["/events/batch"]["post"]

    assert {"200", "201", "202", "401", "403", "404", "422"} <= set(single["responses"])
    assert {"200", "201", "202", "401", "403", "404", "422"} <= set(batch["responses"])
    assert any(
        parameter["name"] == "X-Camera-Key" for parameter in single["parameters"]
    )


@pytest.mark.parametrize(
    ("id_override", "expected_code"),
    [
        ({"lecture_id": 999}, "LECTURE_NOT_FOUND"),
        ({"classroom_id": 999}, "CLASSROOM_MISMATCH"),
    ],
)
def test_unknown_lecture_and_classroom_mismatch_are_rejected(
    client, session_factory, id_override, expected_code
):
    classroom, _, lecture = create_camera_context(client, session_factory)
    payload = {
        **event_payload(classroom["id"], lecture["id"]),
        **id_override,
    }

    response = client.post(
        "/events",
        json=payload,
        headers={"X-Camera-Key": CAMERA_KEY},
    )

    assert response.status_code in (404, 422)
    assert response.json()["error"]["code"] == expected_code


def test_entry_exit_return_and_idempotency(client, session_factory):
    classroom, student, lecture = create_camera_context(client, session_factory)
    headers = {"X-Camera-Key": CAMERA_KEY}

    entry_payload = event_payload(
        classroom["id"],
        lecture["id"],
        timestamp="2030-01-01T10:00:00Z",
        client_event_id="event-entry",
    )
    entry = client.post("/events", json=entry_payload, headers=headers)
    assert entry.status_code == 201
    assert entry.json()["event"]["event_type"] == "ENTRY"

    retry = client.post("/events", json=entry_payload, headers=headers)
    assert retry.status_code == 200
    assert retry.json()["duplicate"] is True
    assert retry.json()["event"]["id"] == entry.json()["event"]["id"]

    exit_payload = event_payload(
        classroom["id"],
        lecture["id"],
        event_type="EXIT",
        timestamp="2030-01-01T10:20:00Z",
    )
    exit_response = client.post("/events", json=exit_payload, headers=headers)
    assert exit_response.status_code == 201
    assert exit_response.json()["event"]["event_type"] == "EXIT"

    return_payload = event_payload(
        classroom["id"],
        lecture["id"],
        timestamp="2030-01-01T10:35:00Z",
    )
    returned = client.post("/events", json=return_payload, headers=headers)
    assert returned.status_code == 201
    assert returned.json()["event"]["event_type"] == "RETURN"

    duplicate_without_client_id = client.post(
        "/events",
        json=return_payload,
        headers=headers,
    )
    assert duplicate_without_client_id.status_code == 200
    assert duplicate_without_client_id.json()["duplicate"] is True

    filtered = client.get(
        f"/events?lecture_id={lecture['id']}&student_id={student['id']}"
        "&event_type=RETURN&flagged_for_review=false"
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["event_type"] == "RETURN"


def test_invalid_sequence_is_persisted_for_review(client, session_factory):
    classroom, _, lecture = create_camera_context(client, session_factory)
    response = client.post(
        "/events",
        json=event_payload(
            classroom["id"],
            lecture["id"],
            event_type="EXIT",
            timestamp="2030-01-01T10:05:00Z",
        ),
        headers={"X-Camera-Key": CAMERA_KEY},
    )

    assert response.status_code == 202
    assert response.json()["flagged_for_review"] is True
    assert response.json()["reason"] == "invalid_sequence:exit_before_entry"
    assert response.json()["event"]["review_status"] == "needs_review"


@pytest.mark.parametrize(
    ("events", "expected_reason"),
    [
        (
            [("ENTRY", "10:00"), ("ENTRY", "10:05")],
            "invalid_sequence:entry_while_inside",
        ),
        (
            [("ENTRY", "10:00"), ("EXIT", "10:05"), ("EXIT", "10:10")],
            "invalid_sequence:exit_while_outside",
        ),
        (
            [("ENTRY", "10:10"), ("EXIT", "10:05")],
            "event_out_of_order",
        ),
    ],
)
def test_invalid_event_sequences_are_flagged(
    client, session_factory, events, expected_reason
):
    classroom, _, lecture = create_camera_context(client, session_factory)
    headers = {"X-Camera-Key": CAMERA_KEY}

    responses = [
        client.post(
            "/events",
            json=event_payload(
                classroom["id"],
                lecture["id"],
                event_type=event_type,
                timestamp=f"2030-01-01T{time}:00Z",
            ),
            headers=headers,
        )
        for event_type, time in events
    ]

    assert all(response.status_code == 201 for response in responses[:-1])
    assert responses[-1].status_code == 202
    assert responses[-1].json()["reason"] == expected_reason


def test_unknown_and_unmatched_student_codes_are_review_flagged(
    client, session_factory
):
    classroom, _, lecture = create_camera_context(client, session_factory)
    headers = {"X-Camera-Key": CAMERA_KEY}

    unknown = client.post(
        "/events",
        json=event_payload(
            classroom["id"],
            lecture["id"],
            student_id="UNKNOWN",
        ),
        headers=headers,
    )
    unmatched = client.post(
        "/events",
        json=event_payload(
            classroom["id"],
            lecture["id"],
            student_id="NOT_ENROLLED",
        ),
        headers=headers,
    )

    assert unknown.status_code == 202
    assert unknown.json()["event"]["student_id"] is None
    assert unknown.json()["event"]["student_code_raw"] == "UNKNOWN"
    assert unmatched.status_code == 202
    assert unmatched.json()["event"]["student_id"] is None


def test_timestamps_within_grace_are_flagged_and_beyond_grace_rejected(
    client, session_factory
):
    classroom, _, lecture = create_camera_context(client, session_factory)
    headers = {"X-Camera-Key": CAMERA_KEY}

    within_grace = client.post(
        "/events",
        json=event_payload(
            classroom["id"],
            lecture["id"],
            timestamp="2030-01-01T09:59:00Z",
        ),
        headers=headers,
    )
    beyond_grace = client.post(
        "/events",
        json=event_payload(
            classroom["id"],
            lecture["id"],
            timestamp="2030-01-01T09:54:00Z",
        ),
        headers=headers,
    )

    assert within_grace.status_code == 202
    assert within_grace.json()["reason"] == "timestamp_outside_lecture"
    assert beyond_grace.status_code == 422
    assert beyond_grace.json()["error"]["code"] == "TIMESTAMP_OUTSIDE_ALLOWED_WINDOW"


def test_confidence_and_event_type_validation_errors_are_safe(client, session_factory):
    classroom, _, lecture = create_camera_context(client, session_factory)
    headers = {"X-Camera-Key": CAMERA_KEY}
    base = event_payload(classroom["id"], lecture["id"])

    bad_confidence = client.post(
        "/events",
        json={**base, "confidence": 1.1},
        headers=headers,
    )
    bad_event_type = client.post(
        "/events",
        json={**base, "event_type": "RETURN"},
        headers=headers,
    )

    assert bad_confidence.status_code == 422
    assert bad_confidence.json()["error"]["code"] == "VALIDATION_ERROR"
    assert bad_event_type.status_code == 422
    assert bad_event_type.json()["error"]["code"] == "VALIDATION_ERROR"


def test_batch_ingests_events_atomically_and_is_idempotent(client, session_factory):
    classroom, _, lecture = create_camera_context(client, session_factory)
    payload = [
        event_payload(
            classroom["id"],
            lecture["id"],
            timestamp="2030-01-01T10:00:00Z",
        ),
        event_payload(
            classroom["id"],
            lecture["id"],
            event_type="EXIT",
            timestamp="2030-01-01T10:10:00Z",
        ),
    ]
    headers = {"X-Camera-Key": CAMERA_KEY}

    inserted = client.post("/events/batch", json=payload, headers=headers)
    assert inserted.status_code == 201
    assert inserted.json()["accepted_count"] == 2

    repeated = client.post("/events/batch", json=payload, headers=headers)
    assert repeated.status_code == 200
    assert repeated.json()["duplicate_count"] == 2
    assert client.get(f"/events?lecture_id={lecture['id']}").json()["total"] == 2


def test_batch_rolls_back_all_items_when_one_item_is_invalid(client, session_factory):
    classroom, _, lecture = create_camera_context(client, session_factory)
    payload = [
        event_payload(classroom["id"], lecture["id"]),
        event_payload(classroom["id"], 999),
    ]

    response = client.post(
        "/events/batch",
        json=payload,
        headers={"X-Camera-Key": CAMERA_KEY},
    )

    assert response.status_code == 404
    assert client.get(f"/events?lecture_id={lecture['id']}").json()["total"] == 0


def test_batch_rejects_empty_and_over_limit_payloads(client):
    empty = client.post("/events/batch", json=[])
    oversized = client.post(
        "/events/batch",
        json=[event_payload(1, 1) for _ in range(101)],
    )

    assert empty.status_code == 422
    assert empty.json()["error"]["code"] == "EMPTY_BATCH"
    assert oversized.status_code == 422
    assert oversized.json()["error"]["code"] == "BATCH_TOO_LARGE"


def test_camera_cannot_ingest_events_for_another_classroom(client, session_factory):
    create_camera_context(client, session_factory)
    another_room = client.post(
        "/classrooms",
        json={"name": "Room 102", "capacity": 30},
    ).json()
    class_group = client.get("/classes?limit=1").json()["items"][0]
    other_lecture = client.post(
        "/lectures",
        json={
            "classroom_id": another_room["id"],
            "class_id": class_group["id"],
            "subject": "Chemistry",
            "start_time": "2030-01-01T11:00:00Z",
            "end_time": "2030-01-01T12:00:00Z",
        },
    ).json()
    payload = event_payload(another_room["id"], other_lecture["id"])

    response = client.post(
        "/events",
        json=payload,
        headers={"X-Camera-Key": CAMERA_KEY},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CAMERA_CLASSROOM_MISMATCH"

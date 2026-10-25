from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.models import (
    ActivityWindow,
    ClassGroup,
    Classroom,
    Department,
    Lecture,
    Suggestion,
)


def create_live_lecture(session_factory):
    start = datetime(2030, 1, 1, 4, 30, tzinfo=UTC)
    with session_factory.begin() as session:
        department = Department(name="Activity Department")
        session.add(department)
        session.flush()
        class_group = ClassGroup(
            department_id=department.id,
            name="B.Tech",
            section="A",
            year=1,
        )
        classroom = Classroom(name="Activity Room", capacity=60)
        session.add_all([class_group, classroom])
        session.flush()
        lecture = Lecture(
            classroom_id=classroom.id,
            class_id=class_group.id,
            subject="Activity Test",
            start_time=start,
            end_time=start + timedelta(hours=1),
            status="live",
        )
        session.add(lecture)
        session.flush()
        return lecture.id


def activity_payload(lecture_id, minute, score=0.5):
    start = datetime(2030, 1, 1, 4, 30, tzinfo=UTC) + timedelta(minutes=minute)
    return {
        "lecture_id": lecture_id,
        "window_start": start.isoformat(),
        "window_end": (start + timedelta(minutes=1)).isoformat(),
        "movement_level": score,
        "inactivity_seconds": 60 * (1 - score),
        "front_facing_ratio": score,
        "audio_level_db_mean": -120 + score * 120,
        "voice_activity_ratio": score,
        "source": "camera+mic",
    }


def test_activity_endpoint_accepts_single_and_batch_idempotently(
    client, session_factory
):
    lecture_id = create_live_lecture(session_factory)
    payloads = [activity_payload(lecture_id, minute) for minute in range(2)]

    first = client.post("/activity", json=payloads)
    retry = client.post("/activity", json=payloads)
    single = client.post("/activity", json=activity_payload(lecture_id, 2))

    assert first.status_code == 200
    assert first.json()["stored_count"] == 2
    assert first.json()["duplicate_count"] == 0
    assert retry.json()["stored_count"] == 0
    assert retry.json()["duplicate_count"] == 2
    assert single.status_code == 200
    assert single.json()["stored_count"] == 1
    with session_factory() as session:
        stored = session.scalar(select(func.count(ActivityWindow.id)))
    assert stored == 3


def test_activity_endpoint_rejects_invalid_ranges_or_conflicting_retries(
    client, session_factory
):
    lecture_id = create_live_lecture(session_factory)
    invalid = activity_payload(lecture_id, 0, score=1.2)
    invalid_response = client.post("/activity", json=invalid)
    assert invalid_response.status_code == 422
    invalid_source = client.post(
        "/activity",
        json={**activity_payload(lecture_id, 1), "source": "Private Student Name"},
    )
    assert invalid_source.status_code == 422

    valid = activity_payload(lecture_id, 0)
    assert client.post("/activity", json=valid).status_code == 200
    conflict = {**valid, "movement_level": 0.8}
    conflict_response = client.post("/activity", json=conflict)
    assert conflict_response.status_code == 409
    assert conflict_response.json()["error"]["code"] == "ACTIVITY_WINDOW_CONFLICT"


def test_activity_endpoint_rejects_overlapping_windows_and_empty_batch(
    client, session_factory
):
    lecture_id = create_live_lecture(session_factory)
    first = activity_payload(lecture_id, 0)
    overlap = activity_payload(lecture_id, 0.5)
    assert client.post("/activity", json=first).status_code == 200
    overlap_response = client.post("/activity", json=overlap)
    empty_response = client.post("/activity", json=[])

    assert overlap_response.status_code == 409
    assert overlap_response.json()["error"]["code"] == "ACTIVITY_WINDOW_OVERLAP"
    assert empty_response.status_code == 422


def test_activity_batch_rolls_back_if_one_window_is_invalid(client, session_factory):
    lecture_id = create_live_lecture(session_factory)
    payloads = [
        activity_payload(lecture_id, 0),
        activity_payload(999, 1),
    ]

    response = client.post("/activity", json=payloads)

    assert response.status_code == 404
    with session_factory() as session:
        stored = session.scalar(select(func.count(ActivityWindow.id)))
    assert stored == 0


def test_engagement_and_suggestions_endpoints_are_aggregate_and_idempotent(
    client, session_factory
):
    lecture_id = create_live_lecture(session_factory)
    payloads = [
        activity_payload(lecture_id, minute, 0.9 if minute < 3 else 0.1)
        for minute in range(6)
    ]
    assert client.post("/activity", json=payloads).status_code == 200

    engagement = client.get(f"/lectures/{lecture_id}/engagement")
    first = client.get(f"/lectures/{lecture_id}/suggestions")
    second = client.get(f"/lectures/{lecture_id}/suggestions")

    assert engagement.status_code == 200
    engagement_data = engagement.json()
    assert engagement_data["estimate_note"] == "estimate based on observable indicators"
    assert engagement_data["decline"]["status"] == "detected"
    assert engagement_data["valid_window_count"] == 6
    assert first.status_code == second.status_code == 200
    assert [item["rule_id"] for item in first.json()] == [
        item["rule_id"] for item in second.json()
    ]
    assert all(item["status"] == "pending" for item in first.json())
    with session_factory() as session:
        stored_suggestions = session.scalar(
            select(func.count(Suggestion.id)).where(Suggestion.lecture_id == lecture_id)
        )
    assert stored_suggestions == len(first.json())


def test_engagement_endpoints_return_safe_not_found_errors(client):
    assert client.get("/lectures/999/engagement").status_code == 404
    assert client.get("/lectures/999/suggestions").status_code == 404

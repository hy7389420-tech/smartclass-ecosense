from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import AttendanceRecord, Camera, PresenceEvent
from app.services.camera_auth import hash_camera_key

CAMERA_KEY = "attendance-test-camera-key"


def create_live_context(client, session_factory):
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
    students = []
    for index, name in enumerate(("Student A", "Student B", "Student C"), start=1):
        students.append(
            client.post(
                "/students",
                json={
                    "student_code": f"STUDENT_{name[-1]}",
                    "roll_no": str(index),
                    "name": name,
                    "class_id": class_group["id"],
                },
            ).json()
        )

    lecture_start = datetime.now(UTC).replace(second=0, microsecond=0) - timedelta(
        hours=1
    )
    lecture_end = lecture_start + timedelta(hours=1)
    lecture = client.post(
        "/lectures",
        json={
            "classroom_id": classroom["id"],
            "class_id": class_group["id"],
            "subject": "Physics",
            "start_time": lecture_start.isoformat(),
            "end_time": lecture_end.isoformat(),
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
    return classroom, students, lecture, lecture_start, lecture_end


def send_event(client, classroom, lecture, student_code, event_type, at):
    return client.post(
        "/events",
        headers={"X-Camera-Key": CAMERA_KEY},
        json={
            "student_id": student_code,
            "classroom_id": classroom["id"],
            "lecture_id": lecture["id"],
            "event_type": event_type,
            "timestamp": at.isoformat(),
            "confidence": 0.9,
            "source": "camera",
            "presence_confirmed": True,
        },
    )


def test_lifecycle_attendance_dashboard_and_presence_history(client, session_factory):
    classroom, students, lecture, start, _end = create_live_context(
        client, session_factory
    )
    lecture_id = lecture["id"]

    started = client.post(f"/lectures/{lecture_id}/start")
    repeated_start = client.post(f"/lectures/{lecture_id}/start")
    assert started.status_code == 200
    assert started.json()["status"] == "live"
    assert repeated_start.status_code == 200
    assert client.get(f"/dashboard/{lecture_id}").json()["camera_status"] == (
        "Camera Offline"
    )

    assert (
        send_event(
            client,
            classroom,
            lecture,
            "STUDENT_A",
            "ENTRY",
            start + timedelta(minutes=2),
        ).status_code
        == 201
    )
    assert (
        send_event(
            client,
            classroom,
            lecture,
            "STUDENT_A",
            "EXIT",
            start + timedelta(minutes=30),
        ).status_code
        == 201
    )
    assert (
        send_event(
            client,
            classroom,
            lecture,
            "STUDENT_A",
            "ENTRY",
            start + timedelta(minutes=42),
        ).status_code
        == 201
    )
    assert (
        send_event(
            client,
            classroom,
            lecture,
            "STUDENT_B",
            "ENTRY",
            start + timedelta(minutes=20),
        ).status_code
        == 201
    )
    assert (
        send_event(
            client,
            classroom,
            lecture,
            "STUDENT_B",
            "EXIT",
            start + timedelta(minutes=30),
        ).status_code
        == 201
    )
    assert (
        send_event(
            client,
            classroom,
            lecture,
            "UNKNOWN",
            "ENTRY",
            start + timedelta(minutes=25),
        ).status_code
        == 202
    )

    live_dashboard = client.get(f"/dashboard/{lecture_id}")
    assert live_dashboard.status_code == 200
    assert live_dashboard.json()["camera_status"] == "Online"
    assert live_dashboard.json()["pending_review_count"] == 1

    ended = client.post(f"/lectures/{lecture_id}/end")
    repeated_end = client.post(f"/lectures/{lecture_id}/end")
    assert ended.status_code == 200
    assert repeated_end.status_code == 200
    assert ended.json()["finalized"] is True
    assert ended.json()["total_students"] == 3
    assert ended.json()["present"] == 2
    assert ended.json()["inside"] == 1
    assert ended.json()["outside"] == 1
    assert ended.json()["absent"] == 1
    assert ended.json()["occupancy_percent"] == 33.33

    student_a_record = next(
        row for row in ended.json()["records"] if row["student_code"] == "STUDENT_A"
    )
    assert student_a_record["inside_minutes"] == 46
    assert student_a_record["outside_minutes"] == 12
    assert student_a_record["return_count"] == 1

    dashboard = client.get(f"/dashboard/{lecture_id}").json()
    assert dashboard["cards"]["present"] == 2
    assert dashboard["cards"]["occupancy_percent"] == 33.33
    assert dashboard["pending_review_count"] == 1

    history = client.get(f"/students/{students[0]['id']}/presence-history")
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["inside_minutes"] == 46

    with session_factory() as session:
        records = list(
            session.scalars(
                select(AttendanceRecord).where(
                    AttendanceRecord.lecture_id == lecture_id
                )
            )
        )
        lifecycle_events = list(
            session.scalars(
                select(PresenceEvent).where(
                    PresenceEvent.lecture_id == lecture_id,
                    PresenceEvent.event_type.in_(("LECTURE_START", "LECTURE_END")),
                )
            )
        )
    assert len(records) == 3
    assert sorted(record.status for record in records) == [
        "ABSENT",
        "INSIDE",
        "OUTSIDE",
    ]
    assert len(lifecycle_events) == 2


def test_lifecycle_rejects_invalid_transition_and_unknown_lecture(
    client, session_factory
):
    missing = client.post("/lectures/999/start")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "LECTURE_NOT_FOUND"

    _, _, lecture, _, _ = create_live_context(client, session_factory)
    cannot_end_scheduled = client.post(f"/lectures/{lecture['id']}/end")
    assert cannot_end_scheduled.status_code == 409
    assert cannot_end_scheduled.json()["error"]["code"] == "LECTURE_CANNOT_END"


def test_camera_becomes_offline_when_last_event_is_stale(client, session_factory):
    _, _, lecture, _, _ = create_live_context(client, session_factory)
    with session_factory.begin() as session:
        camera = session.scalar(select(Camera))
        camera.status = "online"
        camera.last_seen_at = datetime.now(UTC) - timedelta(minutes=3)

    response = client.get(f"/dashboard/{lecture['id']}")

    assert response.status_code == 200
    assert response.json()["camera_status"] == "Camera Offline"

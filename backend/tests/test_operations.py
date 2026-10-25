from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models import (
    Alert,
    AuditLog,
    Camera,
    ClassGroup,
    Classroom,
    Department,
    Faculty,
    FacultyClassAssignment,
    Lecture,
    PresenceEvent,
    Student,
    User,
)
from app.services.auth import create_access_token, hash_password
from app.services.camera_auth import hash_camera_key
from app.services.operations import refresh_operational_alerts


@pytest.fixture
def operation_records(
    client, session_factory: sessionmaker[Session]
) -> dict[str, object]:
    start = datetime(2030, 1, 1, 9, tzinfo=UTC)
    with session_factory.begin() as session:
        admin = session.scalar(select(User).where(User.role == "ADMIN"))
        department = Department(name="Operations department")
        session.add(department)
        session.flush()
        class_group = ClassGroup(
            department_id=department.id,
            name="Operations class",
            section="A",
            year=1,
        )
        session.add(class_group)
        other_class = ClassGroup(
            department_id=department.id,
            name="Other operations class",
            section="B",
            year=2,
        )
        session.add(other_class)
        session.flush()
        student = Student(
            student_code="OPS-001",
            roll_no="1",
            name="Operations student",
            class_id=class_group.id,
        )
        other_student = Student(
            student_code="OPS-002",
            roll_no="2",
            name="Other class student",
            class_id=other_class.id,
        )
        session.add(student)
        faculty_user = User(
            email="operations-faculty@example.test",
            password_hash=hash_password("operations-faculty-password"),
            role="FACULTY",
            is_active=True,
        )
        session.add_all([student, other_student, faculty_user])
        session.flush()
        faculty = Faculty(user_id=faculty_user.id, department_id=department.id)
        session.add(faculty)
        session.flush()
        session.add(
            FacultyClassAssignment(faculty_id=faculty.id, class_id=class_group.id)
        )
        classroom = Classroom(name="Operations room", capacity=30)
        session.add(classroom)
        session.flush()
        lecture = Lecture(
            classroom_id=classroom.id,
            class_id=class_group.id,
            subject="Operations test",
            faculty_id=faculty.id,
            start_time=start,
            end_time=start + timedelta(hours=1),
            status="completed",
        )
        camera = Camera(
            classroom_id=classroom.id,
            name="Operations camera",
            api_key_hash=hash_camera_key("operations-camera-key"),
            status="online",
            last_seen_at=datetime.now(UTC),
        )
        session.add_all([lecture, camera])
        session.flush()
        return {
            "admin_id": admin.id,
            "faculty_id": faculty_user.id,
            "student_id": student.id,
            "other_student_id": other_student.id,
            "class_id": class_group.id,
            "classroom_id": classroom.id,
            "lecture_id": lecture.id,
            "camera_id": camera.id,
            "start": start,
            "faculty_token": create_access_token(faculty_user),
            "admin_token": create_access_token(admin),
        }


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_correction_adds_manual_correction_and_audit_and_recomputes(
    client, session_factory, operation_records
):
    with session_factory.begin() as session:
        original = PresenceEvent(
            lecture_id=operation_records["lecture_id"],
            classroom_id=operation_records["classroom_id"],
            student_id=None,
            student_code_raw="UNKNOWN",
            event_type="ENTRY",
            timestamp_utc=operation_records["start"] + timedelta(minutes=5),
            confidence=0.2,
            source="camera",
            flagged_for_review=True,
            review_status="needs_review",
            presence_confirmed=True,
        )
        session.add(original)
        session.flush()
        original_id = original.id

    response = client.post(
        f"/events/{original_id}/correct",
        headers=_auth(operation_records["faculty_token"]),
        json={
            "student_id": operation_records["student_id"],
            "event_type": "ENTRY",
            "timestamp": (
                operation_records["start"] + timedelta(minutes=5)
            ).isoformat(),
            "reason": "Verified against the instructor's manual record.",
        },
    )

    assert response.status_code == 200
    correction = response.json()["event"]
    assert correction["event_type"] == "MANUAL_CORRECTION"
    assert correction["correction_event_type"] == "ENTRY"
    assert correction["correction_of_event_id"] == original_id
    assert response.json()["attendance"]["records"][0]["inside_minutes"] == 55

    with session_factory() as session:
        unchanged_original = session.get(PresenceEvent, original_id)
        assert unchanged_original.flagged_for_review is True
        assert unchanged_original.review_status == "resolved"
        audit = session.scalar(
            select(AuditLog).where(AuditLog.entity_id == str(original_id))
        )
        assert audit is not None
        assert audit.actor_user_id == operation_records["faculty_id"]
        assert audit.reason == "Verified against the instructor's manual record."
        assert audit.before_json["flagged_for_review"] is True
        assert audit.after_json["event_type"] == "MANUAL_CORRECTION"


def test_correction_rejects_invalid_sequence_and_wrong_class_student(
    client, session_factory, operation_records
):
    with session_factory.begin() as session:
        original = PresenceEvent(
            lecture_id=operation_records["lecture_id"],
            classroom_id=operation_records["classroom_id"],
            student_id=None,
            student_code_raw="UNKNOWN",
            event_type="EXIT",
            timestamp_utc=operation_records["start"] + timedelta(minutes=10),
            confidence=0.2,
            source="camera",
            flagged_for_review=True,
            review_status="needs_review",
            presence_confirmed=True,
        )
        session.add(original)
        session.flush()
        event_id = original.id

    invalid_sequence = client.post(
        f"/events/{event_id}/correct",
        headers=_auth(operation_records["faculty_token"]),
        json={
            "student_id": operation_records["student_id"],
            "event_type": "EXIT",
            "timestamp": (
                operation_records["start"] + timedelta(minutes=10)
            ).isoformat(),
            "reason": "Checked the source record.",
        },
    )
    assert invalid_sequence.status_code == 422
    wrong_class = client.post(
        f"/events/{event_id}/correct",
        headers=_auth(operation_records["admin_token"]),
        json={
            "student_id": operation_records["other_student_id"],
            "event_type": "ENTRY",
            "timestamp": (
                operation_records["start"] + timedelta(minutes=10)
            ).isoformat(),
            "reason": "The student code was checked against the class roster.",
        },
    )
    assert wrong_class.status_code == 422
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AuditLog)) == 0
        original = session.get(PresenceEvent, event_id)
        assert original.review_status == "needs_review"


def test_correction_derives_return_when_entry_matches_exit_timestamp(
    client, session_factory, operation_records
):
    with session_factory.begin() as session:
        session.add_all(
            [
                PresenceEvent(
                    lecture_id=operation_records["lecture_id"],
                    classroom_id=operation_records["classroom_id"],
                    student_id=operation_records["student_id"],
                    student_code_raw="OPS-001",
                    event_type="ENTRY",
                    timestamp_utc=operation_records["start"] + timedelta(minutes=2),
                    confidence=1.0,
                    source="simulator",
                    flagged_for_review=False,
                    review_status="not_required",
                    presence_confirmed=True,
                ),
                PresenceEvent(
                    lecture_id=operation_records["lecture_id"],
                    classroom_id=operation_records["classroom_id"],
                    student_id=operation_records["student_id"],
                    student_code_raw="OPS-001",
                    event_type="EXIT",
                    timestamp_utc=operation_records["start"] + timedelta(minutes=10),
                    confidence=1.0,
                    source="simulator",
                    flagged_for_review=False,
                    review_status="not_required",
                    presence_confirmed=True,
                ),
                PresenceEvent(
                    lecture_id=operation_records["lecture_id"],
                    classroom_id=operation_records["classroom_id"],
                    student_id=None,
                    student_code_raw="UNKNOWN",
                    event_type="ENTRY",
                    timestamp_utc=operation_records["start"] + timedelta(minutes=11),
                    confidence=0.2,
                    source="camera",
                    flagged_for_review=True,
                    review_status="needs_review",
                    presence_confirmed=True,
                ),
            ]
        )
        session.flush()
        source_event_id = session.scalar(
            select(PresenceEvent.id)
            .where(PresenceEvent.student_code_raw == "UNKNOWN")
            .order_by(PresenceEvent.id.desc())
        )

    response = client.post(
        f"/events/{source_event_id}/correct",
        headers=_auth(operation_records["faculty_token"]),
        json={
            "student_id": operation_records["student_id"],
            "event_type": "ENTRY",
            "timestamp": (
                operation_records["start"] + timedelta(minutes=10)
            ).isoformat(),
            "reason": "Verified the exit and return times.",
        },
    )

    assert response.status_code == 200
    assert response.json()["event"]["correction_event_type"] == "RETURN"


def test_review_queue_and_resolution_are_audited(
    client, session_factory, operation_records
):
    with session_factory.begin() as session:
        event = PresenceEvent(
            lecture_id=operation_records["lecture_id"],
            classroom_id=operation_records["classroom_id"],
            student_id=None,
            student_code_raw="UNKNOWN",
            event_type="ENTRY",
            timestamp_utc=operation_records["start"] + timedelta(minutes=2),
            confidence=0.2,
            source="camera",
            flagged_for_review=True,
            review_status="needs_review",
            presence_confirmed=False,
        )
        session.add(event)
        session.flush()
        event_id = event.id

    queue = client.get(
        "/review/events",
        headers=_auth(operation_records["faculty_token"]),
    )
    assert queue.status_code == 200
    assert queue.json()["total"] == 1
    resolved = client.post(
        f"/review/events/{event_id}/resolve",
        headers=_auth(operation_records["faculty_token"]),
        json={"reason": "Reviewed; event remains excluded."},
    )
    assert resolved.status_code == 200
    assert resolved.json()["review_status"] == "resolved"
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AuditLog)) == 1


def test_camera_heartbeat_creates_and_resolves_offline_alert(
    client, session_factory, operation_records, monkeypatch
):
    settings = get_settings()
    monkeypatch.setattr(settings, "camera_offline_seconds", 60)
    with session_factory.begin() as session:
        camera = session.get(Camera, operation_records["camera_id"])
        camera.last_seen_at = datetime.now(UTC) - timedelta(minutes=2)
        camera.status = "online"

    alerts = client.get("/alerts")
    assert alerts.status_code == 200
    offline = [
        item for item in alerts.json()["items"] if item["kind"] == "camera_offline"
    ]
    assert len(offline) == 1

    heartbeat = client.post(
        f"/cameras/{operation_records['camera_id']}/heartbeat",
        headers={"X-Camera-Key": "operations-camera-key"},
    )
    assert heartbeat.status_code == 200
    assert heartbeat.json()["status"] == "online"
    with session_factory() as session:
        camera = session.get(Camera, operation_records["camera_id"])
        resolved_alert = session.get(Alert, offline[0]["id"])
        assert camera.status == "online"
        assert resolved_alert.resolved_at is not None


def test_camera_offline_alert_uses_fake_clock_and_is_deduplicated(
    session_factory, operation_records, monkeypatch
):
    settings = get_settings()
    monkeypatch.setattr(settings, "camera_offline_seconds", 60)
    fake_now = datetime(2030, 1, 1, 12, tzinfo=UTC)
    with session_factory.begin() as session:
        camera = session.get(Camera, operation_records["camera_id"])
        camera.last_seen_at = fake_now - timedelta(seconds=61)
        camera.status = "online"
        refresh_operational_alerts(session, fake_now)
        refresh_operational_alerts(session, fake_now + timedelta(seconds=1))
        alerts = session.scalars(
            select(Alert).where(
                Alert.kind == "camera_offline",
                Alert.camera_id == camera.id,
            )
        ).all()
        assert len(alerts) == 1
        assert camera.status == "offline"
        assert alerts[0].created_at.replace(tzinfo=UTC) == fake_now


def test_wrong_camera_key_cannot_send_heartbeat(client, operation_records):
    response = client.post(
        f"/cameras/{operation_records['camera_id']}/heartbeat",
        headers={"X-Camera-Key": "wrong-camera-key"},
    )
    assert response.status_code == 401


def test_threshold_alerts_are_neutral_deduplicated_and_admin_audited(
    client, session_factory, operation_records, monkeypatch
):
    settings = get_settings()
    monkeypatch.setattr(settings, "low_confidence_alert_min_events", 2)
    monkeypatch.setattr(settings, "unusual_exit_alert_min_events", 2)
    now = datetime.now(UTC)
    with session_factory.begin() as session:
        for index in range(4):
            is_low_confidence = index < 2
            session.add(
                PresenceEvent(
                    lecture_id=operation_records["lecture_id"],
                    classroom_id=operation_records["classroom_id"],
                    student_id=operation_records["student_id"],
                    student_code_raw="OPS-001",
                    event_type="EXIT",
                    timestamp_utc=now - timedelta(seconds=index + 1),
                    confidence=0.2 if is_low_confidence else 0.9,
                    source="camera",
                    flagged_for_review=is_low_confidence,
                    review_status="needs_review"
                    if is_low_confidence
                    else "not_required",
                    presence_confirmed=True,
                )
            )
        refresh_operational_alerts(session, now)

    first = client.get("/alerts")
    second = client.get("/alerts")
    kinds = [item["kind"] for item in first.json()["items"]]
    assert kinds.count("low_confidence_event_spike") == 1
    assert kinds.count("unusual_exit_activity") == 1
    assert first.json() == second.json()
    assert all(
        "Please verify" in item["message"]
        for item in first.json()["items"]
        if item["kind"] != "camera_offline"
    )

    audit_forbidden = client.get(
        "/audit-logs",
        headers=_auth(operation_records["faculty_token"]),
    )
    audit_allowed = client.get(
        "/audit-logs",
        headers=_auth(operation_records["admin_token"]),
    )
    assert audit_forbidden.status_code == 403
    assert audit_allowed.status_code == 200


def test_faculty_cannot_resolve_unscoped_alert(
    client, session_factory, operation_records
):
    with session_factory.begin() as session:
        alert = Alert(
            kind="system_notice",
            severity="low",
            message="System notice.",
        )
        session.add(alert)
        session.flush()
        alert_id = alert.id
    response = client.post(
        f"/alerts/{alert_id}/resolve",
        headers=_auth(operation_records["faculty_token"]),
        json={"reason": "Not in my class scope."},
    )
    assert response.status_code == 403

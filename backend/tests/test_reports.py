import csv
from datetime import UTC, datetime, timedelta
from io import StringIO

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models import (
    ActivityWindow,
    AttendanceRecord,
    AuditLog,
    ClassGroup,
    Classroom,
    Department,
    Insight,
    Lecture,
    PresenceEvent,
    Student,
    User,
)
from app.services.auth import create_access_token
from app.services.reports import run_retention


def _authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _records(
    session_factory: sessionmaker[Session],
) -> dict[str, object]:
    start = datetime(2030, 1, 1, 9, tzinfo=UTC)
    with session_factory.begin() as session:
        admin = session.scalar(select(User).where(User.role == "ADMIN"))
        if admin is None:
            admin = User(
                email="reports-admin@example.test",
                password_hash="unused-test-hash",
                role="ADMIN",
                is_active=True,
            )
            session.add(admin)
            session.flush()
        department = Department(name="Reports department")
        session.add(department)
        session.flush()
        class_group = ClassGroup(
            department_id=department.id,
            name="Reports class",
            section="A",
            year=1,
        )
        session.add(class_group)
        session.flush()
        first_student = Student(
            student_code="REPORT-001",
            roll_no="1",
            name='=HYPERLINK("https://invalid.test")',
            class_id=class_group.id,
        )
        second_student = Student(
            student_code="REPORT-002",
            roll_no="2",
            name="Report Student B",
            class_id=class_group.id,
        )
        session.add_all([first_student, second_student])
        session.flush()
        student_user = User(
            email="report-student@example.test",
            password_hash="unused-test-hash",
            role="STUDENT",
            student_id=first_student.id,
            is_active=True,
        )
        session.add(student_user)
        classroom = Classroom(name="Reports room", capacity=20)
        session.add(classroom)
        session.flush()
        lecture = Lecture(
            classroom_id=classroom.id,
            class_id=class_group.id,
            subject="Reports lecture",
            start_time=start,
            end_time=start + timedelta(hours=1),
            status="completed",
        )
        session.add(lecture)
        session.flush()
        session.add_all(
            [
                AttendanceRecord(
                    lecture_id=lecture.id,
                    student_id=first_student.id,
                    status="INSIDE",
                    inside_minutes=55,
                    outside_minutes=5,
                    exit_count=1,
                    return_count=1,
                ),
                AttendanceRecord(
                    lecture_id=lecture.id,
                    student_id=second_student.id,
                    status="ABSENT",
                    inside_minutes=0,
                    outside_minutes=0,
                    exit_count=0,
                    return_count=0,
                ),
                ActivityWindow(
                    lecture_id=lecture.id,
                    window_start=start,
                    window_end=start + timedelta(seconds=10),
                    movement_level=0.5,
                    inactivity_seconds=2,
                    front_facing_ratio=0.7,
                    audio_level_db_mean=-40,
                    voice_activity_ratio=0.3,
                    source="simulated",
                ),
            ]
        )
        session.flush()
        return {
            "admin_id": admin.id,
            "admin_token": create_access_token(admin),
            "student_token": create_access_token(student_user),
            "lecture_id": lecture.id,
            "student_id": first_student.id,
            "start": start,
        }


def test_session_report_json_csv_and_student_scope(
    client, session_factory, monkeypatch
):
    records = _records(session_factory)
    settings = get_settings()
    monkeypatch.setattr(settings, "local_timezone", "UTC")
    session_path = f"/reports/lectures/{records['lecture_id']}"

    staff = client.get(
        session_path,
        headers=_authorization(records["admin_token"]),
    )
    assert staff.status_code == 200
    assert staff.json()["attendance_summary"]["total_students"] == 2
    assert len(staff.json()["student_records"]) == 2
    assert staff.json()["student_records"][0]["status"] == "INSIDE"
    assert staff.json()["estimates_note"] == "estimate based on observable indicators"
    assert staff.json()["engagement"]["estimate_note"] == (
        "estimate based on observable indicators"
    )

    student = client.get(
        session_path,
        headers=_authorization(records["student_token"]),
    )
    assert student.status_code == 200
    assert student.json()["attendance_summary"] is None
    assert student.json()["engagement"] is None
    assert len(student.json()["student_records"]) == 1
    assert student.json()["student_records"][0]["student_id"] == records["student_id"]

    csv_response = client.get(
        f"{session_path}?format=csv",
        headers=_authorization(records["student_token"]),
    )
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert "STUDENT_ONLY" not in csv_response.text
    assert "'=HYPERLINK" in csv_response.text
    assert "estimate based on observable indicators" not in csv_response.text
    csv_rows = list(csv.DictReader(StringIO(csv_response.text)))
    assert len(csv_rows) == 1
    csv_header = next(csv.reader(StringIO(csv_response.text)))
    assert len(csv_header) == len(set(csv_header))


def test_daily_weekly_summary_json_and_csv(client, session_factory, monkeypatch):
    records = _records(session_factory)
    settings = get_settings()
    monkeypatch.setattr(settings, "local_timezone", "UTC")
    headers = _authorization(records["admin_token"])

    daily = client.get(
        "/reports/summaries?period=daily&date=2030-01-01",
        headers=headers,
    )
    weekly = client.get(
        "/reports/summaries?period=weekly&date=2030-01-01",
        headers=headers,
    )
    assert daily.status_code == weekly.status_code == 200
    assert daily.json()["lecture_count"] == 1
    assert daily.json()["rows"][0]["total_students"] == 2
    assert daily.json()["rows"][0]["absent"] == 1
    assert weekly.json()["start_date"] == "2029-12-31"
    assert weekly.json()["end_date"] == "2030-01-06"

    csv_response = client.get(
        "/reports/summaries?period=daily&date=2030-01-01&format=csv",
        headers=headers,
    )
    assert csv_response.status_code == 200
    assert "limitations_note" in csv_response.text
    assert "This report reflects recorded data only." in csv_response.text

    student_summary = client.get(
        "/reports/summaries?period=daily&date=2030-01-01",
        headers=_authorization(records["student_token"]),
    )
    assert student_summary.status_code == 200
    row = student_summary.json()["rows"][0]
    assert row["student_id"] == records["student_id"]
    assert row["total_students"] is None
    assert row["inside_minutes"] == 55


def test_retention_dry_run_and_delete_are_audited_and_scoped(
    session_factory, monkeypatch
):
    records = _records(session_factory)
    now = datetime(2030, 6, 1, tzinfo=UTC)
    cutoff = now - timedelta(days=90)
    with session_factory.begin() as session:
        lecture_id = records["lecture_id"]
        expired_event = PresenceEvent(
            lecture_id=lecture_id,
            classroom_id=1,
            student_id=records["student_id"],
            event_type="ENTRY",
            timestamp_utc=cutoff - timedelta(seconds=1),
            confidence=1.0,
            source="simulator",
            presence_confirmed=True,
        )
        session.add(expired_event)
        session.flush()
        session.add_all(
            [
                PresenceEvent(
                    lecture_id=lecture_id,
                    classroom_id=1,
                    student_id=records["student_id"],
                    event_type="MANUAL_CORRECTION",
                    correction_event_type="ENTRY",
                    correction_of_event_id=expired_event.id,
                    timestamp_utc=cutoff + timedelta(seconds=1),
                    confidence=1.0,
                    source="manual",
                    presence_confirmed=True,
                ),
                PresenceEvent(
                    lecture_id=lecture_id,
                    classroom_id=1,
                    student_id=records["student_id"],
                    event_type="EXIT",
                    timestamp_utc=cutoff,
                    confidence=1.0,
                    source="simulator",
                    presence_confirmed=True,
                ),
                ActivityWindow(
                    lecture_id=lecture_id,
                    window_start=cutoff - timedelta(seconds=20),
                    window_end=cutoff - timedelta(seconds=10),
                    source="simulated",
                ),
                ActivityWindow(
                    lecture_id=lecture_id,
                    window_start=cutoff - timedelta(seconds=5),
                    window_end=cutoff,
                    source="simulated",
                ),
                ActivityWindow(
                    lecture_id=lecture_id,
                    window_start=cutoff + timedelta(seconds=10),
                    window_end=cutoff + timedelta(seconds=20),
                    source="simulated",
                ),
                Insight(
                    lecture_id=lecture_id,
                    kind="old",
                    text="Older neutral report.",
                    created_at=cutoff - timedelta(seconds=1),
                ),
                Insight(
                    lecture_id=lecture_id,
                    kind="new",
                    text="Current neutral report.",
                    created_at=cutoff + timedelta(seconds=1),
                ),
                Insight(
                    lecture_id=lecture_id,
                    kind="cutoff",
                    text="At the retention cutoff.",
                    created_at=cutoff,
                ),
            ]
        )

    settings = get_settings()
    monkeypatch.setattr(settings, "retention_days", 90)
    with session_factory.begin() as session:
        preview = run_retention(
            session,
            actor_user_id=records["admin_id"],
            dry_run=True,
            now=now,
        )
    assert preview["candidates"] == {
        "presence_events": 1,
        "activity_windows": 2,
        "insights": 1,
    }
    assert preview["deleted"] == {
        "presence_events": 0,
        "activity_windows": 0,
        "insights": 0,
    }
    assert preview["correction_links_to_detach"] == 1
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PresenceEvent)) == 3
        assert session.scalar(select(func.count()).select_from(ActivityWindow)) == 4
        assert session.scalar(select(func.count()).select_from(Insight)) == 3

    with session_factory.begin() as session:
        deletion = run_retention(
            session,
            actor_user_id=records["admin_id"],
            dry_run=False,
            now=now,
        )
        assert deletion["deleted"] == preview["candidates"]

    with session_factory() as session:
        retained_correction = session.scalar(
            select(PresenceEvent).where(PresenceEvent.event_type == "MANUAL_CORRECTION")
        )
        assert retained_correction.correction_of_event_id is None
        assert session.scalar(select(func.count()).select_from(PresenceEvent)) == 2
        assert session.scalar(select(func.count()).select_from(ActivityWindow)) == 2
        assert session.scalar(select(func.count()).select_from(Insight)) == 2
        assert session.scalar(select(func.count()).select_from(AttendanceRecord)) == 2
        actions = set(session.scalars(select(AuditLog.action)))
        assert {"retention_dry_run", "retention_deleted"} <= actions


def test_retention_admin_endpoint_defaults_to_dry_run(client, session_factory):
    records = _records(session_factory)
    response = client.post(
        "/admin/retention/run",
        headers=_authorization(records["admin_token"]),
        json={},
    )
    assert response.status_code == 200
    assert response.json()["dry_run"] is True
    assert response.json()["retention_days"] == 90
    assert all(value == 0 for value in response.json()["deleted"].values())

    student_forbidden = client.post(
        "/admin/retention/run",
        headers=_authorization(records["student_token"]),
        json={"dry_run": False},
    )
    assert student_forbidden.status_code == 403

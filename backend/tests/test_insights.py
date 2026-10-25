import re
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.models import (
    AttendanceRecord,
    ClassGroup,
    Classroom,
    Department,
    Insight,
    Lecture,
    PresenceEvent,
    Student,
)
from app.services.neutral_text import BANNED_TERMS, assert_neutral_text


def create_insight_context(session_factory):
    start = datetime(2030, 1, 1, 4, 30, tzinfo=UTC)
    with session_factory.begin() as session:
        department = Department(name="Insights Department")
        session.add(department)
        session.flush()
        class_group = ClassGroup(
            department_id=department.id,
            name="B.Tech",
            section="I",
            year=1,
        )
        classroom = Classroom(name="Insights Room", capacity=10)
        session.add_all([class_group, classroom])
        session.flush()
        lecture = Lecture(
            classroom_id=classroom.id,
            class_id=class_group.id,
            subject="Insights Test",
            start_time=start,
            end_time=start + timedelta(minutes=60),
            status="completed",
        )
        students = [
            Student(
                student_code=f"INSIGHT_{index}",
                roll_no=str(index),
                name=f"Private Student {index}",
                class_id=class_group.id,
            )
            for index in range(3)
        ]
        session.add_all([lecture, *students])
        session.flush()
        session.add_all(
            [
                AttendanceRecord(
                    lecture_id=lecture.id,
                    student_id=student.id,
                    status="INSIDE",
                    inside_minutes=60,
                    outside_minutes=0,
                )
                for student in students
            ]
        )
        session.add_all(
            [
                PresenceEvent(
                    lecture_id=lecture.id,
                    classroom_id=classroom.id,
                    student_id=student.id,
                    student_code_raw=student.student_code,
                    event_type="EXIT",
                    timestamp_utc=start + timedelta(minutes=25, seconds=index),
                    confidence=1.0,
                    source="simulated",
                    flagged_for_review=False,
                    review_status="not_required",
                    presence_confirmed=True,
                )
                for index, student in enumerate(students)
            ]
        )
        return lecture.id


def test_insights_endpoint_regenerates_without_duplicates_and_keeps_text_neutral(
    client, session_factory
):
    lecture_id = create_insight_context(session_factory)

    first = client.get(f"/insights/{lecture_id}")
    second = client.get(f"/insights/{lecture_id}")

    assert first.status_code == 200
    assert second.status_code == 200
    first_rows = first.json()
    second_rows = second.json()
    assert [row["kind"] for row in first_rows] == [row["kind"] for row in second_rows]
    assert {row["kind"] for row in first_rows} == {
        "exit_spike",
        "outside_duration_trend_insufficient_history",
    }
    assert "10:25 and 10:30 (3 exits)" in first_rows[0]["text"]
    assert "Please verify." in first_rows[0]["text"]
    all_text = " ".join(row["text"].lower() for row in first_rows)
    assert not any(
        re.search(rf"\b{re.escape(term)}\b", all_text) for term in BANNED_TERMS
    )
    assert "Private Student" not in all_text
    assert first_rows[0]["evidence_json"]["exit_count"] == 3

    with session_factory() as session:
        stored_count = session.scalar(
            select(func.count(Insight.id)).where(Insight.lecture_id == lecture_id)
        )
    assert stored_count == len(first_rows)


def test_insights_endpoint_checks_lecture_state(client):
    response = client.get("/insights/999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "LECTURE_NOT_FOUND"


def test_insights_endpoint_requires_completed_lecture(client, session_factory):
    lecture_id = create_insight_context(session_factory)
    with session_factory.begin() as session:
        lecture = session.get(Lecture, lecture_id)
        assert lecture is not None
        lecture.status = "live"

    response = client.get(f"/insights/{lecture_id}")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LECTURE_NOT_COMPLETED"


def test_simulated_sample_is_eight_lectures_and_idempotent(client, session_factory):
    from sample_data.generate_sample import generate_sample_data

    with session_factory.begin() as session:
        summary = generate_sample_data(session, date(2030, 1, 10))
    assert summary["student_count"] == 60
    assert summary["lecture_count"] == 8

    with session_factory.begin() as session:
        repeated = generate_sample_data(session, date(2030, 1, 10))
        lecture_count = session.scalar(select(func.count(Lecture.id)))
        student_count = session.scalar(select(func.count(Student.id)))
        event_count = session.scalar(select(func.count(PresenceEvent.id)))
        spike_lecture = session.get(Lecture, summary["spike_lecture_id"])
        assert spike_lecture is not None
        spike_exits = session.scalar(
            select(func.count(PresenceEvent.id)).where(
                PresenceEvent.lecture_id == spike_lecture.id,
                PresenceEvent.event_type == "EXIT",
            )
        )

    assert repeated == summary
    assert lecture_count == 8
    assert student_count == 60
    assert event_count == 60 * 8 + 2 * (7 + 7)
    assert spike_exits == 7
    generated_insights = client.get(f"/insights/{repeated['spike_lecture_id']}")
    assert generated_insights.status_code == 200
    assert any(
        insight["kind"] == "exit_spike" and "(7 exits)" in insight["text"]
        for insight in generated_insights.json()
    )


def test_neutral_text_guard_rejects_prohibited_wording():
    assert assert_neutral_text("Unusual activity detected. Please verify.") == (
        "Unusual activity detected. Please verify."
    )
    with pytest.raises(ValueError, match="prohibited term"):
        assert_neutral_text("A student skipped the lecture.")

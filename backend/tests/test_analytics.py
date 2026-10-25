from datetime import UTC, date, datetime, timedelta

import pytest

from app.models import (
    AttendanceRecord,
    ClassGroup,
    Classroom,
    Lecture,
    PresenceEvent,
    Student,
)
from app.services.analytics import (
    OccupancyEvent,
    UnusedPeriod,
    aggregate_outside_duration,
    analyze_lecture,
    classify_utilization,
)


def test_hand_calculated_lecture_average_peak_and_utilization():
    start = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    events = [
        OccupancyEvent(student_id=student_id, event_type="ENTRY", timestamp=start)
        for student_id in range(1, 43)
    ]

    result = analyze_lecture(events, start, start + timedelta(minutes=60), capacity=60)

    assert result.average_occupancy == 42
    assert result.peak_occupancy == 42
    assert result.peak_time == start
    assert result.utilization_percent == 70
    assert result.exit_count == 0
    assert len(result.occupancy_by_minute) == 60
    assert all(bucket.average_occupied == 42 for bucket in result.occupancy_by_minute)
    assert result.unused_periods == ()


def test_empty_lecture_and_one_minute_lecture_are_handled():
    start = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    empty = analyze_lecture([], start, start + timedelta(minutes=10), capacity=60)
    assert empty.average_occupancy == 0
    assert empty.peak_occupancy == 0
    assert empty.peak_time is None
    assert empty.utilization_percent == 0
    assert empty.unused_periods == (
        UnusedPeriod(start=start, end=start + timedelta(minutes=10)),
    )

    one_minute = analyze_lecture(
        [
            OccupancyEvent(1, "ENTRY", start),
            OccupancyEvent(1, "EXIT", start + timedelta(seconds=30)),
        ],
        start,
        start + timedelta(minutes=1),
        capacity=60,
    )
    assert one_minute.average_occupancy == 0.5
    assert one_minute.peak_occupancy == 1
    assert one_minute.exit_count == 1
    assert one_minute.outside_minutes == 0.5
    assert one_minute.occupancy_by_minute[0].average_occupied == 0.5
    assert one_minute.unused_periods == ()


def test_events_are_clipped_to_lecture_window_and_timestamps_need_timezone():
    start = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    result = analyze_lecture(
        [
            OccupancyEvent(1, "ENTRY", start - timedelta(seconds=1)),
            OccupancyEvent(1, "ENTRY", start),
            OccupancyEvent(1, "EXIT", start + timedelta(minutes=1)),
        ],
        start,
        start + timedelta(minutes=1),
        capacity=10,
    )
    assert result.average_occupancy == 1
    assert result.exit_count == 0

    with pytest.raises(ValueError, match="event timestamp must include a timezone"):
        analyze_lecture(
            [OccupancyEvent(1, "ENTRY", start.replace(tzinfo=None))],
            start,
            start + timedelta(minutes=1),
            capacity=10,
        )
    with pytest.raises(ValueError, match="Unsupported occupancy event type"):
        analyze_lecture(
            [OccupancyEvent(1, "LECTURE_START", start)],
            start,
            start + timedelta(minutes=1),
            capacity=10,
        )


def test_invalid_time_window_or_capacity_is_rejected():
    start = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="lecture_end must be after"):
        analyze_lecture([], start, start, capacity=60)

    with pytest.raises(ValueError, match="capacity must be positive"):
        analyze_lecture([], start, start + timedelta(minutes=1), capacity=0)


def test_utilization_cutoff_boundaries_and_no_data():
    assert classify_utilization(39.99) == "underutilized"
    assert classify_utilization(40) == "well_utilized"
    assert classify_utilization(90) == "well_utilized"
    assert classify_utilization(90.01) == "overutilized"
    assert classify_utilization(0, has_data=False) == "no_data"


def test_outside_duration_periods_use_day_week_and_month_starts():
    rows = [
        (datetime(2030, 1, 1, 10, tzinfo=UTC), 12, 10),
        (datetime(2030, 1, 2, 10, tzinfo=UTC), 8, 10),
        (datetime(2030, 1, 8, 10, tzinfo=UTC), 5, 11),
    ]

    assert aggregate_outside_duration(rows, "day") == [
        (date(2030, 1, 1), 12, 1),
        (date(2030, 1, 2), 8, 1),
        (date(2030, 1, 8), 5, 1),
    ]
    assert aggregate_outside_duration(rows, "week") == [
        (date(2029, 12, 31), 20, 1),
        (date(2030, 1, 7), 5, 1),
    ]
    assert aggregate_outside_duration(rows, "month") == [
        (date(2030, 1, 1), 25, 2),
    ]


def create_analytics_context(client, session_factory):
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
        db_class = session.get(ClassGroup, class_group["id"])
        db_room = session.get(Classroom, classroom["id"])
        assert db_class is not None
        assert db_room is not None
        students = [
            Student(
                student_code=f"STUDENT_{student_id:02}",
                roll_no=str(student_id),
                name=f"Student {student_id}",
                class_id=db_class.id,
            )
            for student_id in range(1, 43)
        ]
        session.add_all(students)
        session.flush()
        session.add_all(
            PresenceEvent(
                lecture_id=lecture["id"],
                classroom_id=db_room.id,
                student_id=student.id,
                student_code_raw=student.student_code,
                event_type="ENTRY",
                timestamp_utc=datetime(2030, 1, 1, 10, tzinfo=UTC),
                confidence=0.9,
                source="simulator",
                presence_confirmed=True,
            )
            for student in students
        )
        db_lecture = session.get(Lecture, lecture["id"])
        assert db_lecture is not None
        db_lecture.status = "completed"
        session.add(
            AttendanceRecord(
                lecture_id=db_lecture.id,
                student_id=students[0].id,
                status="PARTIAL",
                inside_minutes=46,
                outside_minutes=12,
                exit_count=1,
                return_count=1,
            )
        )
    return classroom, lecture


def test_analytics_endpoints_hand_check_and_simulated_suggestion(
    client, session_factory
):
    classroom, lecture = create_analytics_context(client, session_factory)

    lecture_response = client.get(f"/analytics/lecture/{lecture['id']}")
    assert lecture_response.status_code == 200
    assert lecture_response.json()["average_occupancy"] == 42
    assert lecture_response.json()["peak_occupancy"] == 42
    assert lecture_response.json()["utilization_percent"] == 70
    assert lecture_response.json()["enrolled_students"] == 42
    assert lecture_response.json()["occupancy_by_minute"][0]["average_occupied"] == 42

    utilization = client.get(
        f"/analytics/classroom/{classroom['id']}/utilization"
        "?from=2030-01-01&to=2030-01-01"
    )
    assert utilization.status_code == 200
    result = utilization.json()
    assert result["lecture_count"] == 1
    assert result["average_occupancy"] == 42
    assert result["utilization_percent"] == 70
    assert result["classification"] == "well_utilized"
    assert result["simulated"] is True
    assert (
        "occupancy data can support resource optimization"
        in result["suggestion"].lower()
    )
    assert "energy" not in result["suggestion"].lower()

    outside = client.get("/analytics/outside-duration?period=week")
    assert outside.status_code == 200
    assert outside.json()["total_outside_minutes"] == 12
    assert outside.json()["buckets"] == [
        {
            "period_start": "2029-12-31",
            "lecture_count": 1,
            "outside_minutes": 12,
        }
    ]


def test_analytics_endpoints_report_no_data_and_validate_ranges(client):
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
    not_completed = client.get(f"/analytics/lecture/{lecture['id']}")
    assert not_completed.status_code == 409
    assert not_completed.json()["error"]["code"] == "LECTURE_NOT_COMPLETED"

    no_data = client.get(f"/analytics/classroom/{classroom['id']}/utilization")
    assert no_data.status_code == 200
    assert no_data.json()["classification"] == "no_data"
    assert no_data.json()["simulated"] is True
    assert no_data.json()["lecture_count"] == 0

    reversed_range = client.get(
        f"/analytics/classroom/{classroom['id']}/utilization"
        "?from=2030-01-02&to=2030-01-01"
    )
    assert reversed_range.status_code == 422
    assert reversed_range.json()["error"]["code"] == "INVALID_DATE_RANGE"

    invalid_period = client.get("/analytics/outside-duration?period=year")
    assert invalid_period.status_code == 422
    missing_classroom = client.get("/analytics/classroom/999/utilization")
    assert missing_classroom.status_code == 404

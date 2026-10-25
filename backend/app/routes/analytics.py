from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.config import get_settings
from app.core.errors import ApiError
from app.models import (
    AttendanceRecord,
    Classroom,
    Lecture,
    PresenceEvent,
    Student,
)
from app.routes.dependencies import DatabaseSession
from app.schemas.analytics import (
    ClassroomUtilizationRead,
    LectureAnalyticsRead,
    OccupancyMinuteRead,
    OutsideDurationBucket,
    OutsideDurationRead,
    UnusedPeriodRead,
)
from app.schemas.resources import normalize_output_datetime
from app.services.analytics import (
    LectureAnalytics,
    OccupancyEvent,
    aggregate_outside_duration,
    analyze_lecture,
    classify_utilization,
    utilization_suggestion,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])
OutsidePeriod = Literal["day", "week", "month"]


def _lecture_analytics(session: DatabaseSession, lecture: Lecture, capacity: int):
    enrolled_ids = list(
        session.scalars(
            select(Student.id).where(
                Student.class_id == lecture.class_id,
                Student.is_active.is_(True),
            )
        )
    )
    if not enrolled_ids:
        return analyze_lecture(
            [],
            normalize_output_datetime(lecture.start_time),
            normalize_output_datetime(lecture.end_time),
            capacity,
        )
    events = list(
        session.scalars(
            select(PresenceEvent)
            .where(
                PresenceEvent.lecture_id == lecture.id,
                PresenceEvent.student_id.in_(enrolled_ids),
                PresenceEvent.flagged_for_review.is_(False),
                PresenceEvent.presence_confirmed.is_(True),
                PresenceEvent.event_type.in_(("ENTRY", "EXIT", "RETURN")),
            )
            .order_by(PresenceEvent.timestamp_utc, PresenceEvent.id)
        )
    )
    analytics = analyze_lecture(
        [
            OccupancyEvent(
                student_id=event.student_id,
                event_type=event.event_type,
                timestamp=normalize_output_datetime(event.timestamp_utc),
            )
            for event in events
            if event.student_id is not None
        ],
        normalize_output_datetime(lecture.start_time),
        normalize_output_datetime(lecture.end_time),
        capacity,
    )
    return analytics


@router.get("/lecture/{lecture_id}", response_model=LectureAnalyticsRead)
def read_lecture_analytics(lecture_id: int, session: DatabaseSession):
    lecture = session.get(Lecture, lecture_id)
    if lecture is None:
        raise ApiError(404, "LECTURE_NOT_FOUND", "Lecture was not found.")
    if lecture.status != "completed":
        raise ApiError(
            409,
            "LECTURE_NOT_COMPLETED",
            "Lecture analytics are available after the lecture is completed.",
        )
    classroom = session.get(Classroom, lecture.classroom_id)
    if classroom is None:
        raise ApiError(404, "CLASSROOM_NOT_FOUND", "Classroom was not found.")
    analytics = _lecture_analytics(session, lecture, classroom.capacity)
    enrolled_count = len(
        list(
            session.scalars(
                select(Student.id).where(
                    Student.class_id == lecture.class_id,
                    Student.is_active.is_(True),
                )
            )
        )
    )
    return LectureAnalyticsRead(
        lecture_id=lecture.id,
        classroom_id=lecture.classroom_id,
        capacity=classroom.capacity,
        enrolled_students=enrolled_count,
        average_occupancy=analytics.average_occupancy,
        peak_occupancy=analytics.peak_occupancy,
        peak_time=analytics.peak_time,
        utilization_percent=analytics.utilization_percent,
        exit_count=analytics.exit_count,
        outside_minutes=analytics.outside_minutes,
        occupancy_by_minute=[
            OccupancyMinuteRead(
                timestamp=bucket.timestamp,
                average_occupied=bucket.average_occupied,
            )
            for bucket in analytics.occupancy_by_minute
        ],
        unused_periods=[
            UnusedPeriodRead(
                lecture_id=lecture.id,
                start=period.start,
                end=period.end,
            )
            for period in analytics.unused_periods
        ],
    )


@router.get(
    "/classroom/{classroom_id}/utilization",
    response_model=ClassroomUtilizationRead,
)
def read_classroom_utilization(
    classroom_id: int,
    session: DatabaseSession,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
):
    classroom = session.get(Classroom, classroom_id)
    if classroom is None:
        raise ApiError(404, "CLASSROOM_NOT_FOUND", "Classroom was not found.")
    if from_date is not None and to_date is not None and from_date > to_date:
        raise ApiError(422, "INVALID_DATE_RANGE", "'from' must be on or before 'to'.")

    lectures = list(
        session.scalars(
            select(Lecture)
            .where(Lecture.classroom_id == classroom_id, Lecture.status == "completed")
            .order_by(Lecture.start_time, Lecture.id)
        )
    )
    if from_date is not None:
        lectures = [
            lecture
            for lecture in lectures
            if normalize_output_datetime(lecture.start_time).date() >= from_date
        ]
    if to_date is not None:
        lectures = [
            lecture
            for lecture in lectures
            if normalize_output_datetime(lecture.start_time).date() <= to_date
        ]

    results = [
        (lecture, _lecture_analytics(session, lecture, classroom.capacity))
        for lecture in lectures
    ]
    total_seconds = sum(item.total_duration_seconds for _, item in results)
    occupied_person_seconds = sum(item.occupied_person_seconds for _, item in results)
    average_occupancy = (
        occupied_person_seconds / total_seconds if total_seconds else 0.0
    )
    utilization_percent = (
        round(average_occupancy / classroom.capacity * 100, 2) if total_seconds else 0.0
    )
    peak_lecture: tuple[Lecture, LectureAnalytics] | None = max(
        results,
        key=lambda pair: pair[1].peak_occupancy,
        default=None,
    )
    peak_occupancy = peak_lecture[1].peak_occupancy if peak_lecture else 0
    peak_time = peak_lecture[1].peak_time if peak_lecture else None
    unused_periods = [
        UnusedPeriodRead(
            lecture_id=lecture.id,
            start=period.start,
            end=period.end,
        )
        for lecture, result in results
        for period in result.unused_periods
    ]
    unused_seconds = sum(
        (period.end - period.start).total_seconds()
        for lecture, result in results
        for period in result.unused_periods
    )
    settings = get_settings()
    classification = classify_utilization(
        utilization_percent,
        settings.underutilized_cutoff_percent,
        settings.overutilized_cutoff_percent,
        has_data=bool(results),
    )
    return ClassroomUtilizationRead(
        classroom_id=classroom.id,
        classroom_name=classroom.name,
        capacity=classroom.capacity,
        from_date=from_date,
        to_date=to_date,
        lecture_count=len(results),
        average_occupancy=round(average_occupancy, 4),
        peak_occupancy=peak_occupancy,
        peak_time=peak_time,
        utilization_percent=utilization_percent,
        exit_count=sum(item.exit_count for _, item in results),
        unused_minutes=round(unused_seconds / 60, 2),
        unused_periods=unused_periods,
        classification=classification,
        simulated=True,
        suggestion=utilization_suggestion(
            classroom.name, utilization_percent, classification
        ),
    )


@router.get("/outside-duration", response_model=OutsideDurationRead)
def read_outside_duration(
    session: DatabaseSession,
    period: Annotated[OutsidePeriod, Query()] = "day",
):
    rows = session.execute(
        select(Lecture.start_time, AttendanceRecord.outside_minutes, Lecture.id)
        .join(AttendanceRecord, AttendanceRecord.lecture_id == Lecture.id)
        .where(Lecture.status == "completed")
        .order_by(Lecture.start_time, Lecture.id)
    ).all()
    aggregates = aggregate_outside_duration(
        [
            (normalize_output_datetime(start), outside_minutes, lecture_id)
            for start, outside_minutes, lecture_id in rows
        ],
        period,
    )
    buckets = [
        OutsideDurationBucket(
            period_start=period_start,
            outside_minutes=outside_minutes,
            lecture_count=lecture_count,
        )
        for period_start, outside_minutes, lecture_count in aggregates
    ]
    return OutsideDurationRead(
        period=period,
        total_outside_minutes=round(
            sum(bucket.outside_minutes for bucket in buckets), 2
        ),
        buckets=buckets,
    )

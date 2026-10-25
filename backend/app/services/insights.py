from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.errors import ApiError
from app.models import (
    AttendanceRecord,
    Insight,
    Lecture,
    PresenceEvent,
    Student,
)
from app.schemas.resources import normalize_output_datetime
from app.services.anomaly import ExitEvent, detect_exit_spikes
from app.services.neutral_text import assert_neutral_text
from app.services.trends import OutsideDurationTrend, compare_outside_duration


def regenerate_lecture_insights(session: Session, lecture_id: int) -> list[Insight]:
    lecture = session.get(Lecture, lecture_id)
    if lecture is None:
        raise ApiError(404, "LECTURE_NOT_FOUND", "Lecture was not found.")
    if lecture.status != "completed":
        raise ApiError(
            409,
            "LECTURE_NOT_COMPLETED",
            "Insights are available after the lecture is completed.",
        )

    settings = get_settings()
    enrolled_students = list(
        session.scalars(
            select(Student).where(
                Student.class_id == lecture.class_id,
                Student.is_active.is_(True),
            )
        )
    )
    enrolled_ids = {student.id for student in enrolled_students}
    valid_events = list(
        session.scalars(
            select(PresenceEvent)
            .where(
                PresenceEvent.lecture_id == lecture.id,
                PresenceEvent.flagged_for_review.is_(False),
                PresenceEvent.presence_confirmed.is_(True),
                PresenceEvent.student_id.in_(enrolled_ids) if enrolled_ids else False,
                PresenceEvent.event_type.in_(("ENTRY", "EXIT", "RETURN")),
            )
            .order_by(PresenceEvent.timestamp_utc, PresenceEvent.id)
        )
    )
    lecture_start = normalize_output_datetime(lecture.start_time)
    lecture_end = normalize_output_datetime(lecture.end_time)
    spikes = detect_exit_spikes(
        [
            ExitEvent(normalize_output_datetime(event.timestamp_utc))
            for event in valid_events
            if event.event_type == "EXIT"
        ],
        lecture_start,
        lecture_end,
        window_minutes=settings.insight_window_minutes,
        min_exits=settings.insight_min_exits,
        min_buckets=settings.insight_min_buckets,
    )

    generated: list[Insight] = []
    timezone = ZoneInfo(settings.local_timezone)
    for spike in spikes:
        generated.append(
            Insight(
                lecture_id=lecture.id,
                kind="exit_spike",
                text=assert_neutral_text(
                    "Unusual activity detected between "
                    f"{_format_time(spike.start, timezone)} and "
                    f"{_format_time(spike.end, timezone)} "
                    f"({spike.exit_count} exits). Please verify."
                ),
                evidence_json={
                    "window_start": spike.start.isoformat(),
                    "window_end": spike.end.isoformat(),
                    "exit_count": spike.exit_count,
                    "mean_exits_per_window": spike.mean_exits,
                    "standard_deviation": spike.standard_deviation,
                    "window_minutes": settings.insight_window_minutes,
                },
            )
        )

    trend = _lecture_outside_trend(session, lecture, enrolled_students, settings)
    if trend.status == "insufficient_history":
        generated.append(
            Insight(
                lecture_id=lecture.id,
                kind="outside_duration_trend_insufficient_history",
                text=assert_neutral_text(
                    "Not enough historical data to compare average outside "
                    "duration. Please verify after more completed lectures."
                ),
                evidence_json={
                    "history_count": trend.history_count,
                    "history_required": trend.history_required,
                    "current_average_minutes": trend.current_average_minutes,
                },
            )
        )
    elif trend.status == "higher":
        generated.append(
            Insight(
                lecture_id=lecture.id,
                kind="outside_duration_trend",
                text=assert_neutral_text(
                    "Average outside duration is higher than the previous "
                    f"{trend.history_count} lectures "
                    f"({trend.current_average_minutes:.2f} vs "
                    f"{trend.previous_average_minutes:.2f} minutes per enrolled "
                    "student). Please verify."
                ),
                evidence_json={
                    "current_average_minutes_per_student": trend.current_average_minutes,
                    "previous_average_minutes_per_student": trend.previous_average_minutes,
                    "history_count": trend.history_count,
                },
            )
        )

    session.execute(delete(Insight).where(Insight.lecture_id == lecture.id))
    session.add_all(generated)
    session.flush()
    return generated


def _lecture_outside_trend(
    session: Session,
    lecture: Lecture,
    enrolled_students: list[Student],
    settings: Settings,
) -> OutsideDurationTrend:
    current_ids = [student.id for student in enrolled_students]
    current_records = list(
        session.scalars(
            select(AttendanceRecord).where(
                AttendanceRecord.lecture_id == lecture.id,
                AttendanceRecord.student_id.in_(current_ids) if current_ids else False,
            )
        )
    )
    current_outside = (
        [record.outside_minutes for record in current_records]
        if current_ids and len(current_records) == len(current_ids)
        else []
    )

    previous_lectures = list(
        session.scalars(
            select(Lecture)
            .where(
                Lecture.class_id == lecture.class_id,
                Lecture.status == "completed",
                Lecture.start_time < lecture.start_time,
                Lecture.id != lecture.id,
            )
            .order_by(Lecture.start_time.desc(), Lecture.id.desc())
            .limit(settings.insight_history_lectures)
        )
    )
    previous_averages: list[float] = []
    for previous in previous_lectures:
        previous_students = list(
            session.scalars(
                select(Student.id).where(
                    Student.class_id == previous.class_id,
                    Student.is_active.is_(True),
                )
            )
        )
        if not previous_students:
            continue
        outside_total, record_count = session.execute(
            select(
                func.coalesce(func.sum(AttendanceRecord.outside_minutes), 0),
                func.count(AttendanceRecord.id),
            ).where(
                AttendanceRecord.lecture_id == previous.id,
                AttendanceRecord.student_id.in_(previous_students),
            )
        ).one()
        if record_count == len(previous_students):
            previous_averages.append(float(outside_total or 0) / len(previous_students))

    return compare_outside_duration(
        current_outside,
        previous_averages,
        min_history=settings.insight_min_history,
    )


def _format_time(value: datetime, timezone: ZoneInfo) -> str:
    return value.astimezone(timezone).strftime("%H:%M")

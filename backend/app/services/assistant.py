import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    AttendanceRecord,
    ClassGroup,
    Classroom,
    Lecture,
    PresenceEvent,
    Student,
    User,
)
from app.schemas.resources import normalize_output_datetime
from app.services.access import class_scope
from app.services.analytics import OccupancyEvent, analyze_lecture, classify_utilization
from app.services.anomaly import ExitEvent, detect_exit_spikes
from app.services.neutral_text import assert_neutral_text

AssistantIntent = Literal[
    "highest_outside_by_class",
    "weekly_utilization",
    "underutilized_rooms",
    "unusual_activity_yesterday",
    "room_average_occupancy",
    "monthly_comparison",
]

_PRIVATE_DATA_PATTERNS = (
    r"\b(?:student|learner)\s+(?:name|names|id|code|record|records|attendance)\b",
    r"\b(?:student|learner)\s+(?:data|details)\b",
    r"\b(?:all|every)\s+(?:student|learner)\b.*\b(?:data|details|records|names)\b",
    r"\broll(?:\s+number|\s+no\.?)\b",
    r"\b(?:individual|student-wise|per student|each student)\b",
    r"\b(?:who|which student)\b",
    r"\b(?:everyone|everybody)(?:'s)?\s+(?:data|records|attendance|names)\b",
    r"\bshow\s+(?:me\s+)?(?:all|every)\s+students?\b",
    r"\bignore\s+(?:all\s+)?(?:previous\s+)?instructions\b",
)


@dataclass(frozen=True, slots=True)
class AssistantResult:
    status: Literal["answered", "refused"]
    intent: AssistantIntent | None
    answer: str

    def __post_init__(self) -> None:
        assert_neutral_text(self.answer)


@dataclass(frozen=True, slots=True)
class LectureMetrics:
    lecture: Lecture
    classroom: Classroom
    average_occupancy: float
    utilization_percent: float
    outside_minutes: float
    occupied_person_seconds: float
    total_duration_seconds: float


def answer_question(session: Session, user: User, question: str) -> AssistantResult:
    normalized = _normalize_question(question)
    if any(re.search(pattern, normalized) for pattern in _PRIVATE_DATA_PATTERNS):
        return AssistantResult(
            "refused",
            None,
            "I can only provide aggregate class and room information, not "
            "individual student data.",
        )

    intent = _detect_intent(normalized)
    if intent is None:
        return AssistantResult(
            "refused",
            None,
            "I could not match that to a supported aggregate question. Ask about "
            "class outside-time averages, weekly room utilization, underutilized "
            "rooms, unusual activity yesterday, a room's average occupancy, or "
            "this-month versus last-month trends.",
        )

    class_ids = list(session.scalars(class_scope(session, user)))
    if not class_ids:
        return AssistantResult(
            "answered", intent, "No class data is available in your permitted scope."
        )

    if intent == "highest_outside_by_class":
        return _highest_outside_by_class(session, class_ids, intent)
    if intent == "weekly_utilization":
        return _weekly_utilization(session, class_ids, intent)
    if intent == "underutilized_rooms":
        return _underutilized_rooms(session, class_ids, intent)
    if intent == "unusual_activity_yesterday":
        return _unusual_activity_yesterday(session, class_ids, intent)
    if intent == "room_average_occupancy":
        return _room_average_occupancy(session, class_ids, normalized, intent)
    return _monthly_comparison(session, class_ids, intent)


def _detect_intent(question: str) -> AssistantIntent | None:
    question = _normalize_question(question)
    if (
        "outside" in question
        and ("highest" in question or "most" in question)
        and ("class" in question or "section" in question)
    ):
        return "highest_outside_by_class"
    if (
        "unusual activity" in question or "exit spike" in question
    ) and "yesterday" in question:
        return "unusual_activity_yesterday"
    if "utilization" in question and "this week" in question:
        return "weekly_utilization"
    if "underutilized" in question or "under utilized" in question:
        return "underutilized_rooms"
    if (
        "occupancy" in question
        and "room" in question
        and re.search(r"\b(?:average|avg)\b", question)
    ):
        return "room_average_occupancy"
    if (
        "this month" in question
        and "last month" in question
        and ("compare" in question or "comparison" in question)
    ):
        return "monthly_comparison"
    return None


def _normalize_question(question: str) -> str:
    normalized = question.casefold().replace("’", "'").replace("-", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def _highest_outside_by_class(
    session: Session, class_ids: list[int], intent: AssistantIntent
) -> AssistantResult:
    rows = session.execute(
        select(
            ClassGroup.name,
            ClassGroup.section,
            func.avg(AttendanceRecord.outside_minutes),
            func.count(AttendanceRecord.id),
        )
        .join(Lecture, Lecture.class_id == ClassGroup.id)
        .join(AttendanceRecord, AttendanceRecord.lecture_id == Lecture.id)
        .join(Student, Student.id == AttendanceRecord.student_id)
        .where(
            ClassGroup.id.in_(class_ids),
            Lecture.status == "completed",
            Student.is_active.is_(True),
        )
        .group_by(ClassGroup.id, ClassGroup.name, ClassGroup.section)
        .order_by(func.avg(AttendanceRecord.outside_minutes).desc(), ClassGroup.id)
    ).all()
    if not rows:
        return AssistantResult(
            "answered",
            intent,
            "No completed attendance data is available in your scope.",
        )
    name, section, average_minutes, _ = rows[0]
    class_label = f"{name} ({section})" if section else name
    return AssistantResult(
        "answered",
        intent,
        f"{class_label} has the highest average outside time: "
        f"{float(average_minutes or 0):.2f} minutes per active student record "
        "across completed lectures. This is an aggregate estimate; please verify "
        "the underlying records.",
    )


def _weekly_utilization(
    session: Session, class_ids: list[int], intent: AssistantIntent
) -> AssistantResult:
    timezone = ZoneInfo(get_settings().local_timezone)
    today = datetime.now(timezone).date()
    start_date = today - timedelta(days=today.weekday())
    metrics = _lecture_metrics(
        session,
        class_ids,
        _local_midnight(start_date, timezone),
        _local_midnight(start_date + timedelta(days=7), timezone),
    )
    by_room = _metrics_by_room(metrics)
    if not by_room:
        return AssistantResult(
            "answered",
            intent,
            "No completed lecture occupancy data is available this week.",
        )
    summary = ", ".join(
        f"{room_name}: {utilization:.1f}%"
        for room_name, (utilization, _, _) in sorted(by_room.items())
    )
    return AssistantResult(
        "answered",
        intent,
        f"Completed-lecture utilization this week (through {today.isoformat()}): "
        f"{summary}. Utilization is based on time-weighted occupancy, not energy "
        "measurement.",
    )


def _underutilized_rooms(
    session: Session, class_ids: list[int], intent: AssistantIntent
) -> AssistantResult:
    settings = get_settings()
    by_room = _metrics_by_room(_lecture_metrics(session, class_ids))
    underutilized = [
        (name, utilization)
        for name, (utilization, _, lecture_count) in by_room.items()
        if lecture_count
        and classify_utilization(
            utilization,
            settings.underutilized_cutoff_percent,
            settings.overutilized_cutoff_percent,
        )
        == "underutilized"
    ]
    if not underutilized:
        return AssistantResult(
            "answered",
            intent,
            "No underutilized rooms were identified from completed lectures in "
            "your scope. This reflects occupancy only; it does not measure energy use.",
        )
    summary = ", ".join(
        f"{name}: {utilization:.1f}%"
        for name, utilization in sorted(underutilized, key=lambda row: row[1])
    )
    return AssistantResult(
        "answered",
        intent,
        f"Rooms below the configured {settings.underutilized_cutoff_percent:.0f}% "
        f"utilization threshold: {summary}. This is occupancy-based and does not "
        "claim energy savings.",
    )


def _unusual_activity_yesterday(
    session: Session, class_ids: list[int], intent: AssistantIntent
) -> AssistantResult:
    settings = get_settings()
    timezone = ZoneInfo(settings.local_timezone)
    yesterday = datetime.now(timezone).date() - timedelta(days=1)
    start = _local_midnight(yesterday, timezone)
    end = _local_midnight(yesterday + timedelta(days=1), timezone)
    lectures = _completed_lectures(session, class_ids, start, end)
    spike_count = 0
    total_exits = 0
    for lecture in lectures:
        events = list(
            session.scalars(
                select(PresenceEvent)
                .where(
                    PresenceEvent.lecture_id == lecture.id,
                    PresenceEvent.timestamp_utc >= start,
                    PresenceEvent.timestamp_utc < end,
                    PresenceEvent.flagged_for_review.is_(False),
                    PresenceEvent.presence_confirmed.is_(True),
                    PresenceEvent.event_type.in_(("EXIT", "MANUAL_CORRECTION")),
                )
                .order_by(PresenceEvent.timestamp_utc, PresenceEvent.id)
            )
        )
        exits = [
            event
            for event in events
            if (event.correction_event_type or event.event_type) == "EXIT"
        ]
        total_exits += len(exits)
        spikes = detect_exit_spikes(
            [
                ExitEvent(normalize_output_datetime(event.timestamp_utc))
                for event in exits
            ],
            normalize_output_datetime(lecture.start_time),
            normalize_output_datetime(lecture.end_time),
            window_minutes=settings.insight_window_minutes,
            min_exits=settings.insight_min_exits,
            min_buckets=settings.insight_min_buckets,
        )
        spike_count += len(spikes)
    if not spike_count:
        return AssistantResult(
            "answered",
            intent,
            f"No unusual exit activity was detected yesterday ({total_exits} "
            "confirmed exits reviewed). Please verify before drawing conclusions.",
        )
    return AssistantResult(
        "answered",
        intent,
        f"Unusual activity detected. Please verify. {spike_count} exit-spike "
        f"window(s) were detected across completed lectures yesterday "
        f"({total_exits} confirmed exits reviewed).",
    )


def _room_average_occupancy(
    session: Session,
    class_ids: list[int],
    question: str,
    intent: AssistantIntent,
) -> AssistantResult:
    rooms = list(
        session.scalars(
            select(Classroom)
            .join(Lecture, Lecture.classroom_id == Classroom.id)
            .where(Lecture.class_id.in_(class_ids))
            .distinct()
        )
    )
    room = next(
        (candidate for candidate in rooms if candidate.name.casefold() in question),
        None,
    )
    if room is None:
        return AssistantResult(
            "refused",
            intent,
            "I could not match a room name in your permitted scope. Include the "
            "exact room name from your schedule.",
        )
    metrics = _lecture_metrics(session, class_ids, classroom_id=room.id)
    duration = sum(item.total_duration_seconds for item in metrics)
    occupied = sum(item.occupied_person_seconds for item in metrics)
    lecture_count = len(metrics)
    average = occupied / duration if duration else 0.0
    if not lecture_count:
        return AssistantResult(
            "answered",
            intent,
            f"No completed lecture occupancy data is available for {room.name}.",
        )
    return AssistantResult(
        "answered",
        intent,
        f"{room.name} had an average occupancy of {average:.2f} people "
        f"({average / room.capacity * 100:.1f}% of its capacity) across "
        f"{lecture_count} completed lecture(s).",
    )


def _monthly_comparison(
    session: Session, class_ids: list[int], intent: AssistantIntent
) -> AssistantResult:
    timezone = ZoneInfo(get_settings().local_timezone)
    today = datetime.now(timezone).date()
    this_month = today.replace(day=1)
    last_month_end = this_month
    last_month_start = (this_month - timedelta(days=1)).replace(day=1)
    current = _period_metrics(
        _lecture_metrics(
            session,
            class_ids,
            _local_midnight(this_month, timezone),
            _local_midnight(_next_month(this_month), timezone),
        )
    )
    previous = _period_metrics(
        _lecture_metrics(
            session,
            class_ids,
            _local_midnight(last_month_start, timezone),
            _local_midnight(last_month_end, timezone),
        )
    )
    if not current[2] and not previous[2]:
        return AssistantResult(
            "answered",
            intent,
            "No completed lecture occupancy data is available for this month "
            "or last month.",
        )
    return AssistantResult(
        "answered",
        intent,
        f"Completed lecture comparison: this month—average occupancy "
        f"{current[0]:.2f}, utilization {current[1]:.1f}%, outside time "
        f"{current[3]:.1f} minutes across {current[2]} lecture(s); last "
        f"month—average occupancy {previous[0]:.2f}, utilization "
        f"{previous[1]:.1f}%, outside time {previous[3]:.1f} minutes across "
        f"{previous[2]} lecture(s). Occupancy and utilization are estimates "
        "from recorded data.",
    )


def _lecture_metrics(
    session: Session,
    class_ids: list[int],
    start: datetime | None = None,
    end: datetime | None = None,
    classroom_id: int | None = None,
) -> list[LectureMetrics]:
    lectures = _completed_lectures(session, class_ids, start, end, classroom_id)
    if not lectures:
        return []
    rooms = {
        room.id: room
        for room in session.scalars(
            select(Classroom).where(
                Classroom.id.in_({lecture.classroom_id for lecture in lectures})
            )
        )
    }
    results = []
    for lecture in lectures:
        classroom = rooms.get(lecture.classroom_id)
        if classroom is None:
            continue
        student_ids = list(
            session.scalars(
                select(Student.id).where(
                    Student.class_id == lecture.class_id,
                    Student.is_active.is_(True),
                )
            )
        )
        events = []
        if student_ids:
            records = session.scalars(
                select(PresenceEvent)
                .where(
                    PresenceEvent.lecture_id == lecture.id,
                    PresenceEvent.student_id.in_(student_ids),
                    PresenceEvent.flagged_for_review.is_(False),
                    PresenceEvent.presence_confirmed.is_(True),
                    PresenceEvent.event_type.in_(
                        ("ENTRY", "EXIT", "RETURN", "MANUAL_CORRECTION")
                    ),
                )
                .order_by(PresenceEvent.timestamp_utc, PresenceEvent.id)
            )
            events = [
                OccupancyEvent(
                    student_id=event.student_id,
                    event_type=event.correction_event_type or event.event_type,
                    timestamp=normalize_output_datetime(event.timestamp_utc),
                )
                for event in records
                if event.student_id is not None
            ]
        analytics = analyze_lecture(
            events,
            normalize_output_datetime(lecture.start_time),
            normalize_output_datetime(lecture.end_time),
            classroom.capacity,
        )
        results.append(
            LectureMetrics(
                lecture=lecture,
                classroom=classroom,
                average_occupancy=analytics.average_occupancy,
                utilization_percent=analytics.utilization_percent,
                outside_minutes=analytics.outside_minutes,
                occupied_person_seconds=analytics.occupied_person_seconds,
                total_duration_seconds=analytics.total_duration_seconds,
            )
        )
    return results


def _completed_lectures(
    session: Session,
    class_ids: list[int],
    start: datetime | None = None,
    end: datetime | None = None,
    classroom_id: int | None = None,
) -> list[Lecture]:
    statement = select(Lecture).where(
        Lecture.class_id.in_(class_ids),
        Lecture.status == "completed",
    )
    if start is not None:
        statement = statement.where(Lecture.start_time >= start)
    if end is not None:
        statement = statement.where(Lecture.start_time < end)
    if classroom_id is not None:
        statement = statement.where(Lecture.classroom_id == classroom_id)
    return list(session.scalars(statement.order_by(Lecture.start_time, Lecture.id)))


def _metrics_by_room(
    metrics: list[LectureMetrics],
) -> dict[str, tuple[float, float, int]]:
    totals: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    for item in metrics:
        total = totals[item.classroom.name]
        total[0] += item.occupied_person_seconds
        total[1] += item.total_duration_seconds * item.classroom.capacity
        total[2] += 1
    return {
        name: (
            round(occupied / capacity_seconds * 100, 2) if capacity_seconds else 0,
            occupied,
            int(count),
        )
        for name, (occupied, capacity_seconds, count) in totals.items()
    }


def _period_metrics(
    metrics: list[LectureMetrics],
) -> tuple[float, float, int, float]:
    total_seconds = sum(item.total_duration_seconds for item in metrics)
    occupied = sum(item.occupied_person_seconds for item in metrics)
    capacity_seconds = sum(
        item.total_duration_seconds * item.classroom.capacity for item in metrics
    )
    average_occupancy = occupied / total_seconds if total_seconds else 0.0
    utilization = occupied / capacity_seconds * 100 if capacity_seconds else 0.0
    return (
        average_occupancy,
        utilization,
        len(metrics),
        sum(item.outside_minutes for item in metrics),
    )


def _local_midnight(value: date, timezone: ZoneInfo) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone).astimezone(UTC)


def _next_month(value: date) -> date:
    return value.replace(
        year=value.year + (value.month == 12), month=value.month % 12 + 1
    )

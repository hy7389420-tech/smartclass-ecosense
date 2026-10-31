from datetime import UTC, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import ApiError
from app.models import Camera, Lecture, PresenceEvent, Student, utc_now
from app.schemas.events import EventIngestRequest, EventIngestResponse
from app.schemas.resources import normalize_output_datetime
from app.services.presence import PresenceEvent as LogicEvent
from app.services.presence import derive_event_types


def parse_database_id(value: int | str, resource_name: str) -> int:
    try:
        record_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ApiError(404, "NOT_FOUND", f"{resource_name} was not found.") from exc
    if record_id < 1:
        raise ApiError(404, "NOT_FOUND", f"{resource_name} was not found.")
    return record_id


def ingest_event(
    session: Session,
    payload: EventIngestRequest,
    camera: Camera | None,
) -> EventIngestResponse:
    lecture_id = parse_database_id(payload.lecture_id, "Lecture")
    classroom_id = parse_database_id(payload.classroom_id, "Classroom")
    lecture = session.get(Lecture, lecture_id)
    if lecture is None:
        raise ApiError(404, "LECTURE_NOT_FOUND", "Lecture was not found.")
    if classroom_id != lecture.classroom_id:
        raise ApiError(
            422,
            "CLASSROOM_MISMATCH",
            "Classroom does not match the selected lecture.",
        )
    if camera is not None and camera.classroom_id != classroom_id:
        raise ApiError(
            403,
            "CAMERA_CLASSROOM_MISMATCH",
            "Camera is not assigned to the selected classroom.",
        )

    timestamp = payload.timestamp.astimezone(UTC)
    lecture_start = normalize_output_datetime(lecture.start_time)
    lecture_end = normalize_output_datetime(lecture.end_time)
    settings = get_settings()
    grace = timedelta(seconds=settings.event_time_grace_seconds)
    if timestamp < lecture_start - grace or timestamp > lecture_end + grace:
        raise ApiError(
            422,
            "TIMESTAMP_OUTSIDE_ALLOWED_WINDOW",
            "Event timestamp is outside the allowed lecture time window.",
        )

    student_code = payload.student_id
    student = None
    if student_code.upper() != "UNKNOWN":
        student = session.scalar(
            select(Student).where(Student.student_code == student_code)
        )
    if student is not None and student.class_id != lecture.class_id:
        raise ApiError(
            422,
            "STUDENT_CLASS_MISMATCH",
            "Student is not enrolled in the selected lecture class.",
        )

    duplicate = _find_duplicate(session, lecture_id, student, student_code, payload)
    if duplicate is not None:
        _mark_camera_online(camera)
        return EventIngestResponse(
            event=duplicate,
            duplicate=True,
            flagged_for_review=duplicate.flagged_for_review,
            reason="idempotent_duplicate",
        )

    flag_reasons: list[str] = []
    if student is None:
        flag_reasons.append("unknown_student")
    if payload.flagged_for_review:
        flag_reasons.append("client_flagged_for_review")
    if not payload.presence_confirmed:
        flag_reasons.append("presence_not_confirmed")
    if payload.confidence < settings.min_event_confidence:
        flag_reasons.append("low_confidence")
    if timestamp < lecture_start or timestamp > lecture_end:
        flag_reasons.append("timestamp_outside_lecture")

    derived_event_type = payload.event_type
    if not flag_reasons:
        existing_events = list(
            session.scalars(
                select(PresenceEvent)
                .where(
                    PresenceEvent.lecture_id == lecture_id,
                    PresenceEvent.student_id == student.id,
                    PresenceEvent.flagged_for_review.is_(False),
                    PresenceEvent.presence_confirmed.is_(True),
                    PresenceEvent.event_type.in_(
                        ("ENTRY", "EXIT", "RETURN", "MANUAL_CORRECTION")
                    ),
                )
                .order_by(PresenceEvent.timestamp_utc, PresenceEvent.id)
            )
        )
        latest_timestamp = (
            normalize_output_datetime(existing_events[-1].timestamp_utc)
            if existing_events
            else None
        )
        if latest_timestamp is not None and timestamp < latest_timestamp:
            flag_reasons.append("event_out_of_order")
        else:
            raw_events = [
                LogicEvent(
                    event_type=(
                        "ENTRY"
                        if (existing.correction_event_type or existing.event_type)
                        == "RETURN"
                        else existing.correction_event_type or existing.event_type
                    ),
                    timestamp=normalize_output_datetime(existing.timestamp_utc),
                )
                for existing in existing_events
            ]
            raw_events.append(LogicEvent(payload.event_type, timestamp))
            sequence = derive_event_types(raw_events)
            candidate_index = len(raw_events) - 1
            candidate_issue = next(
                (
                    issue
                    for issue in sequence.issues
                    if issue.event_index == candidate_index
                ),
                None,
            )
            if candidate_issue is not None:
                flag_reasons.append(f"invalid_sequence:{candidate_issue.reason}")
            elif sequence.events:
                derived_event_type = sequence.events[-1].event_type

    is_flagged = bool(flag_reasons)
    record = PresenceEvent(
        client_event_id=payload.client_event_id,
        lecture_id=lecture_id,
        classroom_id=classroom_id,
        student_id=student.id if student is not None else None,
        student_code_raw=student_code,
        event_type=derived_event_type,
        timestamp_utc=timestamp,
        confidence=payload.confidence,
        source=payload.source,
        flagged_for_review=is_flagged,
        review_status="needs_review" if is_flagged else "not_required",
        presence_confirmed=payload.presence_confirmed,
    )
    session.add(record)
    session.flush()
    _mark_camera_online(camera)

    return EventIngestResponse(
        event=record,
        duplicate=False,
        flagged_for_review=is_flagged,
        reason=";".join(flag_reasons) if flag_reasons else None,
    )


def _mark_camera_online(camera: Camera | None) -> None:
    if camera is None:
        return
    camera.status = "online"
    camera.last_seen_at = utc_now()


def _find_duplicate(
    session: Session,
    lecture_id: int,
    student: Student | None,
    student_code: str,
    payload: EventIngestRequest,
) -> PresenceEvent | None:
    if payload.client_event_id is not None:
        duplicate = session.scalar(
            select(PresenceEvent).where(
                PresenceEvent.lecture_id == lecture_id,
                PresenceEvent.client_event_id == payload.client_event_id,
            )
        )
        if duplicate is not None:
            return duplicate

    statement = select(PresenceEvent).where(
        PresenceEvent.lecture_id == lecture_id,
        PresenceEvent.timestamp_utc == payload.timestamp,
        PresenceEvent.event_type.in_(
            ("ENTRY", "RETURN") if payload.event_type == "ENTRY" else ("EXIT",)
        ),
    )
    if student is None:
        statement = statement.where(
            PresenceEvent.student_id.is_(None),
            PresenceEvent.student_code_raw == student_code,
        )
    else:
        statement = statement.where(PresenceEvent.student_id == student.id)
    return session.scalar(statement.order_by(PresenceEvent.id).limit(1))

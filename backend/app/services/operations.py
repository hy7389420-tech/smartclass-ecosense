from datetime import datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import ApiError
from app.models import (
    Alert,
    AuditLog,
    Camera,
    Lecture,
    PresenceEvent,
    User,
    utc_now,
)
from app.schemas.attendance import AttendanceResponse
from app.schemas.events import EventCorrectionWrite, PresenceEventRead
from app.schemas.operations import (
    AlertRead,
    AuditLogRead,
    HeartbeatRead,
)
from app.schemas.resources import normalize_output_datetime
from app.services.access import (
    assert_can_view_lecture,
    assert_can_view_student,
    class_scope,
)
from app.services.attendance import finalize_attendance
from app.services.camera_auth import authenticate_camera_key
from app.services.presence import PresenceEvent as LogicEvent
from app.services.presence import derive_event_types


def _event_snapshot(event: PresenceEvent) -> dict[str, object]:
    return {
        "id": event.id,
        "lecture_id": event.lecture_id,
        "classroom_id": event.classroom_id,
        "student_id": event.student_id,
        "student_code_raw": event.student_code_raw,
        "event_type": event.event_type,
        "correction_event_type": event.correction_event_type,
        "timestamp_utc": normalize_output_datetime(event.timestamp_utc).isoformat(),
        "confidence": event.confidence,
        "source": event.source,
        "flagged_for_review": event.flagged_for_review,
        "review_status": event.review_status,
        "presence_confirmed": event.presence_confirmed,
        "correction_of_event_id": event.correction_of_event_id,
    }


def correct_presence_event(
    session: Session,
    event_id: int,
    user: User,
    payload: EventCorrectionWrite,
) -> tuple[PresenceEventRead, AttendanceResponse]:
    original = session.get(PresenceEvent, event_id)
    if original is None:
        raise ApiError(404, "EVENT_NOT_FOUND", "Event was not found.")
    if not original.flagged_for_review or original.review_status != "needs_review":
        raise ApiError(
            409,
            "EVENT_NOT_REVIEWABLE",
            "Only events awaiting review can be corrected.",
        )
    lecture = assert_can_view_lecture(session, user, original.lecture_id)
    if not (
        normalize_output_datetime(lecture.start_time)
        <= payload.timestamp
        <= normalize_output_datetime(lecture.end_time)
    ):
        raise ApiError(
            422,
            "CORRECTION_OUTSIDE_LECTURE",
            "Corrected event timestamp must be inside the lecture time.",
        )

    student_id = payload.student_id or original.student_id
    if student_id is None:
        raise ApiError(
            422,
            "CORRECTION_STUDENT_REQUIRED",
            "Select a student for this event before applying the correction.",
        )
    student = assert_can_view_student(session, user, student_id)
    if student.class_id != lecture.class_id:
        raise ApiError(
            422,
            "CORRECTION_STUDENT_CLASS_MISMATCH",
            "Corrected student must belong to the lecture's class.",
        )

    existing_events = list(
        session.scalars(
            select(PresenceEvent)
            .where(
                PresenceEvent.lecture_id == lecture.id,
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
    sequence_events = []
    for event in existing_events:
        event_type = event.correction_event_type or event.event_type
        sequence_events.append(
            LogicEvent(
                event_type="ENTRY" if event_type == "RETURN" else event_type,
                timestamp=normalize_output_datetime(event.timestamp_utc),
            )
        )
    sequence_events.append(
        LogicEvent(event_type=payload.event_type, timestamp=payload.timestamp)
    )
    sequence = derive_event_types(sequence_events)
    new_index = len(sequence_events) - 1
    issue = next(
        (item for item in sequence.issues if item.event_index == new_index),
        None,
    )
    if issue is not None:
        raise ApiError(
            422,
            "INVALID_CORRECTED_EVENT_SEQUENCE",
            "Corrected event does not fit the student's event sequence.",
        )
    issue_indices = {item.event_index for item in sequence.issues}
    derived_index = 0
    corrected_type = None
    for input_index, _event in sorted(
        enumerate(sequence_events), key=lambda item: item[1].timestamp
    ):
        if input_index in issue_indices:
            continue
        if input_index == new_index:
            corrected_type = sequence.events[derived_index].event_type
            break
        derived_index += 1
    if corrected_type is None:
        raise ApiError(
            422,
            "INVALID_CORRECTED_EVENT_SEQUENCE",
            "Corrected event does not fit the student's event sequence.",
        )

    before = _event_snapshot(original)
    original.review_status = "resolved"
    correction = PresenceEvent(
        lecture_id=lecture.id,
        classroom_id=lecture.classroom_id,
        student_id=student.id,
        student_code_raw=student.student_code,
        event_type="MANUAL_CORRECTION",
        correction_event_type=corrected_type,
        timestamp_utc=payload.timestamp,
        confidence=1.0,
        source="manual",
        flagged_for_review=False,
        review_status="not_required",
        presence_confirmed=True,
        correction_of_event_id=original.id,
    )
    session.add(correction)
    session.flush()
    session.add(
        AuditLog(
            actor_user_id=user.id,
            action="event_corrected",
            entity_type="presence_event",
            entity_id=str(original.id),
            before_json=before,
            after_json=_event_snapshot(correction),
            reason=payload.reason,
        )
    )
    attendance = finalize_attendance(session, lecture)
    return PresenceEventRead.model_validate(correction), attendance


def resolve_review_event(
    session: Session, event_id: int, user: User, reason: str
) -> PresenceEventRead:
    event = session.get(PresenceEvent, event_id)
    if event is None:
        raise ApiError(404, "EVENT_NOT_FOUND", "Event was not found.")
    if not event.flagged_for_review or event.review_status != "needs_review":
        raise ApiError(
            409,
            "EVENT_NOT_REVIEWABLE",
            "Only events awaiting review can be resolved.",
        )
    assert_can_view_lecture(session, user, event.lecture_id)
    before = _event_snapshot(event)
    event.review_status = "resolved"
    session.add(
        AuditLog(
            actor_user_id=user.id,
            action="review_event_resolved",
            entity_type="presence_event",
            entity_id=str(event.id),
            before_json=before,
            after_json=_event_snapshot(event),
            reason=reason,
        )
    )
    session.flush()
    return PresenceEventRead.model_validate(event)


def list_review_events(
    session: Session,
    user: User,
    limit: int,
    offset: int,
) -> tuple[list[PresenceEventRead], int]:
    filters = [
        PresenceEvent.flagged_for_review.is_(True),
        PresenceEvent.review_status == "needs_review",
    ]
    if user.role != "ADMIN":
        filters.append(
            PresenceEvent.lecture_id.in_(
                select(Lecture.id).where(
                    Lecture.class_id.in_(class_scope(session, user))
                )
            )
        )
    rows = list(
        session.scalars(
            select(PresenceEvent)
            .where(*filters)
            .order_by(PresenceEvent.timestamp_utc.desc(), PresenceEvent.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    total = (
        session.scalar(select(func.count()).select_from(PresenceEvent).where(*filters))
        or 0
    )
    return [PresenceEventRead.model_validate(row) for row in rows], total


def _open_camera_alert(session: Session, camera_id: int) -> Alert | None:
    return session.scalar(
        select(Alert)
        .where(
            Alert.kind == "camera_offline",
            Alert.camera_id == camera_id,
            Alert.resolved_at.is_(None),
        )
        .limit(1)
    )


def _create_alert(
    session: Session,
    kind: str,
    severity: str,
    message: str,
    *,
    now: datetime,
    camera_id: int | None = None,
    classroom_id: int | None = None,
    lecture_id: int | None = None,
) -> None:
    filters = [
        Alert.kind == kind,
        Alert.resolved_at.is_(None),
        Alert.camera_id == camera_id
        if camera_id is not None
        else Alert.camera_id.is_(None),
        Alert.classroom_id == classroom_id
        if classroom_id is not None
        else Alert.classroom_id.is_(None),
        Alert.lecture_id == lecture_id
        if lecture_id is not None
        else Alert.lecture_id.is_(None),
    ]
    if session.scalar(select(Alert.id).where(*filters).limit(1)) is not None:
        return
    session.add(
        Alert(
            kind=kind,
            severity=severity,
            message=message,
            camera_id=camera_id,
            classroom_id=classroom_id,
            lecture_id=lecture_id,
            created_at=now,
        )
    )


def refresh_operational_alerts(session: Session, now: datetime | None = None) -> None:
    current_time = now or utc_now()
    settings = get_settings()
    cutoff = current_time - timedelta(seconds=settings.camera_offline_seconds)
    for camera in session.scalars(select(Camera)):
        if (
            camera.last_seen_at is None
            or normalize_output_datetime(camera.last_seen_at) < cutoff
        ):
            camera.status = "offline"
            _create_alert(
                session,
                "camera_offline",
                "high",
                "Camera Offline. Please verify the camera connection.",
                camera_id=camera.id,
                classroom_id=camera.classroom_id,
                now=current_time,
            )

    low_cutoff = current_time - timedelta(
        minutes=settings.low_confidence_alert_window_minutes
    )
    low_groups = session.execute(
        select(PresenceEvent.classroom_id, PresenceEvent.lecture_id, func.count())
        .where(
            PresenceEvent.timestamp_utc >= low_cutoff,
            PresenceEvent.timestamp_utc <= current_time,
            PresenceEvent.confidence < settings.min_event_confidence,
            PresenceEvent.flagged_for_review.is_(True),
        )
        .group_by(PresenceEvent.classroom_id, PresenceEvent.lecture_id)
        .having(func.count() >= settings.low_confidence_alert_min_events)
    ).all()
    for classroom_id, lecture_id, _count in low_groups:
        _create_alert(
            session,
            "low_confidence_event_spike",
            "medium",
            "Unusual activity detected. Please verify.",
            classroom_id=classroom_id,
            lecture_id=lecture_id,
            now=current_time,
        )

    exit_cutoff = current_time - timedelta(
        minutes=settings.unusual_exit_alert_window_minutes
    )
    exit_groups = session.execute(
        select(PresenceEvent.classroom_id, PresenceEvent.lecture_id, func.count())
        .where(
            PresenceEvent.timestamp_utc >= exit_cutoff,
            PresenceEvent.timestamp_utc <= current_time,
            or_(
                PresenceEvent.event_type == "EXIT",
                PresenceEvent.correction_event_type == "EXIT",
            ),
            PresenceEvent.flagged_for_review.is_(False),
            PresenceEvent.presence_confirmed.is_(True),
        )
        .group_by(PresenceEvent.classroom_id, PresenceEvent.lecture_id)
        .having(func.count() >= settings.unusual_exit_alert_min_events)
    ).all()
    for classroom_id, lecture_id, _count in exit_groups:
        _create_alert(
            session,
            "unusual_exit_activity",
            "medium",
            "Unusual activity detected. Please verify.",
            classroom_id=classroom_id,
            lecture_id=lecture_id,
            now=current_time,
        )
    session.flush()


def camera_heartbeat(
    session: Session,
    camera_id: int,
    api_key: str | None,
    now: datetime | None = None,
) -> HeartbeatRead:
    camera = authenticate_camera_key(session, api_key)
    if camera is None or camera.id != camera_id:
        raise ApiError(403, "CAMERA_MISMATCH", "Camera key does not match this camera.")

    current_time = now or utc_now()
    camera.status = "online"
    camera.last_seen_at = current_time
    open_alert = _open_camera_alert(session, camera.id)
    if open_alert is not None:
        before = {"resolved_at": None}
        open_alert.resolved_at = current_time
        session.add(
            AuditLog(
                actor_user_id=None,
                action="camera_recovered",
                entity_type="alert",
                entity_id=str(open_alert.id),
                before_json=before,
                after_json={"resolved_at": current_time.isoformat()},
                reason="Camera heartbeat received.",
            )
        )
    refresh_operational_alerts(session, current_time)
    session.flush()
    return HeartbeatRead(
        camera_id=camera.id,
        status="online",
        last_seen_at=current_time,
    )


def list_alerts(
    session: Session,
    user: User,
    limit: int,
    offset: int,
    unresolved_only: bool,
) -> tuple[list[AlertRead], int]:
    refresh_operational_alerts(session)
    filters = [Alert.resolved_at.is_(None)] if unresolved_only else []
    if user.role != "ADMIN":
        accessible_classes = class_scope(session, user)
        lecture_ids = select(Lecture.id).where(Lecture.class_id.in_(accessible_classes))
        classroom_ids = select(Lecture.classroom_id).where(
            Lecture.class_id.in_(accessible_classes)
        )
        filters.append(
            Alert.lecture_id.in_(lecture_ids) | Alert.classroom_id.in_(classroom_ids)
        )
    rows = list(
        session.scalars(
            select(Alert)
            .where(*filters)
            .order_by(Alert.created_at.desc(), Alert.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    total = session.scalar(select(func.count()).select_from(Alert).where(*filters)) or 0
    return [AlertRead.model_validate(row) for row in rows], total


def resolve_alert(
    session: Session, alert_id: int, user: User, reason: str
) -> AlertRead:
    alert = session.get(Alert, alert_id)
    if alert is None:
        raise ApiError(404, "ALERT_NOT_FOUND", "Alert was not found.")
    if alert.resolved_at is not None:
        raise ApiError(409, "ALERT_ALREADY_RESOLVED", "Alert is already resolved.")
    if user.role != "ADMIN":
        accessible_classes = class_scope(session, user)
        if alert.lecture_id is not None:
            assert_can_view_lecture(session, user, alert.lecture_id)
        elif alert.classroom_id is not None:
            visible = session.scalar(
                select(Lecture.id).where(
                    Lecture.classroom_id == alert.classroom_id,
                    Lecture.class_id.in_(accessible_classes),
                )
            )
            if visible is None:
                raise ApiError(
                    403, "FORBIDDEN", "You do not have access to this alert."
                )
        else:
            raise ApiError(403, "FORBIDDEN", "You do not have access to this alert.")
    before = {"resolved_at": None}
    alert.resolved_at = utc_now()
    session.add(
        AuditLog(
            actor_user_id=user.id,
            action="alert_resolved",
            entity_type="alert",
            entity_id=str(alert.id),
            before_json=before,
            after_json={"resolved_at": alert.resolved_at.isoformat()},
            reason=reason,
        )
    )
    session.flush()
    return AlertRead.model_validate(alert)


def list_audit_logs(
    session: Session,
    limit: int,
    offset: int,
    entity_type: str | None,
    actor_user_id: int | None,
) -> tuple[list[AuditLogRead], int]:
    filters = []
    if entity_type is not None:
        filters.append(AuditLog.entity_type == entity_type)
    if actor_user_id is not None:
        filters.append(AuditLog.actor_user_id == actor_user_id)
    rows = list(
        session.scalars(
            select(AuditLog)
            .where(*filters)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    total = (
        session.scalar(select(func.count()).select_from(AuditLog).where(*filters)) or 0
    )
    return [AuditLogRead.model_validate(row) for row in rows], total

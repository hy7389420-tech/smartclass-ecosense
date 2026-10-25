from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import ApiError
from app.models import (
    AttendanceRecord,
    Camera,
    ClassGroup,
    Lecture,
    PresenceEvent,
    Student,
)
from app.schemas.attendance import AttendanceResponse, AttendanceStudentRead
from app.schemas.resources import normalize_output_datetime
from app.services.presence import PresenceEvent as LogicEvent
from app.services.presence import calculate_presence


def get_lecture(session: Session, lecture_id: int) -> Lecture:
    lecture = session.get(Lecture, lecture_id)
    if lecture is None:
        raise ApiError(404, "LECTURE_NOT_FOUND", "Lecture was not found.")
    return lecture


def change_lecture_lifecycle(
    session: Session, lecture_id: int, action: Literal["start", "end"]
) -> Lecture:
    lecture = get_lecture(session, lecture_id)
    if action == "start":
        if lecture.status == "live":
            _ensure_lifecycle_event(session, lecture, "LECTURE_START")
            return lecture
        if lecture.status != "scheduled":
            raise ApiError(
                409,
                "LECTURE_CANNOT_START",
                "Only a scheduled lecture can be started.",
            )
        lecture.status = "live"
        event_type = "LECTURE_START"
    else:
        if lecture.status == "completed":
            _ensure_lifecycle_event(session, lecture, "LECTURE_END")
            return lecture
        if lecture.status != "live":
            raise ApiError(
                409,
                "LECTURE_CANNOT_END",
                "Only a live lecture can be ended.",
            )
        lecture.status = "completed"
        event_type = "LECTURE_END"

    _ensure_lifecycle_event(session, lecture, event_type)
    session.flush()
    return lecture


def _ensure_lifecycle_event(
    session: Session,
    lecture: Lecture,
    event_type: Literal["LECTURE_START", "LECTURE_END"],
) -> None:
    existing = session.scalar(
        select(PresenceEvent.id)
        .where(
            PresenceEvent.lecture_id == lecture.id,
            PresenceEvent.event_type == event_type,
        )
        .limit(1)
    )
    if existing is not None:
        return
    session.add(
        PresenceEvent(
            lecture_id=lecture.id,
            classroom_id=lecture.classroom_id,
            student_id=None,
            event_type=event_type,
            timestamp_utc=datetime.now(UTC),
            confidence=1.0,
            source="manual",
            flagged_for_review=False,
            review_status="not_required",
            presence_confirmed=True,
        )
    )
    session.flush()


def attendance_snapshot(
    session: Session, lecture: Lecture, now: datetime | None = None
) -> AttendanceResponse:
    evaluation_time = now or datetime.now(UTC)
    lecture_start = normalize_output_datetime(lecture.start_time)
    lecture_end = normalize_output_datetime(lecture.end_time)
    if lecture.status == "completed":
        ended_at = session.scalar(
            select(PresenceEvent.timestamp_utc)
            .where(
                PresenceEvent.lecture_id == lecture.id,
                PresenceEvent.event_type == "LECTURE_END",
            )
            .order_by(PresenceEvent.timestamp_utc.desc(), PresenceEvent.id.desc())
            .limit(1)
        )
        if ended_at is not None:
            evaluation_time = normalize_output_datetime(ended_at)
        else:
            evaluation_time = lecture_end
    elif lecture.status == "scheduled":
        evaluation_time = min(evaluation_time, lecture_start)

    students = list(
        session.scalars(
            select(Student)
            .join(ClassGroup, Student.class_id == ClassGroup.id)
            .where(ClassGroup.id == lecture.class_id, Student.is_active.is_(True))
            .order_by(Student.id)
        )
    )
    event_rows = list(
        session.scalars(
            select(PresenceEvent)
            .where(
                PresenceEvent.lecture_id == lecture.id,
                PresenceEvent.flagged_for_review.is_(False),
                PresenceEvent.presence_confirmed.is_(True),
                PresenceEvent.event_type.in_(
                    ("ENTRY", "EXIT", "RETURN", "MANUAL_CORRECTION")
                ),
            )
            .order_by(PresenceEvent.timestamp_utc, PresenceEvent.id)
        )
    )
    review_rows = list(
        session.scalars(
            select(PresenceEvent).where(
                PresenceEvent.lecture_id == lecture.id,
                PresenceEvent.flagged_for_review.is_(True),
            )
        )
    )
    records: list[AttendanceStudentRead] = []
    for student in students:
        student_events = [
            LogicEvent(
                event_type=event.correction_event_type or event.event_type,
                timestamp=normalize_output_datetime(event.timestamp_utc),
            )
            for event in event_rows
            if event.student_id == student.id
        ]
        result = calculate_presence(
            student_events,
            lecture_start,
            lecture_end,
            now=evaluation_time,
        )
        state = "ABSENT"
        for event in student_events:
            if event.timestamp <= evaluation_time:
                state = "OUTSIDE" if event.event_type == "EXIT" else "INSIDE"
        records.append(
            AttendanceStudentRead(
                student_id=student.id,
                student_code=student.student_code,
                name=student.name,
                status=state,
                first_entry=result.first_entry,
                last_exit=result.last_exit,
                inside_minutes=result.inside_minutes,
                outside_minutes=result.outside_minutes,
                exit_count=result.exit_count,
                return_count=result.return_count,
                flagged=any(event.student_id == student.id for event in review_rows),
            )
        )

    total = len(records)
    present = sum(record.status != "ABSENT" for record in records)
    inside = sum(record.status == "INSIDE" for record in records)
    outside = sum(record.status == "OUTSIDE" for record in records)
    absent = total - present
    return AttendanceResponse(
        lecture_id=lecture.id,
        lecture_status=lecture.status,
        finalized=lecture.status == "completed",
        total_students=total,
        present=present,
        inside=inside,
        outside=outside,
        absent=absent,
        occupancy_percent=round(inside / total * 100, 2) if total else 0.0,
        records=records,
    )


def finalize_attendance(
    session: Session, lecture: Lecture, now: datetime | None = None
) -> AttendanceResponse:
    snapshot = attendance_snapshot(session, lecture, now)
    computed_at = datetime.now(UTC)
    for item in snapshot.records:
        record = session.scalar(
            select(AttendanceRecord).where(
                AttendanceRecord.lecture_id == lecture.id,
                AttendanceRecord.student_id == item.student_id,
            )
        )
        if record is None:
            record = AttendanceRecord(
                lecture_id=lecture.id,
                student_id=item.student_id,
                status=item.status,
            )
            session.add(record)
        record.status = item.status
        record.first_entry = item.first_entry
        record.last_exit = item.last_exit
        record.inside_minutes = item.inside_minutes
        record.outside_minutes = item.outside_minutes
        record.exit_count = item.exit_count
        record.return_count = item.return_count
        record.computed_at = computed_at
    session.flush()
    return snapshot


def get_finalized_attendance(session: Session, lecture: Lecture) -> AttendanceResponse:
    if lecture.status == "completed":
        persisted = list(
            session.scalars(
                select(AttendanceRecord)
                .where(AttendanceRecord.lecture_id == lecture.id)
                .order_by(AttendanceRecord.student_id)
            )
        )
        if persisted:
            students = {
                student.id: student
                for student in session.scalars(
                    select(Student).where(
                        Student.id.in_([record.student_id for record in persisted])
                    )
                )
            }
            flagged_student_ids = set(
                session.scalars(
                    select(PresenceEvent.student_id).where(
                        PresenceEvent.lecture_id == lecture.id,
                        PresenceEvent.flagged_for_review.is_(True),
                        PresenceEvent.student_id.is_not(None),
                    )
                )
            )
            rows = [
                AttendanceStudentRead(
                    student_id=record.student_id,
                    student_code=students[record.student_id].student_code,
                    name=students[record.student_id].name,
                    status=record.status,
                    first_entry=record.first_entry,
                    last_exit=record.last_exit,
                    inside_minutes=record.inside_minutes,
                    outside_minutes=record.outside_minutes,
                    exit_count=record.exit_count,
                    return_count=record.return_count,
                    flagged=record.student_id in flagged_student_ids,
                )
                for record in persisted
                if record.student_id in students
            ]
            total = len(rows)
            present = sum(row.status != "ABSENT" for row in rows)
            inside = sum(row.status == "INSIDE" for row in rows)
            outside = sum(row.status == "OUTSIDE" for row in rows)
            return AttendanceResponse(
                lecture_id=lecture.id,
                lecture_status=lecture.status,
                finalized=True,
                total_students=total,
                present=present,
                inside=inside,
                outside=outside,
                absent=total - present,
                occupancy_percent=round(inside / total * 100, 2) if total else 0.0,
                records=rows,
            )
    return attendance_snapshot(session, lecture)


def camera_status(session: Session, classroom_id: int) -> str:
    offline_window = timedelta(seconds=get_settings().camera_offline_seconds)
    cutoff = datetime.now(UTC) - offline_window
    recent_camera = session.scalar(
        select(Camera.id)
        .where(
            Camera.classroom_id == classroom_id,
            Camera.status == "online",
            Camera.last_seen_at.is_not(None),
            Camera.last_seen_at >= cutoff,
        )
        .limit(1)
    )
    return "Online" if recent_camera is not None else "Camera Offline"

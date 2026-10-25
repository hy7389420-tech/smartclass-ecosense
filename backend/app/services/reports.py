import csv
from datetime import UTC, date, datetime, time, timedelta
from io import StringIO
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import ApiError
from app.models import (
    ActivityWindow,
    AttendanceRecord,
    AuditLog,
    Classroom,
    Insight,
    Lecture,
    PresenceEvent,
    User,
)
from app.schemas.attendance import AttendanceResponse
from app.schemas.reports import (
    LectureSummaryRead,
    ReportAttendanceSummary,
    ReportLectureRead,
    SessionReportRead,
    SummaryReportRead,
)
from app.services.access import assert_can_view_lecture, class_scope
from app.services.attendance import attendance_snapshot, get_finalized_attendance
from app.services.engagement import ESTIMATE_NOTE, get_lecture_engagement

LIMITATIONS_NOTE = (
    "This report reflects recorded data only. Camera and derived presence "
    "measurements may be incomplete; verify sensitive decisions manually."
)
STUDENT_ONLY_NOTE = (
    "This export contains only the authenticated student's own attendance data."
)
CSV_FIELDS = (
    "lecture_id",
    "subject",
    "start_time",
    "student_id",
    "student_code",
    "student_name",
    "status",
    "first_entry",
    "last_exit",
    "inside_minutes",
    "outside_minutes",
    "exit_count",
    "return_count",
    "total_students",
    "present",
    "inside",
    "outside",
    "absent",
    "occupancy_percent",
    "engagement_estimate",
    "estimates_note",
    "limitations_note",
)


def build_session_report(
    session: Session, lecture_id: int, user: User
) -> SessionReportRead:
    lecture = assert_can_view_lecture(session, user, lecture_id)
    classroom = session.get(Classroom, lecture.classroom_id)
    if classroom is None:
        raise ApiError(404, "CLASSROOM_NOT_FOUND", "Classroom was not found.")

    attendance: AttendanceResponse = (
        get_finalized_attendance(session, lecture)
        if lecture.status == "completed"
        else attendance_snapshot(session, lecture)
    )
    is_student = user.role == "STUDENT"
    student_records = (
        [row for row in attendance.records if row.student_id == user.student_id]
        if is_student
        else attendance.records
    )
    summary = None
    engagement = None
    estimates_note = None
    if not is_student:
        summary = ReportAttendanceSummary(
            total_students=attendance.total_students,
            present=attendance.present,
            inside=attendance.inside,
            outside=attendance.outside,
            absent=attendance.absent,
            occupancy_percent=attendance.occupancy_percent,
        )
        engagement = get_lecture_engagement(session, lecture_id)
        estimates_note = ESTIMATE_NOTE

    return SessionReportRead(
        lecture=ReportLectureRead(
            lecture_id=lecture.id,
            subject=lecture.subject,
            status=lecture.status,
            classroom_id=classroom.id,
            classroom_name=classroom.name,
            capacity=classroom.capacity,
            start_time=lecture.start_time,
            end_time=lecture.end_time,
        ),
        attendance_summary=summary,
        student_records=student_records,
        engagement=engagement,
        estimates_note=estimates_note,
        limitations_note=STUDENT_ONLY_NOTE if is_student else LIMITATIONS_NOTE,
    )


def build_summary_report(
    session: Session, user: User, period: str, requested_date: date | None = None
) -> SummaryReportRead:
    timezone = ZoneInfo(get_settings().local_timezone)
    report_date = requested_date or datetime.now(timezone).date()
    if period == "daily":
        start_date = report_date
        end_date = report_date
    elif period == "weekly":
        start_date = report_date - timedelta(days=report_date.weekday())
        end_date = start_date + timedelta(days=6)
    else:
        raise ValueError(f"Unsupported report period: {period}")

    start_at = datetime.combine(start_date, time.min, tzinfo=timezone).astimezone(UTC)
    end_at = datetime.combine(
        end_date + timedelta(days=1), time.min, tzinfo=timezone
    ).astimezone(UTC)
    accessible_classes = class_scope(session, user)
    lectures = list(
        session.scalars(
            select(Lecture)
            .where(
                Lecture.status == "completed",
                Lecture.class_id.in_(accessible_classes),
                Lecture.start_time >= start_at,
                Lecture.start_time < end_at,
            )
            .order_by(Lecture.start_time, Lecture.id)
        )
    )

    rows: list[LectureSummaryRead] = []
    if user.role == "STUDENT":
        if user.student_id is None:
            raise ApiError(
                403,
                "STUDENT_MAPPING_REQUIRED",
                "Student account is not linked to a student record.",
            )
        for lecture in lectures:
            record = session.scalar(
                select(AttendanceRecord).where(
                    AttendanceRecord.lecture_id == lecture.id,
                    AttendanceRecord.student_id == user.student_id,
                )
            )
            if record is None:
                continue
            rows.append(
                LectureSummaryRead(
                    lecture_id=lecture.id,
                    subject=lecture.subject,
                    start_time=lecture.start_time,
                    total_students=None,
                    present=None,
                    inside=None,
                    outside=None,
                    absent=None,
                    inside_minutes=record.inside_minutes,
                    outside_minutes=record.outside_minutes,
                    status=record.status,
                    student_id=user.student_id,
                )
            )
    else:
        for lecture in lectures:
            records = list(
                session.scalars(
                    select(AttendanceRecord).where(
                        AttendanceRecord.lecture_id == lecture.id
                    )
                )
            )
            total = len(records)
            present = sum(row.status != "ABSENT" for row in records)
            inside = sum(row.status == "INSIDE" for row in records)
            outside = sum(row.status == "OUTSIDE" for row in records)
            rows.append(
                LectureSummaryRead(
                    lecture_id=lecture.id,
                    subject=lecture.subject,
                    start_time=lecture.start_time,
                    total_students=total,
                    present=present,
                    inside=inside,
                    outside=outside,
                    absent=total - present,
                    inside_minutes=round(sum(row.inside_minutes for row in records), 2),
                    outside_minutes=round(
                        sum(row.outside_minutes for row in records), 2
                    ),
                )
            )
    return SummaryReportRead(
        period=period,
        start_date=start_date,
        end_date=end_date,
        lecture_count=len(rows),
        rows=rows,
        limitations_note=STUDENT_ONLY_NOTE
        if user.role == "STUDENT"
        else LIMITATIONS_NOTE,
    )


def session_report_csv(report: SessionReportRead) -> str:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, lineterminator="\r\n")
    writer.writeheader()
    summary = report.attendance_summary
    engagement_average = (
        report.engagement.average_estimate if report.engagement is not None else None
    )
    if not report.student_records:
        writer.writerow(
            {
                "estimates_note": report.estimates_note or "",
                "limitations_note": report.limitations_note,
            }
        )
    for record in report.student_records:
        writer.writerow(
            _safe_csv_row(
                {
                    "lecture_id": report.lecture.lecture_id,
                    "subject": report.lecture.subject,
                    "start_time": report.lecture.start_time.isoformat(),
                    "student_id": record.student_id,
                    "student_code": record.student_code,
                    "student_name": record.name,
                    "status": record.status,
                    "first_entry": record.first_entry.isoformat()
                    if record.first_entry
                    else "",
                    "last_exit": record.last_exit.isoformat()
                    if record.last_exit
                    else "",
                    "inside_minutes": record.inside_minutes,
                    "outside_minutes": record.outside_minutes,
                    "exit_count": record.exit_count,
                    "return_count": record.return_count,
                    "total_students": summary.total_students if summary else "",
                    "present": summary.present if summary else "",
                    "inside": summary.inside if summary else "",
                    "outside": summary.outside if summary else "",
                    "absent": summary.absent if summary else "",
                    "occupancy_percent": summary.occupancy_percent if summary else "",
                    "engagement_estimate": engagement_average
                    if engagement_average is not None
                    else "",
                    "estimates_note": report.estimates_note or "",
                    "limitations_note": report.limitations_note,
                }
            )
        )
    return output.getvalue()


def summary_report_csv(report: SummaryReportRead) -> str:
    output = StringIO(newline="")
    fields = (*LectureSummaryRead.model_fields, "limitations_note")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\r\n")
    writer.writeheader()
    if not report.rows:
        writer.writerow({"limitations_note": report.limitations_note})
    for row in report.rows:
        values = row.model_dump(mode="json")
        values["limitations_note"] = report.limitations_note
        writer.writerow(_safe_csv_row(values))
    return output.getvalue()


def _safe_csv_row(row: dict[str, object]) -> dict[str, object]:
    safe: dict[str, object] = {}
    for key, value in row.items():
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
            safe[key] = "'" + value
        else:
            safe[key] = value
    return safe


def run_retention(
    session: Session,
    actor_user_id: int | None,
    *,
    dry_run: bool = True,
    now: datetime | None = None,
) -> dict[str, object]:
    settings = get_settings()
    current_time = now or datetime.now(UTC)
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("now must include a timezone.")
    current_time = current_time.astimezone(UTC)
    cutoff = current_time - timedelta(days=settings.retention_days)
    predicates = {
        "presence_events": PresenceEvent.timestamp_utc < cutoff,
        "activity_windows": ActivityWindow.window_end < cutoff,
        "insights": Insight.created_at < cutoff,
    }
    candidates = {
        table: int(
            session.scalar(select(func.count()).select_from(model).where(predicate))
            or 0
        )
        for table, (model, predicate) in _retention_models(predicates).items()
    }
    expired_event_ids = select(PresenceEvent.id).where(predicates["presence_events"])
    correction_links_to_detach = int(
        session.scalar(
            select(func.count())
            .select_from(PresenceEvent)
            .where(
                PresenceEvent.correction_of_event_id.in_(expired_event_ids),
                PresenceEvent.timestamp_utc >= cutoff,
            )
        )
        or 0
    )
    deleted = {table: 0 for table in predicates}
    if not dry_run:
        if correction_links_to_detach:
            session.execute(
                update(PresenceEvent)
                .where(
                    PresenceEvent.correction_of_event_id.in_(expired_event_ids),
                    PresenceEvent.timestamp_utc >= cutoff,
                )
                .values(correction_of_event_id=None)
            )
        for table, (model, predicate) in _retention_models(predicates).items():
            result = session.execute(model.__table__.delete().where(predicate))
            deleted[table] = max(0, result.rowcount or 0)

    session.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action="retention_dry_run" if dry_run else "retention_deleted",
            entity_type="data_retention",
            entity_id=cutoff.isoformat(),
            before_json={
                "candidates": candidates,
                "correction_links_to_detach": correction_links_to_detach,
            },
            after_json={
                "deleted": deleted,
                "correction_links_detached": (
                    0 if dry_run else correction_links_to_detach
                ),
            },
            reason=(
                f"{'Previewed' if dry_run else 'Deleted'} records older than "
                f"{settings.retention_days} days."
            ),
            created_at=current_time,
        )
    )
    session.flush()
    return {
        "dry_run": dry_run,
        "retention_days": settings.retention_days,
        "cutoff_at": cutoff,
        "candidates": candidates,
        "deleted": deleted,
        "correction_links_to_detach": correction_links_to_detach,
    }


def _retention_models(predicates):
    return {
        "presence_events": (PresenceEvent, predicates["presence_events"]),
        "activity_windows": (ActivityWindow, predicates["activity_windows"]),
        "insights": (Insight, predicates["insights"]),
    }

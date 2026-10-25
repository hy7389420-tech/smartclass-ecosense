from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import func, select

from app.models import AttendanceRecord, Lecture, Student
from app.repositories.catalog import (
    create_record,
    delete_record,
    get_record,
    update_record,
)
from app.routes.dependencies import (
    CurrentUser,
    DatabaseSession,
    PageLimit,
    PageOffset,
    require_role,
)
from app.schemas.attendance import PresenceHistoryItem
from app.schemas.common import PaginatedResponse
from app.schemas.resources import StudentRead, StudentWrite
from app.services.access import assert_can_view_student, class_scope

router = APIRouter(
    prefix="/students",
    tags=["students"],
    dependencies=[Depends(require_role("ADMIN", "HOD", "FACULTY", "STUDENT"))],
)


@router.get("/{student_id}/presence-history", response_model=list[PresenceHistoryItem])
def read_student_presence_history(
    student_id: int, session: DatabaseSession, user: CurrentUser
):
    student = assert_can_view_student(session, user, student_id)
    rows = session.execute(
        select(AttendanceRecord, Lecture)
        .join(Lecture, AttendanceRecord.lecture_id == Lecture.id)
        .where(AttendanceRecord.student_id == student.id)
        .order_by(Lecture.start_time.desc(), Lecture.id.desc())
    ).all()
    return [
        PresenceHistoryItem(
            lecture_id=lecture.id,
            subject=lecture.subject,
            lecture_start=lecture.start_time,
            lecture_end=lecture.end_time,
            status=record.status,
            first_entry=record.first_entry,
            last_exit=record.last_exit,
            inside_minutes=record.inside_minutes,
            outside_minutes=record.outside_minutes,
            exit_count=record.exit_count,
            return_count=record.return_count,
        )
        for record, lecture in rows
    ]


@router.post(
    "",
    response_model=StudentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("ADMIN"))],
)
def create_student(payload: StudentWrite, session: DatabaseSession):
    return create_record(session, Student, payload.model_dump())


@router.get("", response_model=PaginatedResponse[StudentRead])
def list_students(
    session: DatabaseSession,
    user: CurrentUser,
    limit: PageLimit = 20,
    offset: PageOffset = 0,
):
    if user.role == "STUDENT":
        if user.student_id is None:
            class_scope(session, user)
        filters = [Student.id == user.student_id]
    else:
        filters = [Student.class_id.in_(class_scope(session, user))]
    items = list(
        session.scalars(
            select(Student)
            .where(*filters)
            .order_by(Student.id)
            .offset(offset)
            .limit(limit)
        )
    )
    total = (
        session.scalar(select(func.count()).select_from(Student).where(*filters)) or 0
    )
    return PaginatedResponse[StudentRead](
        items=items, total=total, limit=limit, offset=offset
    )


@router.get("/{student_id}", response_model=StudentRead)
def read_student(student_id: int, session: DatabaseSession, user: CurrentUser):
    assert_can_view_student(session, user, student_id)
    return get_record(session, Student, student_id, "Student")


@router.put(
    "/{student_id}",
    response_model=StudentRead,
    dependencies=[Depends(require_role("ADMIN"))],
)
def update_student(student_id: int, payload: StudentWrite, session: DatabaseSession):
    return update_record(session, Student, student_id, "Student", payload.model_dump())


@router.delete(
    "/{student_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("ADMIN"))],
)
def delete_student(student_id: int, session: DatabaseSession):
    delete_record(session, Student, student_id, "Student")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

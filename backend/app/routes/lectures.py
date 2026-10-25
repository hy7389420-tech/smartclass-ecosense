from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import func, select

from app.core.errors import ApiError
from app.models import Lecture
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
from app.schemas.attendance import AttendanceResponse
from app.schemas.common import PaginatedResponse
from app.schemas.resources import LectureRead, LectureWrite
from app.services.access import assert_can_view_lecture, class_scope
from app.services.attendance import (
    change_lecture_lifecycle,
    finalize_attendance,
    get_finalized_attendance,
    get_lecture,
)
from app.services.catalog import ensure_lecture_time_available

router = APIRouter(
    prefix="/lectures",
    tags=["lectures"],
    dependencies=[Depends(require_role("ADMIN", "HOD", "FACULTY", "STUDENT"))],
)


@router.post(
    "/{lecture_id}/start",
    response_model=LectureRead,
    dependencies=[Depends(require_role("ADMIN", "HOD", "FACULTY"))],
)
def start_lecture(lecture_id: int, session: DatabaseSession, user: CurrentUser):
    assert_can_view_lecture(session, user, lecture_id)
    return change_lecture_lifecycle(session, lecture_id, "start")


@router.post(
    "/{lecture_id}/end",
    response_model=AttendanceResponse,
    dependencies=[Depends(require_role("ADMIN", "HOD", "FACULTY"))],
)
def end_lecture(lecture_id: int, session: DatabaseSession, user: CurrentUser):
    assert_can_view_lecture(session, user, lecture_id)
    lecture = change_lecture_lifecycle(session, lecture_id, "end")
    return finalize_attendance(session, lecture)


@router.get(
    "/{lecture_id}/attendance",
    response_model=AttendanceResponse,
    dependencies=[Depends(require_role("ADMIN", "HOD", "FACULTY"))],
)
def read_lecture_attendance(
    lecture_id: int, session: DatabaseSession, user: CurrentUser
):
    assert_can_view_lecture(session, user, lecture_id)
    lecture = get_lecture(session, lecture_id)
    return get_finalized_attendance(session, lecture)


@router.post(
    "",
    response_model=LectureRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("ADMIN"))],
)
def create_lecture(payload: LectureWrite, session: DatabaseSession):
    if payload.status != "scheduled":
        raise ApiError(
            422,
            "INVALID_INITIAL_LECTURE_STATUS",
            "A new lecture must be scheduled before it can be started.",
        )
    ensure_lecture_time_available(
        session, payload.classroom_id, payload.start_time, payload.end_time
    )
    return create_record(session, Lecture, payload.model_dump())


@router.get("", response_model=PaginatedResponse[LectureRead])
def list_lectures(
    session: DatabaseSession,
    user: CurrentUser,
    limit: PageLimit = 20,
    offset: PageOffset = 0,
):
    filters = [Lecture.class_id.in_(class_scope(session, user))]
    items = list(
        session.scalars(
            select(Lecture)
            .where(*filters)
            .order_by(Lecture.start_time, Lecture.id)
            .offset(offset)
            .limit(limit)
        )
    )
    total = (
        session.scalar(select(func.count()).select_from(Lecture).where(*filters)) or 0
    )
    return PaginatedResponse[LectureRead](
        items=items, total=total, limit=limit, offset=offset
    )


@router.get("/{lecture_id}", response_model=LectureRead)
def read_lecture(lecture_id: int, session: DatabaseSession, user: CurrentUser):
    assert_can_view_lecture(session, user, lecture_id)
    return get_record(session, Lecture, lecture_id, "Lecture")


@router.put(
    "/{lecture_id}",
    response_model=LectureRead,
    dependencies=[Depends(require_role("ADMIN"))],
)
def update_lecture(lecture_id: int, payload: LectureWrite, session: DatabaseSession):
    lecture = get_lecture(session, lecture_id)
    if lecture.status == "scheduled" and payload.status in ("live", "completed"):
        raise ApiError(
            409,
            "USE_LECTURE_LIFECYCLE",
            "Use the lecture start and end endpoints to change lifecycle status.",
        )
    ensure_lecture_time_available(
        session,
        payload.classroom_id,
        payload.start_time,
        payload.end_time,
        exclude_lecture_id=lecture_id,
    )
    values = payload.model_dump()
    if lecture.status != "scheduled":
        values["status"] = lecture.status
    return update_record(session, Lecture, lecture_id, "Lecture", values)


@router.delete(
    "/{lecture_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("ADMIN"))],
)
def delete_lecture(lecture_id: int, session: DatabaseSession):
    delete_record(session, Lecture, lecture_id, "Lecture")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

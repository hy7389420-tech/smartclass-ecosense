from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import func, select

from app.core.errors import ApiError
from app.models import Classroom, Lecture
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
from app.schemas.common import PaginatedResponse
from app.schemas.resources import ClassroomRead, ClassroomWrite
from app.services.access import class_scope

router = APIRouter(
    prefix="/classrooms",
    tags=["classrooms"],
    dependencies=[Depends(require_role("ADMIN", "HOD", "FACULTY", "STUDENT"))],
)


@router.post(
    "",
    response_model=ClassroomRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("ADMIN"))],
)
def create_classroom(payload: ClassroomWrite, session: DatabaseSession):
    return create_record(session, Classroom, payload.model_dump())


@router.get("", response_model=PaginatedResponse[ClassroomRead])
def list_classrooms(
    session: DatabaseSession,
    user: CurrentUser,
    limit: PageLimit = 20,
    offset: PageOffset = 0,
):
    filters = []
    if user.role != "ADMIN":
        visible_classrooms = select(Lecture.classroom_id).where(
            Lecture.class_id.in_(class_scope(session, user))
        )
        filters.append(Classroom.id.in_(visible_classrooms))
    items = list(
        session.scalars(
            select(Classroom)
            .where(*filters)
            .order_by(Classroom.id)
            .offset(offset)
            .limit(limit)
        )
    )
    total = (
        session.scalar(select(func.count()).select_from(Classroom).where(*filters)) or 0
    )
    return PaginatedResponse[ClassroomRead](
        items=items, total=total, limit=limit, offset=offset
    )


@router.get("/{classroom_id}", response_model=ClassroomRead)
def read_classroom(classroom_id: int, session: DatabaseSession, user: CurrentUser):
    visible = session.scalar(
        select(Lecture.id).where(
            Lecture.classroom_id == classroom_id,
            Lecture.class_id.in_(class_scope(session, user)),
        )
    )
    if user.role != "ADMIN" and visible is None:
        raise ApiError(403, "FORBIDDEN", "You do not have access to this classroom.")
    return get_record(session, Classroom, classroom_id, "Classroom")


@router.put(
    "/{classroom_id}",
    response_model=ClassroomRead,
    dependencies=[Depends(require_role("ADMIN"))],
)
def update_classroom(
    classroom_id: int,
    payload: ClassroomWrite,
    session: DatabaseSession,
):
    return update_record(
        session, Classroom, classroom_id, "Classroom", payload.model_dump()
    )


@router.delete(
    "/{classroom_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("ADMIN"))],
)
def delete_classroom(classroom_id: int, session: DatabaseSession):
    delete_record(session, Classroom, classroom_id, "Classroom")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

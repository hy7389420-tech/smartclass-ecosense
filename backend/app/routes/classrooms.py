from fastapi import APIRouter, Response, status

from app.models import Classroom
from app.repositories.catalog import (
    create_record,
    delete_record,
    get_record,
    list_records,
    update_record,
)
from app.routes.dependencies import DatabaseSession, PageLimit, PageOffset
from app.schemas.common import PaginatedResponse
from app.schemas.resources import ClassroomRead, ClassroomWrite

router = APIRouter(prefix="/classrooms", tags=["classrooms"])


@router.post("", response_model=ClassroomRead, status_code=status.HTTP_201_CREATED)
def create_classroom(payload: ClassroomWrite, session: DatabaseSession):
    return create_record(session, Classroom, payload.model_dump())


@router.get("", response_model=PaginatedResponse[ClassroomRead])
def list_classrooms(
    session: DatabaseSession,
    limit: PageLimit = 20,
    offset: PageOffset = 0,
):
    items, total = list_records(session, Classroom, limit, offset)
    return PaginatedResponse[ClassroomRead](
        items=items, total=total, limit=limit, offset=offset
    )


@router.get("/{classroom_id}", response_model=ClassroomRead)
def read_classroom(classroom_id: int, session: DatabaseSession):
    return get_record(session, Classroom, classroom_id, "Classroom")


@router.put("/{classroom_id}", response_model=ClassroomRead)
def update_classroom(
    classroom_id: int,
    payload: ClassroomWrite,
    session: DatabaseSession,
):
    return update_record(
        session, Classroom, classroom_id, "Classroom", payload.model_dump()
    )


@router.delete("/{classroom_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_classroom(classroom_id: int, session: DatabaseSession):
    delete_record(session, Classroom, classroom_id, "Classroom")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

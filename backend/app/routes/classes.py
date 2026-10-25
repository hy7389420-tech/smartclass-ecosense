from fastapi import APIRouter, Response, status

from app.models import ClassGroup
from app.repositories.catalog import (
    create_record,
    delete_record,
    get_record,
    list_records,
    update_record,
)
from app.routes.dependencies import DatabaseSession, PageLimit, PageOffset
from app.schemas.common import PaginatedResponse
from app.schemas.resources import ClassRead, ClassWrite

router = APIRouter(prefix="/classes", tags=["classes"])


@router.post("", response_model=ClassRead, status_code=status.HTTP_201_CREATED)
def create_class(payload: ClassWrite, session: DatabaseSession):
    return create_record(session, ClassGroup, payload.model_dump())


@router.get("", response_model=PaginatedResponse[ClassRead])
def list_classes(
    session: DatabaseSession,
    limit: PageLimit = 20,
    offset: PageOffset = 0,
):
    items, total = list_records(session, ClassGroup, limit, offset)
    return PaginatedResponse[ClassRead](
        items=items, total=total, limit=limit, offset=offset
    )


@router.get("/{class_id}", response_model=ClassRead)
def read_class(class_id: int, session: DatabaseSession):
    return get_record(session, ClassGroup, class_id, "Class")


@router.put("/{class_id}", response_model=ClassRead)
def update_class(class_id: int, payload: ClassWrite, session: DatabaseSession):
    return update_record(session, ClassGroup, class_id, "Class", payload.model_dump())


@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class(class_id: int, session: DatabaseSession):
    delete_record(session, ClassGroup, class_id, "Class")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

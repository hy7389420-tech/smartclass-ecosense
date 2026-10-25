from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import func, select

from app.models import ClassGroup
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
from app.schemas.resources import ClassRead, ClassWrite
from app.services.access import assert_can_view_class, class_scope

router = APIRouter(
    prefix="/classes",
    tags=["classes"],
    dependencies=[Depends(require_role("ADMIN", "HOD", "FACULTY", "STUDENT"))],
)


@router.post(
    "",
    response_model=ClassRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("ADMIN"))],
)
def create_class(payload: ClassWrite, session: DatabaseSession):
    return create_record(session, ClassGroup, payload.model_dump())


@router.get("", response_model=PaginatedResponse[ClassRead])
def list_classes(
    session: DatabaseSession,
    user: CurrentUser,
    limit: PageLimit = 20,
    offset: PageOffset = 0,
):
    filters = [ClassGroup.id.in_(class_scope(session, user))]
    items = list(
        session.scalars(
            select(ClassGroup)
            .where(*filters)
            .order_by(ClassGroup.id)
            .offset(offset)
            .limit(limit)
        )
    )
    total = (
        session.scalar(select(func.count()).select_from(ClassGroup).where(*filters))
        or 0
    )
    return PaginatedResponse[ClassRead](
        items=items, total=total, limit=limit, offset=offset
    )


@router.get("/{class_id}", response_model=ClassRead)
def read_class(class_id: int, session: DatabaseSession, user: CurrentUser):
    assert_can_view_class(session, user, class_id)
    return get_record(session, ClassGroup, class_id, "Class")


@router.put(
    "/{class_id}",
    response_model=ClassRead,
    dependencies=[Depends(require_role("ADMIN"))],
)
def update_class(class_id: int, payload: ClassWrite, session: DatabaseSession):
    return update_record(session, ClassGroup, class_id, "Class", payload.model_dump())


@router.delete(
    "/{class_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("ADMIN"))],
)
def delete_class(class_id: int, session: DatabaseSession):
    delete_record(session, ClassGroup, class_id, "Class")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

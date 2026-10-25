from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import func, select

from app.core.errors import ApiError
from app.models import Department, Faculty
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
from app.schemas.resources import DepartmentRead, DepartmentWrite

router = APIRouter(
    prefix="/departments",
    tags=["departments"],
    dependencies=[Depends(require_role("ADMIN", "HOD", "FACULTY"))],
)


def _department_ids(session: DatabaseSession, user: CurrentUser) -> list[int] | None:
    if user.role == "ADMIN":
        return None
    faculty = session.scalar(select(Faculty).where(Faculty.user_id == user.id))
    if faculty is None:
        raise ApiError(
            403,
            "SCOPE_MAPPING_REQUIRED",
            "Account does not have an assigned department.",
        )
    return [faculty.department_id]


@router.post(
    "",
    response_model=DepartmentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("ADMIN"))],
)
def create_department(payload: DepartmentWrite, session: DatabaseSession):
    return create_record(session, Department, payload.model_dump())


@router.get("", response_model=PaginatedResponse[DepartmentRead])
def list_departments(
    session: DatabaseSession,
    user: CurrentUser,
    limit: PageLimit = 20,
    offset: PageOffset = 0,
):
    department_ids = _department_ids(session, user)
    filters = [Department.id.in_(department_ids)] if department_ids is not None else []
    items = list(
        session.scalars(
            select(Department)
            .where(*filters)
            .order_by(Department.id)
            .offset(offset)
            .limit(limit)
        )
    )
    total = (
        session.scalar(select(func.count()).select_from(Department).where(*filters))
        or 0
    )
    return PaginatedResponse[DepartmentRead](
        items=items, total=total, limit=limit, offset=offset
    )


@router.get("/{department_id}", response_model=DepartmentRead)
def read_department(department_id: int, session: DatabaseSession, user: CurrentUser):
    department_ids = _department_ids(session, user)
    if department_ids is not None and department_id not in department_ids:
        raise ApiError(403, "FORBIDDEN", "You do not have access to this department.")
    return get_record(session, Department, department_id, "Department")


@router.put(
    "/{department_id}",
    response_model=DepartmentRead,
    dependencies=[Depends(require_role("ADMIN"))],
)
def update_department(
    department_id: int,
    payload: DepartmentWrite,
    session: DatabaseSession,
):
    return update_record(
        session, Department, department_id, "Department", payload.model_dump()
    )


@router.delete(
    "/{department_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("ADMIN"))],
)
def delete_department(department_id: int, session: DatabaseSession):
    delete_record(session, Department, department_id, "Department")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

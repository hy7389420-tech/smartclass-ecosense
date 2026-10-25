from fastapi import APIRouter, Response, status

from app.models import Department
from app.repositories.catalog import (
    create_record,
    delete_record,
    get_record,
    list_records,
    update_record,
)
from app.routes.dependencies import DatabaseSession, PageLimit, PageOffset
from app.schemas.common import PaginatedResponse
from app.schemas.resources import DepartmentRead, DepartmentWrite

router = APIRouter(prefix="/departments", tags=["departments"])


@router.post("", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
def create_department(payload: DepartmentWrite, session: DatabaseSession):
    return create_record(session, Department, payload.model_dump())


@router.get("", response_model=PaginatedResponse[DepartmentRead])
def list_departments(
    session: DatabaseSession,
    limit: PageLimit = 20,
    offset: PageOffset = 0,
):
    items, total = list_records(session, Department, limit, offset)
    return PaginatedResponse[DepartmentRead](
        items=items, total=total, limit=limit, offset=offset
    )


@router.get("/{department_id}", response_model=DepartmentRead)
def read_department(department_id: int, session: DatabaseSession):
    return get_record(session, Department, department_id, "Department")


@router.put("/{department_id}", response_model=DepartmentRead)
def update_department(
    department_id: int,
    payload: DepartmentWrite,
    session: DatabaseSession,
):
    return update_record(
        session, Department, department_id, "Department", payload.model_dump()
    )


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(department_id: int, session: DatabaseSession):
    delete_record(session, Department, department_id, "Department")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

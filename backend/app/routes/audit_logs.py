from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.routes.dependencies import (
    DatabaseSession,
    PageLimit,
    PageOffset,
    require_role,
)
from app.schemas.common import PaginatedResponse
from app.schemas.operations import AuditLogRead
from app.services.operations import list_audit_logs

router = APIRouter(
    prefix="/audit-logs",
    tags=["audit logs"],
    dependencies=[Depends(require_role("ADMIN"))],
)


@router.get("", response_model=PaginatedResponse[AuditLogRead])
def get_audit_logs(
    session: DatabaseSession,
    entity_type: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    actor_user_id: Annotated[int | None, Query(gt=0)] = None,
    limit: PageLimit = 20,
    offset: PageOffset = 0,
) -> PaginatedResponse[AuditLogRead]:
    logs, total = list_audit_logs(
        session,
        limit,
        offset,
        entity_type,
        actor_user_id,
    )
    return PaginatedResponse[AuditLogRead](
        items=logs,
        total=total,
        limit=limit,
        offset=offset,
    )

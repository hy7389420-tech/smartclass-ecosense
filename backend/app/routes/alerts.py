from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.routes.dependencies import (
    CurrentUser,
    DatabaseSession,
    PageLimit,
    PageOffset,
    require_role,
)
from app.schemas.common import PaginatedResponse
from app.schemas.operations import AlertRead, AlertResolveWrite
from app.services.operations import list_alerts, resolve_alert

router = APIRouter(
    prefix="/alerts",
    tags=["alerts"],
    dependencies=[Depends(require_role("ADMIN", "HOD", "FACULTY"))],
)


@router.get("", response_model=PaginatedResponse[AlertRead])
def get_alerts(
    session: DatabaseSession,
    user: CurrentUser,
    unresolved_only: Annotated[bool, Query()] = True,
    limit: PageLimit = 20,
    offset: PageOffset = 0,
) -> PaginatedResponse[AlertRead]:
    alerts, total = list_alerts(session, user, limit, offset, unresolved_only)
    return PaginatedResponse[AlertRead](
        items=alerts,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/{alert_id}/resolve", response_model=AlertRead)
def post_resolve_alert(
    alert_id: int,
    payload: AlertResolveWrite,
    session: DatabaseSession,
    user: CurrentUser,
) -> AlertRead:
    return resolve_alert(session, alert_id, user, payload.reason)

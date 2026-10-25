from typing import Annotated

from fastapi import APIRouter, Body, Depends

from app.routes.dependencies import CurrentUser, DatabaseSession, require_role
from app.schemas.activity import (
    ActivityIngestResponse,
    ActivityWindowWrite,
)
from app.services.access import assert_can_view_lecture
from app.services.engagement import store_activity_windows

router = APIRouter(
    prefix="/activity",
    tags=["activity"],
    dependencies=[Depends(require_role("ADMIN", "FACULTY"))],
)


@router.post("", response_model=ActivityIngestResponse)
def create_activity_windows(
    session: DatabaseSession,
    payload: Annotated[ActivityWindowWrite | list[ActivityWindowWrite], Body()],
    user: CurrentUser,
) -> ActivityIngestResponse:
    payloads = payload if isinstance(payload, list) else [payload]
    for item in payloads:
        assert_can_view_lecture(session, user, item.lecture_id)
    return store_activity_windows(session, payloads)

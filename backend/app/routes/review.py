from fastapi import APIRouter, Depends, status

from app.routes.dependencies import (
    CurrentUser,
    DatabaseSession,
    PageLimit,
    PageOffset,
    require_role,
)
from app.schemas.events import PresenceEventRead, ReviewResolutionWrite
from app.schemas.operations import ReviewQueueRead
from app.services.operations import list_review_events, resolve_review_event

router = APIRouter(
    prefix="/review",
    tags=["review"],
    dependencies=[Depends(require_role("ADMIN", "HOD", "FACULTY"))],
)


@router.get("/events", response_model=ReviewQueueRead)
def get_review_queue(
    session: DatabaseSession,
    user: CurrentUser,
    limit: PageLimit = 20,
    offset: PageOffset = 0,
    lecture_id: int | None = None,
) -> ReviewQueueRead:
    events, total = list_review_events(session, user, limit, offset, lecture_id)
    return ReviewQueueRead(items=events, total=total, limit=limit, offset=offset)


@router.post(
    "/events/{event_id}/resolve",
    status_code=status.HTTP_200_OK,
)
def resolve_review_queue_event(
    event_id: int,
    payload: ReviewResolutionWrite,
    session: DatabaseSession,
    user: CurrentUser,
) -> PresenceEventRead:
    return resolve_review_event(session, event_id, user, payload.reason)

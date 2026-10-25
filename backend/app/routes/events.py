from typing import Annotated

from fastapi import APIRouter, Header, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.config import get_settings
from app.core.errors import ApiError
from app.models import PresenceEvent
from app.routes.dependencies import DatabaseSession, PageLimit, PageOffset
from app.schemas.common import PaginatedResponse
from app.schemas.events import (
    EventBatchResponse,
    EventIngestRequest,
    EventIngestResponse,
    PresenceEventRead,
    StoredEventType,
)
from app.services.camera_auth import authenticate_camera_key
from app.services.events import ingest_event

router = APIRouter(prefix="/events", tags=["events"])
CameraKey = Annotated[str | None, Header(alias="X-Camera-Key")]
EventTypeFilter = Annotated[StoredEventType | None, Query()]
FlaggedFilter = Annotated[bool | None, Query()]
PositiveIdFilter = Annotated[int | None, Query(gt=0)]


@router.post(
    "",
    response_model=EventIngestResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"model": EventIngestResponse, "description": "Idempotent duplicate."},
        202: {
            "model": EventIngestResponse,
            "description": "Event saved for manual review.",
        },
        401: {"description": "Camera key is missing or invalid."},
        403: {"description": "Camera is assigned to another classroom."},
        404: {"description": "Lecture was not found."},
    },
)
def create_event(
    payload: EventIngestRequest,
    session: DatabaseSession,
    camera_key: CameraKey = None,
) -> Response:
    camera = authenticate_camera_key(session, camera_key)
    result = ingest_event(session, payload, camera)
    response_status = (
        status.HTTP_200_OK
        if result.duplicate
        else status.HTTP_202_ACCEPTED
        if result.flagged_for_review
        else status.HTTP_201_CREATED
    )
    return JSONResponse(
        status_code=response_status,
        content=result.model_dump(mode="json"),
    )


@router.post(
    "/batch",
    response_model=EventBatchResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {
            "model": EventBatchResponse,
            "description": "All events were duplicates.",
        },
        202: {
            "model": EventBatchResponse,
            "description": "At least one event was saved for review.",
        },
        401: {"description": "Camera key is missing or invalid."},
        403: {"description": "Camera is assigned to another classroom."},
        404: {"description": "A lecture was not found."},
    },
)
def create_events_batch(
    payload: list[EventIngestRequest],
    session: DatabaseSession,
    camera_key: CameraKey = None,
) -> Response:
    settings = get_settings()
    if not payload:
        raise ApiError(422, "EMPTY_BATCH", "At least one event is required.")
    if len(payload) > settings.max_event_batch_size:
        raise ApiError(
            422,
            "BATCH_TOO_LARGE",
            f"Batch size cannot exceed {settings.max_event_batch_size}.",
        )

    camera = authenticate_camera_key(session, camera_key)
    results = [ingest_event(session, event, camera) for event in payload]
    response = EventBatchResponse(
        items=results,
        accepted_count=sum(
            not item.duplicate and not item.flagged_for_review for item in results
        ),
        flagged_count=sum(item.flagged_for_review for item in results),
        duplicate_count=sum(item.duplicate for item in results),
    )
    response_status = (
        status.HTTP_200_OK
        if response.duplicate_count == len(response.items)
        else status.HTTP_202_ACCEPTED
        if response.flagged_count
        else status.HTTP_201_CREATED
    )
    return JSONResponse(
        status_code=response_status,
        content=response.model_dump(mode="json"),
    )


@router.get("", response_model=PaginatedResponse[PresenceEventRead])
def list_events(
    session: DatabaseSession,
    lecture_id: PositiveIdFilter = None,
    student_id: PositiveIdFilter = None,
    event_type: EventTypeFilter = None,
    flagged_for_review: FlaggedFilter = None,
    limit: PageLimit = 20,
    offset: PageOffset = 0,
):
    filters = []
    if lecture_id is not None:
        filters.append(PresenceEvent.lecture_id == lecture_id)
    if student_id is not None:
        filters.append(PresenceEvent.student_id == student_id)
    if event_type is not None:
        filters.append(PresenceEvent.event_type == event_type)
    if flagged_for_review is not None:
        filters.append(PresenceEvent.flagged_for_review == flagged_for_review)

    items = list(
        session.scalars(
            select(PresenceEvent)
            .where(*filters)
            .order_by(PresenceEvent.timestamp_utc, PresenceEvent.id)
            .offset(offset)
            .limit(limit)
        )
    )
    total = (
        session.scalar(select(func.count()).select_from(PresenceEvent).where(*filters))
        or 0
    )
    return PaginatedResponse[PresenceEventRead](
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )

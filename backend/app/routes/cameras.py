from typing import Annotated

from fastapi import APIRouter, Header

from app.routes.dependencies import DatabaseSession
from app.schemas.operations import HeartbeatRead
from app.services.operations import camera_heartbeat

router = APIRouter(prefix="/cameras", tags=["cameras"])
CameraKey = Annotated[str | None, Header(alias="X-Camera-Key")]


@router.post("/{camera_id}/heartbeat", response_model=HeartbeatRead)
def post_camera_heartbeat(
    camera_id: int,
    session: DatabaseSession,
    camera_key: CameraKey = None,
) -> HeartbeatRead:
    return camera_heartbeat(session, camera_id, camera_key)

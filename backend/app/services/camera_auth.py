import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import ApiError
from app.models import Camera


def hash_camera_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def authenticate_camera_key(session: Session, api_key: str | None) -> Camera | None:
    settings = get_settings()
    if not api_key:
        if settings.require_camera_key:
            raise ApiError(
                401, "CAMERA_KEY_REQUIRED", "Camera authentication required."
            )
        return None

    presented_hash = hash_camera_key(api_key)
    matched_camera: Camera | None = None
    cameras = session.scalars(select(Camera)).all()
    for camera in cameras:
        if secrets.compare_digest(camera.api_key_hash, presented_hash):
            matched_camera = camera

    if matched_camera is None:
        raise ApiError(401, "INVALID_CAMERA_KEY", "Camera authentication failed.")
    return matched_camera

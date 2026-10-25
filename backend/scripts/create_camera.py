import argparse
import secrets

from app.core.errors import ApiError
from app.database import session_scope
from app.models import Camera, Classroom
from app.services.camera_auth import hash_camera_key


def create_camera(classroom_id: int, name: str) -> tuple[int, str]:
    camera_name = name.strip()
    if not camera_name or len(camera_name) > 120:
        raise ValueError("Camera name must contain 1 to 120 characters.")

    api_key = secrets.token_urlsafe(32)
    with session_scope() as session:
        classroom = session.get(Classroom, classroom_id)
        if classroom is None:
            raise ApiError(404, "CLASSROOM_NOT_FOUND", "Classroom was not found.")

        camera = Camera(
            classroom_id=classroom_id,
            name=camera_name,
            api_key_hash=hash_camera_key(api_key),
        )
        session.add(camera)
        session.flush()
        camera_id = camera.id

    return camera_id, api_key


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a camera API key.")
    parser.add_argument("--classroom-id", type=int, required=True)
    parser.add_argument("--name", required=True)
    arguments = parser.parse_args()

    try:
        camera_id, api_key = create_camera(arguments.classroom_id, arguments.name)
    except (ApiError, ValueError) as exc:
        message = exc.message if isinstance(exc, ApiError) else str(exc)
        parser.error(message)

    print(f"Camera created: id={camera_id}")
    print("Save this key now; it is only shown once:")
    print(api_key)


if __name__ == "__main__":
    main()

from fastapi import APIRouter, Request, Response, status

from app.config import get_settings
from app.core.errors import ApiError
from app.models import User
from app.routes.dependencies import CurrentUser, DatabaseSession
from app.schemas.auth import (
    AccessTokenRead,
    ChangePasswordRequest,
    LoginRequest,
    UserRead,
)
from app.services.auth import (
    authenticate_login,
    create_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AccessTokenRead)
def login(payload: LoginRequest, request: Request, session: DatabaseSession):
    client_key = request.client.host if request.client is not None else "unknown"
    user = authenticate_login(session, payload.email, payload.password, client_key)
    settings = get_settings()
    return AccessTokenRead(
        access_token=create_access_token(user),
        expires_in=settings.jwt_access_token_minutes * 60,
    )


@router.get("/me", response_model=UserRead)
def read_current_user(user: CurrentUser) -> User:
    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    user: CurrentUser,
    session: DatabaseSession,
) -> Response:
    if not verify_password(payload.current_password, user.password_hash):
        raise ApiError(
            400,
            "CURRENT_PASSWORD_INCORRECT",
            "Current password is incorrect.",
        )
    if payload.current_password == payload.new_password:
        raise ApiError(
            422,
            "PASSWORD_UNCHANGED",
            "New password must be different from the current password.",
        )
    user.password_hash = hash_password(payload.new_password)
    user.token_version += 1
    session.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

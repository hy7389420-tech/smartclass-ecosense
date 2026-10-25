import secrets
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import Lock
from time import monotonic
from typing import Annotated

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import ApiError
from app.database import get_db
from app.models import User

password_hasher = PasswordHasher()
dummy_password_hash = password_hasher.hash(secrets.token_urlsafe(32))
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError):
        return False


def create_access_token(user: User, now: datetime | None = None) -> str:
    settings = get_settings()
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=settings.jwt_access_token_minutes)
    return jwt.encode(
        {
            "sub": str(user.id),
            "iat": issued_at,
            "exp": expires_at,
            "ver": user.token_version,
        },
        settings.jwt_secret_key,
        algorithm="HS256",
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(401, "UNAUTHORIZED", "Authentication is required.")

    settings = get_settings()
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=["HS256"],
            options={"require": ["sub", "iat", "exp", "ver"]},
        )
        user_id = int(claims["sub"])
        token_version = int(claims["ver"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise ApiError(
            401, "UNAUTHORIZED", "Authentication token is invalid or expired."
        )

    user = session.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active or user.token_version != token_version:
        raise ApiError(
            401, "UNAUTHORIZED", "Authentication token is invalid or expired."
        )
    return user


class LoginRateLimiter:
    def __init__(self) -> None:
        self._attempts: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def consume(self, key: str) -> None:
        settings = get_settings()
        now = monotonic()
        with self._lock:
            attempts = self._attempts[key]
            while attempts and now - attempts[0] >= settings.auth_login_window_seconds:
                attempts.popleft()
            if len(attempts) >= settings.auth_login_max_attempts:
                raise ApiError(
                    429,
                    "LOGIN_RATE_LIMITED",
                    "Too many login attempts. Please try again later.",
                )
            self._attempts[key].append(monotonic())

    def clear(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)


login_rate_limiter = LoginRateLimiter()


def authenticate_login(
    session: Session,
    email: str,
    password: str,
    client_key: str,
    hash_verifier: Callable[[str, str], bool] = verify_password,
) -> User:
    limiter_key = client_key
    login_rate_limiter.consume(limiter_key)
    normalized_email = email.strip().lower()
    user = session.scalar(select(User).where(User.email == normalized_email))
    password_hash = user.password_hash if user is not None else dummy_password_hash
    password_valid = hash_verifier(password, password_hash)
    if user is None or not password_valid or not user.is_active:
        raise ApiError(401, "INVALID_CREDENTIALS", "Email or password is incorrect.")
    login_rate_limiter.clear(limiter_key)
    return user

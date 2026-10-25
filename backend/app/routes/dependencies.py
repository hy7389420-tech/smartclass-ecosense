from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.database import get_db
from app.models import User
from app.services.auth import get_current_user

DatabaseSession = Annotated[Session, Depends(get_db)]
PageLimit = Annotated[int, Query(ge=1, le=100)]
PageOffset = Annotated[int, Query(ge=0)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*allowed_roles: str) -> Callable[..., User]:
    def check_role(user: CurrentUser) -> User:
        if user.role not in allowed_roles:
            raise ApiError(403, "FORBIDDEN", "You do not have access to this resource.")
        return user

    return check_role

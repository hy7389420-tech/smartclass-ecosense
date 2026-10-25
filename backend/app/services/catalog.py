from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import Lecture


def ensure_lecture_time_available(
    session: Session,
    classroom_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_lecture_id: int | None = None,
) -> None:
    statement = select(Lecture.id).where(
        Lecture.classroom_id == classroom_id,
        Lecture.start_time < end_time,
        Lecture.end_time > start_time,
    )
    if exclude_lecture_id is not None:
        statement = statement.where(Lecture.id != exclude_lecture_id)
    if session.scalar(statement.limit(1)) is not None:
        raise ApiError(
            409,
            "LECTURE_TIME_CONFLICT",
            "The classroom already has a lecture during that time.",
        )

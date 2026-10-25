from typing import TypeVar

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import Base

ModelT = TypeVar("ModelT", bound=Base)


def list_records(
    session: Session, model: type[ModelT], limit: int, offset: int
) -> tuple[list[ModelT], int]:
    items = list(
        session.scalars(select(model).order_by(model.id).offset(offset).limit(limit))
    )
    total = session.scalar(select(func.count()).select_from(model)) or 0
    return items, total


def get_record(
    session: Session, model: type[ModelT], record_id: int, resource_name: str
) -> ModelT:
    record = session.get(model, record_id)
    if record is None:
        raise ApiError(404, "NOT_FOUND", f"{resource_name} was not found.")
    return record


def create_record(
    session: Session, model: type[ModelT], values: dict[str, object]
) -> ModelT:
    record = model(**values)
    session.add(record)
    flush_record(session)
    return record


def update_record(
    session: Session,
    model: type[ModelT],
    record_id: int,
    resource_name: str,
    values: dict[str, object],
) -> ModelT:
    record = get_record(session, model, record_id, resource_name)
    for key, value in values.items():
        setattr(record, key, value)
    flush_record(session)
    return record


def delete_record(
    session: Session, model: type[ModelT], record_id: int, resource_name: str
) -> None:
    record = get_record(session, model, record_id, resource_name)
    session.delete(record)
    flush_record(session)


def flush_record(session: Session) -> None:
    try:
        session.flush()
    except IntegrityError as exc:
        raise ApiError(
            409,
            "CONFLICT",
            "The request conflicts with existing data or a database relationship.",
        ) from exc

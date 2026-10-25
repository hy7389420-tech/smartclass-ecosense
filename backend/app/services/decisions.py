from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import Suggestion, SuggestionDecision
from app.schemas.suggestions import (
    SuggestionDecisionRead,
    SuggestionDecisionWrite,
)


def record_suggestion_decision(
    session: Session,
    suggestion_id: int,
    decided_by: int,
    payload: SuggestionDecisionWrite,
) -> SuggestionDecisionRead:
    suggestion = session.get(Suggestion, suggestion_id)
    if suggestion is None:
        raise ApiError(404, "SUGGESTION_NOT_FOUND", "Suggestion was not found.")

    suggestion.status = payload.decision
    decision = SuggestionDecision(
        suggestion_id=suggestion.id,
        decision=payload.decision,
        decided_by=decided_by,
        note=payload.note.strip() if payload.note is not None else None,
    )
    session.add(decision)
    session.flush()
    return SuggestionDecisionRead.model_validate(decision)


def read_lecture_suggestion_decisions(
    session: Session, lecture_id: int
) -> list[SuggestionDecisionRead]:
    rows = session.scalars(
        select(SuggestionDecision)
        .join(Suggestion, Suggestion.id == SuggestionDecision.suggestion_id)
        .where(Suggestion.lecture_id == lecture_id)
        .order_by(SuggestionDecision.decided_at, SuggestionDecision.id)
    )
    return [SuggestionDecisionRead.model_validate(row) for row in rows]

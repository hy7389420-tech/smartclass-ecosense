from fastapi import APIRouter, Depends, status

from app.core.errors import ApiError
from app.models import Suggestion
from app.routes.dependencies import CurrentUser, DatabaseSession, require_role
from app.schemas.activity import EngagementRead
from app.schemas.suggestions import (
    SuggestionDecisionRead,
    SuggestionDecisionWrite,
    SuggestionRead,
)
from app.services.access import assert_can_view_lecture
from app.services.decisions import (
    read_lecture_suggestion_decisions,
    record_suggestion_decision,
)
from app.services.engagement import get_lecture_engagement, get_lecture_suggestions

router = APIRouter(
    prefix="/lectures",
    tags=["engagement"],
    dependencies=[Depends(require_role("ADMIN", "HOD", "FACULTY"))],
)
decision_router = APIRouter(
    prefix="/suggestions",
    tags=["suggestions"],
    dependencies=[Depends(require_role("ADMIN", "FACULTY"))],
)


@router.get("/{lecture_id}/engagement", response_model=EngagementRead)
def read_lecture_engagement(
    lecture_id: int, session: DatabaseSession, user: CurrentUser
) -> EngagementRead:
    assert_can_view_lecture(session, user, lecture_id)
    return get_lecture_engagement(session, lecture_id)


@router.get("/{lecture_id}/suggestions", response_model=list[SuggestionRead])
def read_lecture_suggestions(
    lecture_id: int, session: DatabaseSession, user: CurrentUser
) -> list[SuggestionRead]:
    assert_can_view_lecture(session, user, lecture_id)
    return get_lecture_suggestions(session, lecture_id)


@router.get(
    "/{lecture_id}/suggestions/log",
    response_model=list[SuggestionDecisionRead],
)
def read_suggestion_decision_log(
    lecture_id: int,
    session: DatabaseSession,
    user: CurrentUser,
) -> list[SuggestionDecisionRead]:
    assert_can_view_lecture(session, user, lecture_id)
    return read_lecture_suggestion_decisions(session, lecture_id)


@decision_router.post(
    "/{suggestion_id}/decision",
    response_model=SuggestionDecisionRead,
    status_code=status.HTTP_201_CREATED,
)
def decide_suggestion(
    suggestion_id: int,
    payload: SuggestionDecisionWrite,
    session: DatabaseSession,
    user: CurrentUser,
) -> SuggestionDecisionRead:
    suggestion = session.get(Suggestion, suggestion_id)
    if suggestion is None:
        raise ApiError(404, "SUGGESTION_NOT_FOUND", "Suggestion was not found.")
    assert_can_view_lecture(session, user, suggestion.lecture_id)
    return record_suggestion_decision(session, suggestion_id, user.id, payload)

from fastapi import APIRouter, Depends

from app.config import get_settings
from app.core.errors import ApiError
from app.routes.dependencies import CurrentUser, DatabaseSession, require_role
from app.schemas.assistant import AssistantAnswer, AssistantQuestion
from app.services.assistant import answer_question

router = APIRouter(
    prefix="/ai",
    tags=["HOD assistant"],
    dependencies=[Depends(require_role("ADMIN", "HOD"))],
)


@router.post("/ask", response_model=AssistantAnswer)
def ask_question(
    request: AssistantQuestion, session: DatabaseSession, user: CurrentUser
) -> AssistantAnswer:
    if not get_settings().ai_assistant_enabled:
        raise ApiError(
            503,
            "AI_ASSISTANT_DISABLED",
            "The HOD assistant is disabled.",
        )
    return answer_question(session, user, request.question)

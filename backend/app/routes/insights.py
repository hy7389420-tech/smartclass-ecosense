from fastapi import APIRouter, Depends

from app.routes.dependencies import CurrentUser, DatabaseSession, require_role
from app.schemas.insights import InsightRead
from app.services.access import assert_can_view_lecture
from app.services.insights import regenerate_lecture_insights

router = APIRouter(
    prefix="/insights",
    tags=["insights"],
    dependencies=[Depends(require_role("ADMIN", "HOD", "FACULTY"))],
)


@router.get("/{lecture_id}", response_model=list[InsightRead])
def read_lecture_insights(
    lecture_id: int, session: DatabaseSession, user: CurrentUser
) -> list[InsightRead]:
    assert_can_view_lecture(session, user, lecture_id)
    return regenerate_lecture_insights(session, lecture_id)

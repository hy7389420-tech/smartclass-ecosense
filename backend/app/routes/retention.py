from fastapi import APIRouter, Depends

from app.routes.dependencies import CurrentUser, DatabaseSession, require_role
from app.schemas.reports import RetentionRequest, RetentionRunRead
from app.services.reports import run_retention

router = APIRouter(
    prefix="/admin/retention",
    tags=["retention"],
    dependencies=[Depends(require_role("ADMIN"))],
)


@router.post("/run", response_model=RetentionRunRead)
def post_retention_run(
    payload: RetentionRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> RetentionRunRead:
    return RetentionRunRead.model_validate(
        run_retention(session, user.id, dry_run=payload.dry_run)
    )

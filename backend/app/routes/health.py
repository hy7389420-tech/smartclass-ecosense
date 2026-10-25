import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app import database

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", response_model=None)
def readiness() -> dict[str, str] | JSONResponse:
    try:
        database.check_database()
    except SQLAlchemyError as exc:
        logger.warning(
            "database readiness check failed",
            extra={"error_type": type(exc).__name__},
        )
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "Database is unavailable.",
                }
            },
        )
    return {"status": "ready"}

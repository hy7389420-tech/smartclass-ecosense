from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging_config import configure_logging
from app.routes.activity import router as activity_router
from app.routes.analytics import router as analytics_router
from app.routes.auth import router as auth_router
from app.routes.classes import router as classes_router
from app.routes.classrooms import router as classrooms_router
from app.routes.dashboard import router as dashboard_router
from app.routes.departments import router as departments_router
from app.routes.engagement import (
    decision_router as suggestion_decision_router,
)
from app.routes.engagement import router as engagement_router
from app.routes.events import router as events_router
from app.routes.health import router as health_router
from app.routes.insights import router as insights_router
from app.routes.lectures import router as lectures_router
from app.routes.students import router as students_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging(get_settings().log_level)
    yield


app = FastAPI(
    title="SmartClass EcoSense API",
    version="0.1.0",
    lifespan=lifespan,
)
register_exception_handlers(app)
app.include_router(health_router)
app.include_router(activity_router)
app.include_router(analytics_router)
app.include_router(auth_router)
app.include_router(departments_router)
app.include_router(dashboard_router)
app.include_router(events_router)
app.include_router(classes_router)
app.include_router(classrooms_router)
app.include_router(students_router)
app.include_router(lectures_router)
app.include_router(insights_router)
app.include_router(engagement_router)
app.include_router(suggestion_decision_router)

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging_config import configure_logging
from app.core.security import RequestProtectionMiddleware
from app.routes.activity import router as activity_router
from app.routes.alerts import router as alerts_router
from app.routes.analytics import router as analytics_router
from app.routes.assistant import router as assistant_router
from app.routes.audit_logs import router as audit_logs_router
from app.routes.auth import router as auth_router
from app.routes.cameras import router as cameras_router
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
from app.routes.reports import router as reports_router
from app.routes.retention import router as retention_router
from app.routes.review import router as review_router
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Camera-Key"],
)
app.add_middleware(RequestProtectionMiddleware)
app.include_router(health_router)
app.include_router(activity_router)
app.include_router(assistant_router)
app.include_router(alerts_router)
app.include_router(analytics_router)
app.include_router(audit_logs_router)
app.include_router(auth_router)
app.include_router(cameras_router)
app.include_router(departments_router)
app.include_router(dashboard_router)
app.include_router(events_router)
app.include_router(review_router)
app.include_router(reports_router)
app.include_router(retention_router)
app.include_router(classes_router)
app.include_router(classrooms_router)
app.include_router(students_router)
app.include_router(lectures_router)
app.include_router(insights_router)
app.include_router(engagement_router)
app.include_router(suggestion_decision_router)

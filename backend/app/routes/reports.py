from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.routes.dependencies import (
    CurrentUser,
    DatabaseSession,
    require_role,
)
from app.schemas.reports import (
    ReportFormat,
    ReportPeriod,
    SessionReportRead,
    SummaryReportRead,
)
from app.services.reports import (
    build_session_report,
    build_summary_report,
    session_report_csv,
    summary_report_csv,
)

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(require_role("ADMIN", "HOD", "FACULTY", "STUDENT"))],
)


@router.get(
    "/lectures/{lecture_id}",
    response_model=SessionReportRead,
    responses={200: {"content": {"text/csv": {"schema": {"type": "string"}}}}},
)
def read_session_report(
    lecture_id: int,
    session: DatabaseSession,
    user: CurrentUser,
    report_format: Annotated[ReportFormat, Query(alias="format")] = "json",
) -> SessionReportRead | Response:
    report = build_session_report(session, lecture_id, user)
    if report_format == "csv":
        return Response(
            content=session_report_csv(report),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="session-{lecture_id}.csv"'
            },
        )
    return report


@router.get(
    "/summaries",
    response_model=SummaryReportRead,
    responses={200: {"content": {"text/csv": {"schema": {"type": "string"}}}}},
)
def read_summary_report(
    session: DatabaseSession,
    user: CurrentUser,
    period: Annotated[ReportPeriod, Query()] = "daily",
    report_date: Annotated[date | None, Query(alias="date")] = None,
    report_format: Annotated[ReportFormat, Query(alias="format")] = "json",
) -> SummaryReportRead | Response:
    report = build_summary_report(session, user, period, report_date)
    if report_format == "csv":
        return Response(
            content=summary_report_csv(report),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{period}-summary-'
                    f'{report.start_date.isoformat()}.csv"'
                )
            },
        )
    return report

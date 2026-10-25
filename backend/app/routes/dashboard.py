from fastapi import APIRouter
from sqlalchemy import func, select

from app.models import PresenceEvent
from app.routes.dependencies import DatabaseSession
from app.schemas.dashboard import DashboardCards, DashboardRead
from app.services.attendance import (
    attendance_snapshot,
    camera_status,
    get_lecture,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/{lecture_id}", response_model=DashboardRead)
def read_dashboard(lecture_id: int, session: DatabaseSession):
    lecture = get_lecture(session, lecture_id)
    attendance = attendance_snapshot(session, lecture)
    pending_review_count = (
        session.scalar(
            select(func.count())
            .select_from(PresenceEvent)
            .where(
                PresenceEvent.lecture_id == lecture.id,
                PresenceEvent.flagged_for_review.is_(True),
            )
        )
        or 0
    )
    return DashboardRead(
        lecture_id=lecture.id,
        lecture_status=lecture.status,
        cards=DashboardCards(
            total_students=attendance.total_students,
            present=attendance.present,
            inside=attendance.inside,
            outside=attendance.outside,
            absent=attendance.absent,
            occupancy_percent=attendance.occupancy_percent,
        ),
        students=attendance.records,
        camera_status=camera_status(session, lecture.classroom_id),
        pending_review_count=pending_review_count,
    )

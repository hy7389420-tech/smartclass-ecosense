from typing import Literal

from app.schemas.attendance import AttendanceStudentRead
from app.schemas.common import ORMModel


class DashboardCards(ORMModel):
    total_students: int
    present: int
    inside: int
    outside: int
    absent: int
    occupancy_percent: float


class DashboardRead(ORMModel):
    lecture_id: int
    lecture_status: str
    cards: DashboardCards
    students: list[AttendanceStudentRead]
    camera_status: Literal["Online", "Camera Offline"]
    pending_review_count: int

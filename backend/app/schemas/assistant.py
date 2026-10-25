from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.schemas.common import ORMModel

AssistantStatus = Literal["answered", "refused"]
AssistantIntent = Literal[
    "highest_outside_by_class",
    "weekly_utilization",
    "underutilized_rooms",
    "unusual_activity_yesterday",
    "room_average_occupancy",
    "monthly_comparison",
]


class AssistantQuestion(ORMModel):
    question: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=3, max_length=500),
    ]


class AssistantAnswer(ORMModel):
    status: AssistantStatus
    intent: AssistantIntent | None
    answer: str = Field(min_length=1, max_length=2000)

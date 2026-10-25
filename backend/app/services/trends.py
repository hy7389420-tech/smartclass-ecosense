from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OutsideDurationTrend:
    status: str
    current_average_minutes: float | None
    previous_average_minutes: float | None
    history_count: int
    history_required: int


def compare_outside_duration(
    current_outside_minutes: Sequence[float],
    previous_lecture_averages: Sequence[float],
    *,
    min_history: int = 3,
) -> OutsideDurationTrend:
    if min_history < 1:
        raise ValueError("min_history must be positive.")
    if any(value < 0 for value in current_outside_minutes):
        raise ValueError("Outside durations cannot be negative.")
    if any(value < 0 for value in previous_lecture_averages):
        raise ValueError("Outside durations cannot be negative.")

    current_average = (
        sum(current_outside_minutes) / len(current_outside_minutes)
        if current_outside_minutes
        else None
    )
    history_count = len(previous_lecture_averages)
    if current_average is None or history_count < min_history:
        return OutsideDurationTrend(
            status="insufficient_history",
            current_average_minutes=(
                round(current_average, 2) if current_average is not None else None
            ),
            previous_average_minutes=None,
            history_count=history_count,
            history_required=min_history,
        )

    previous_average = sum(previous_lecture_averages) / history_count
    return OutsideDurationTrend(
        status="higher" if current_average > previous_average else "not_higher",
        current_average_minutes=round(current_average, 2),
        previous_average_minutes=round(previous_average, 2),
        history_count=history_count,
        history_required=min_history,
    )

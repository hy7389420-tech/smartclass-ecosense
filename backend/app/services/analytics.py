from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal

UtilizationLabel = Literal["no_data", "underutilized", "well_utilized", "overutilized"]
OutsidePeriod = Literal["day", "week", "month"]

# Configurable defaults for advisory room-utilization recommendations.
# These are not measured baselines.
UNDERUTILIZED_CUTOFF_PERCENT = 40.0
OVERUTILIZED_CUTOFF_PERCENT = 90.0
MIN_RECOMMENDATION_LECTURES = 2
RECOMMENDATION_LABEL = "Simulated resource optimization suggestion"
NOT_ENOUGH_DATA = "Not enough data"


@dataclass(frozen=True, slots=True)
class OccupancyEvent:
    student_id: int
    event_type: str
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class OccupancyBucket:
    timestamp: datetime
    average_occupied: float


@dataclass(frozen=True, slots=True)
class UnusedPeriod:
    start: datetime
    end: datetime


@dataclass(frozen=True, slots=True)
class LectureAnalytics:
    average_occupancy: float
    peak_occupancy: int
    peak_time: datetime | None
    utilization_percent: float
    exit_count: int
    outside_minutes: float
    total_duration_seconds: float
    occupied_person_seconds: float
    occupancy_by_minute: tuple[OccupancyBucket, ...]
    unused_periods: tuple[UnusedPeriod, ...]


def analyze_lecture(
    events: Sequence[OccupancyEvent],
    lecture_start: datetime,
    lecture_end: datetime,
    capacity: int,
) -> LectureAnalytics:
    start = _as_utc(lecture_start, "lecture_start")
    end = _as_utc(lecture_end, "lecture_end")
    if end <= start:
        raise ValueError("lecture_end must be after lecture_start.")
    if capacity <= 0:
        raise ValueError("capacity must be positive.")

    indexed_events = []
    for index, event in enumerate(events):
        timestamp = _as_utc(event.timestamp, "event timestamp")
        if event.event_type not in {"ENTRY", "EXIT", "RETURN"}:
            raise ValueError(f"Unsupported occupancy event type: {event.event_type}.")
        if start <= timestamp < end:
            indexed_events.append((timestamp, index, event))
    indexed_events.sort(key=lambda item: (item[0], item[1]))

    inside: set[int] = set()
    outside_started: dict[int, datetime] = {}
    outside_seconds = 0.0
    occupied_person_seconds = 0.0
    peak_occupancy = 0
    peak_time: datetime | None = None
    buckets: list[OccupancyBucket] = []
    unused_periods: list[UnusedPeriod] = []
    unused_start: datetime | None = None
    exit_count = 0
    event_index = 0
    bucket_start = start

    def apply_event(event: OccupancyEvent, timestamp: datetime) -> None:
        nonlocal outside_seconds, exit_count
        student_id = event.student_id
        if event.event_type == "ENTRY" or event.event_type == "RETURN":
            if student_id not in inside:
                if student_id in outside_started:
                    outside_seconds += (
                        timestamp - outside_started.pop(student_id)
                    ).total_seconds()
                inside.add(student_id)
        else:
            exit_count += 1
            if student_id in inside:
                inside.remove(student_id)
                outside_started[student_id] = timestamp

    def integrate(start_at: datetime, end_at: datetime) -> float:
        nonlocal occupied_person_seconds, peak_occupancy, peak_time
        seconds = (end_at - start_at).total_seconds()
        if seconds <= 0:
            return 0.0
        occupancy = len(inside)
        occupied_person_seconds += occupancy * seconds
        if occupancy > peak_occupancy:
            peak_occupancy = occupancy
            peak_time = start_at
        return occupancy * seconds

    while bucket_start < end:
        bucket_end = min(bucket_start + timedelta(minutes=1), end)
        while (
            event_index < len(indexed_events)
            and indexed_events[event_index][0] <= bucket_start
        ):
            timestamp, _, event = indexed_events[event_index]
            apply_event(event, timestamp)
            event_index += 1

        cursor = bucket_start
        bucket_person_seconds = 0.0
        while (
            event_index < len(indexed_events)
            and indexed_events[event_index][0] < bucket_end
        ):
            timestamp, _, event = indexed_events[event_index]
            bucket_person_seconds += integrate(cursor, timestamp)
            cursor = timestamp
            apply_event(event, timestamp)
            event_index += 1
        bucket_person_seconds += integrate(cursor, bucket_end)
        bucket_seconds = (bucket_end - bucket_start).total_seconds()
        bucket_average = bucket_person_seconds / bucket_seconds
        buckets.append(OccupancyBucket(bucket_start, round(bucket_average, 4)))

        if bucket_person_seconds == 0:
            if unused_start is None:
                unused_start = bucket_start
        elif unused_start is not None:
            unused_periods.append(UnusedPeriod(unused_start, bucket_start))
            unused_start = None
        bucket_start = bucket_end

    if unused_start is not None:
        unused_periods.append(UnusedPeriod(unused_start, end))

    for outside_start in outside_started.values():
        outside_seconds += (end - outside_start).total_seconds()

    total_duration_seconds = (end - start).total_seconds()
    average_occupancy = occupied_person_seconds / total_duration_seconds
    return LectureAnalytics(
        average_occupancy=round(average_occupancy, 4),
        peak_occupancy=peak_occupancy,
        peak_time=peak_time,
        utilization_percent=round(average_occupancy / capacity * 100, 2),
        exit_count=exit_count,
        outside_minutes=round(outside_seconds / 60, 2),
        total_duration_seconds=total_duration_seconds,
        occupied_person_seconds=occupied_person_seconds,
        occupancy_by_minute=tuple(buckets),
        unused_periods=tuple(unused_periods),
    )


def classify_utilization(
    utilization_percent: float,
    under_cutoff_percent: float = 40,
    over_cutoff_percent: float = 90,
    *,
    has_data: bool = True,
) -> UtilizationLabel:
    if not has_data:
        return "no_data"
    if utilization_percent < under_cutoff_percent:
        return "underutilized"
    if utilization_percent > over_cutoff_percent:
        return "overutilized"
    return "well_utilized"


def utilization_suggestion(
    room_name: str, utilization_percent: float, classification: UtilizationLabel
) -> str:
    if classification == "no_data":
        return (
            f"{room_name} has no completed lecture occupancy data in this period. "
            "Occupancy data can support resource optimization when available."
        )
    if classification == "underutilized":
        return (
            f"{room_name} average utilization is {utilization_percent:.0f}%; "
            "consider reviewing room size and scheduling. Occupancy data can "
            "support resource optimization."
        )
    if classification == "overutilized":
        return (
            f"{room_name} average utilization is {utilization_percent:.0f}%; "
            "consider reviewing room capacity and scheduling. Occupancy data "
            "can support resource optimization."
        )
    return (
        f"{room_name} average utilization is {utilization_percent:.0f}%. "
        "Occupancy data can support resource optimization."
    )


def utilization_status(classification: UtilizationLabel) -> str:
    if classification == "well_utilized":
        return "balanced"
    return classification


def utilization_recommendations(
    classroom_name: str,
    utilization_percent: float,
    classification: UtilizationLabel,
    *,
    lecture_count: int,
    classroom_count: int,
) -> list[str]:
    if (
        classroom_count < 2
        or lecture_count < MIN_RECOMMENDATION_LECTURES
        or classification == "no_data"
    ):
        return [NOT_ENOUGH_DATA]

    if classification == "underutilized":
        advice = (
            f"review scheduling for {classroom_name}; it is used at "
            f"{utilization_percent:.0f}% average utilization."
        )
    elif classification == "overutilized":
        advice = (
            f"review capacity or scheduling for {classroom_name}; it is used at "
            f"{utilization_percent:.0f}% average utilization."
        )
    else:
        advice = (
            f"continue the existing schedule for {classroom_name}; average "
            f"utilization is {utilization_percent:.0f}%."
        )
    return [f"{RECOMMENDATION_LABEL}: {advice}"]


def period_start(value: datetime, period: OutsidePeriod) -> date:
    current_date = _as_utc(value, "period timestamp").date()
    if period == "day":
        return current_date
    if period == "week":
        return current_date - timedelta(days=current_date.weekday())
    return current_date.replace(day=1)


def aggregate_outside_duration(
    rows: Sequence[tuple[datetime, float, int]], period: OutsidePeriod
) -> list[tuple[date, float, int]]:
    totals: dict[date, list[float | int]] = defaultdict(lambda: [0.0, 0])
    lectures_by_period: dict[date, set[int]] = defaultdict(set)
    for lecture_start, outside_minutes, lecture_id in rows:
        key = period_start(lecture_start, period)
        totals[key][0] += outside_minutes
        lectures_by_period[key].add(lecture_id)
    return [
        (key, round(float(values[0]), 2), len(lectures_by_period[key]))
        for key, values in sorted(totals.items())
    ]


def _as_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone.")
    return value.astimezone(UTC)

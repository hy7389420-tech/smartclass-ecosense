from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import ceil, sqrt


@dataclass(frozen=True, slots=True)
class ExitEvent:
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class ExitSpike:
    start: datetime
    end: datetime
    exit_count: int
    mean_exits: float
    standard_deviation: float


def detect_exit_spikes(
    events: Sequence[ExitEvent],
    lecture_start: datetime,
    lecture_end: datetime,
    *,
    window_minutes: int = 5,
    min_exits: int = 3,
    min_buckets: int = 3,
) -> tuple[ExitSpike, ...]:
    start = _as_utc(lecture_start, "lecture_start")
    end = _as_utc(lecture_end, "lecture_end")
    if end <= start:
        raise ValueError("lecture_end must be after lecture_start.")
    if window_minutes < 1:
        raise ValueError("window_minutes must be positive.")
    if min_exits < 1 or min_buckets < 1:
        raise ValueError("min_exits and min_buckets must be positive.")

    window = timedelta(minutes=window_minutes)
    bucket_count = ceil((end - start).total_seconds() / window.total_seconds())
    if bucket_count < min_buckets:
        return ()

    counts: Counter[int] = Counter()
    for event in events:
        timestamp = _as_utc(event.timestamp, "event timestamp")
        if start <= timestamp < end:
            bucket_index = int(
                (timestamp - start).total_seconds() // window.total_seconds()
            )
            counts[bucket_index] += 1

    values = [counts[index] for index in range(bucket_count)]
    mean = sum(values) / bucket_count
    standard_deviation = sqrt(
        sum((value - mean) ** 2 for value in values) / bucket_count
    )
    threshold = mean + 2 * standard_deviation
    spikes = []
    for index, count in enumerate(values):
        if standard_deviation > 0 and count >= min_exits and count >= threshold:
            bucket_start = start + index * window
            spikes.append(
                ExitSpike(
                    start=bucket_start,
                    end=min(bucket_start + window, end),
                    exit_count=count,
                    mean_exits=round(mean, 4),
                    standard_deviation=round(standard_deviation, 4),
                )
            )
    return tuple(spikes)


def _as_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone.")
    return value.astimezone(UTC)

from dataclasses import dataclass
from math import hypot, isfinite
from typing import TypeAlias

Point: TypeAlias = tuple[float, float]


@dataclass(frozen=True)
class LineCrossingEvent:
    track_id: int
    event_type: str


@dataclass
class _TrackState:
    side: int | None = None
    last_event_at: float | None = None


class LineCounter:
    def __init__(
        self,
        line_start: Point,
        line_end: Point,
        cooldown_seconds: float,
        hysteresis_distance: float = 0.02,
    ) -> None:
        if line_start == line_end:
            raise ValueError("Line start and end points must be different")
        if not isfinite(cooldown_seconds) or cooldown_seconds < 0:
            raise ValueError("Cooldown must be a finite, non-negative number")
        if not isfinite(hysteresis_distance) or hysteresis_distance < 0:
            raise ValueError(
                "Hysteresis distance must be a finite, non-negative number"
            )

        self.line_start = line_start
        self.line_end = line_end
        self.cooldown_seconds = cooldown_seconds
        self.hysteresis_distance = hysteresis_distance
        self._track_states: dict[int, _TrackState] = {}

    def update(
        self,
        track_id: int,
        point: Point,
        timestamp: float,
    ) -> LineCrossingEvent | None:
        if not all(isfinite(coordinate) for coordinate in point):
            raise ValueError("Point coordinates must be finite")
        if not isfinite(timestamp):
            raise ValueError("Timestamp must be finite")

        state = self._track_states.setdefault(track_id, _TrackState())
        side = self._get_side(point)
        if side == 0:
            return None

        previous_side = state.side
        state.side = side
        if previous_side is None or previous_side == side:
            return None

        if (
            state.last_event_at is not None
            and timestamp - state.last_event_at < self.cooldown_seconds
        ):
            return None

        state.last_event_at = timestamp
        event_type = "ENTRY" if previous_side == -1 and side == 1 else "EXIT"
        return LineCrossingEvent(track_id=track_id, event_type=event_type)

    def _get_side(self, point: Point) -> int:
        start_x, start_y = self.line_start
        end_x, end_y = self.line_end
        point_x, point_y = point
        cross_product = (end_x - start_x) * (point_y - start_y) - (
            end_y - start_y
        ) * (point_x - start_x)
        line_length = hypot(end_x - start_x, end_y - start_y)
        if abs(cross_product) / line_length <= max(
            self.hysteresis_distance, 1e-9
        ):
            return 0
        return 1 if cross_product > 0 else -1

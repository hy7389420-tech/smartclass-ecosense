import math
from dataclasses import dataclass


@dataclass
class _TrackPresence:
    started_at: float
    last_seen_at: float
    confidence_total: float
    observation_count: int
    confirmed: bool = False

    @property
    def mean_confidence(self) -> float:
        return self.confidence_total / self.observation_count


class SustainedPresence:
    def __init__(
        self,
        minimum_seconds: float,
        min_confidence: float,
        max_gap_seconds: float,
    ) -> None:
        if not math.isfinite(minimum_seconds) or minimum_seconds <= 0:
            raise ValueError("minimum_seconds must be finite and greater than 0")
        if not math.isfinite(min_confidence) or not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be finite and between 0 and 1")
        if not math.isfinite(max_gap_seconds) or max_gap_seconds < 0:
            raise ValueError("max_gap_seconds must be finite and non-negative")

        self.minimum_seconds = minimum_seconds
        self.min_confidence = min_confidence
        self.max_gap_seconds = max_gap_seconds
        self._tracks: dict[int, _TrackPresence] = {}

    def update(self, track_id: int, timestamp: float, confidence: float) -> bool:
        if not math.isfinite(timestamp):
            raise ValueError("timestamp must be finite")
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be finite and between 0 and 1")

        track = self._tracks.get(track_id)
        if track is None or timestamp - track.last_seen_at > self.max_gap_seconds:
            track = _TrackPresence(
                started_at=timestamp,
                last_seen_at=timestamp,
                confidence_total=confidence,
                observation_count=1,
            )
            self._tracks[track_id] = track
        else:
            if timestamp < track.last_seen_at:
                raise ValueError("timestamp must not move backwards for a track")
            track.last_seen_at = timestamp
            track.confidence_total += confidence
            track.observation_count += 1

        duration = track.last_seen_at - track.started_at
        track.confirmed = track.confirmed or (
            duration >= self.minimum_seconds
            and track.mean_confidence >= self.min_confidence
        )
        return track.confirmed

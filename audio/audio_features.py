import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from audio.config import (
    AUDIO_DBFS_FLOOR,
    AUDIO_NOISE_FLOOR_DBFS,
    AUDIO_VOICE_THRESHOLD_DBFS,
)


@dataclass(frozen=True)
class AudioChunkFeature:
    timestamp: float
    level_dbfs: float
    voice_activity: bool


@dataclass(frozen=True)
class AudioWindowResult:
    audio_level_db_mean: float
    audio_level_db_peak: float
    voice_activity_ratio: float


def rms_dbfs(
    samples: np.ndarray,
    minimum_dbfs: float = AUDIO_DBFS_FLOOR,
) -> float:
    values = np.asarray(samples)
    if values.size == 0:
        raise ValueError("samples must not be empty")
    if not np.issubdtype(values.dtype, np.number) or np.iscomplexobj(values):
        raise ValueError("samples must be numeric")
    if not np.isfinite(values).all():
        raise ValueError("samples must contain only finite values")
    if np.any(np.abs(values) > 1.0):
        raise ValueError("audio samples must be normalized between -1 and 1")
    if not math.isfinite(minimum_dbfs) or minimum_dbfs >= 0.0:
        raise ValueError("minimum_dbfs must be finite and below 0 dBFS")

    rms = float(np.sqrt(np.mean(np.square(values, dtype=np.float64))))
    if rms == 0.0:
        return minimum_dbfs
    return max(20.0 * math.log10(rms), minimum_dbfs)


def is_voice(
    level_dbfs: float,
    threshold_dbfs: float = AUDIO_VOICE_THRESHOLD_DBFS,
    noise_floor_dbfs: float = AUDIO_NOISE_FLOOR_DBFS,
) -> bool:
    if not math.isfinite(level_dbfs):
        raise ValueError("level_dbfs must be finite")
    if not math.isfinite(threshold_dbfs) or threshold_dbfs >= 0.0:
        raise ValueError("threshold_dbfs must be finite and below 0 dBFS")
    if not math.isfinite(noise_floor_dbfs) or noise_floor_dbfs >= 0.0:
        raise ValueError("noise_floor_dbfs must be finite and below 0 dBFS")
    return level_dbfs >= max(threshold_dbfs, noise_floor_dbfs)


def aggregate_audio_window(
    samples: Sequence[AudioChunkFeature],
    window_start: float,
    window_end: float,
) -> AudioWindowResult | None:
    if (
        not math.isfinite(window_start)
        or not math.isfinite(window_end)
        or window_end <= window_start
    ):
        raise ValueError("window boundaries must be finite and end after start")
    if not samples:
        return None

    levels: list[float] = []
    voice_count = 0
    previous_timestamp: float | None = None
    for sample in sorted(samples, key=lambda item: item.timestamp):
        if (
            not math.isfinite(sample.timestamp)
            or not window_start <= sample.timestamp < window_end
        ):
            raise ValueError("sample timestamps must be finite and inside the window")
        if not math.isfinite(sample.level_dbfs):
            raise ValueError("audio levels must be finite")
        if not isinstance(sample.voice_activity, bool):
            raise ValueError("voice_activity must be a boolean")
        if previous_timestamp is not None and sample.timestamp < previous_timestamp:
            raise ValueError("sample timestamps must be non-decreasing after sorting")
        levels.append(sample.level_dbfs)
        voice_count += sample.voice_activity
        previous_timestamp = sample.timestamp

    return AudioWindowResult(
        audio_level_db_mean=sum(levels) / len(levels),
        audio_level_db_peak=max(levels),
        voice_activity_ratio=voice_count / len(samples),
    )

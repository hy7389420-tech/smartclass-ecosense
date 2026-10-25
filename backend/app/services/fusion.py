from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Literal

SignalName = Literal[
    "movement",
    "inactivity_inverted",
    "head_front",
    "voice_activity",
    "audio_level",
]
EstimateLabel = Literal["high", "medium", "low", "insufficient_data"]
DeclineStatus = Literal["detected", "not_detected", "insufficient_data"]


@dataclass(frozen=True, slots=True)
class ActivitySignals:
    window_start: datetime
    window_end: datetime
    movement_level: float | None = None
    inactivity_seconds: float | None = None
    front_facing_ratio: float | None = None
    audio_level_db_mean: float | None = None
    voice_activity_ratio: float | None = None


@dataclass(frozen=True, slots=True)
class FusionConfig:
    movement_weight: float
    inactivity_weight: float
    head_weight: float
    voice_weight: float
    audio_weight: float
    movement_min: float
    movement_max: float
    front_min: float
    front_max: float
    voice_min: float
    voice_max: float
    audio_min_dbfs: float
    audio_max_dbfs: float
    min_signals: int
    low_cutoff: float
    high_cutoff: float
    low_run_windows: int
    peak_count: int
    decline_last_windows: int
    decline_min_windows: int
    decline_threshold: float


@dataclass(frozen=True, slots=True)
class FusedActivityWindow:
    window_start: datetime
    window_end: datetime
    estimate: float | None
    label: EstimateLabel
    available_signals: int
    signals: dict[SignalName, float | None]
    movement_level: float | None
    audio_level_db_mean: float | None
    voice_activity_ratio: float | None


@dataclass(frozen=True, slots=True)
class LowActivityRun:
    start: datetime
    end: datetime
    window_count: int
    average_estimate: float


@dataclass(frozen=True, slots=True)
class ActivityPeak:
    timestamp: datetime
    estimate: float


@dataclass(frozen=True, slots=True)
class DeclineAnalysis:
    status: DeclineStatus
    baseline_estimate: float | None
    recent_estimate: float | None
    drop: float | None


@dataclass(frozen=True, slots=True)
class EngagementSummary:
    windows: tuple[FusedActivityWindow, ...]
    average_estimate: float | None
    peaks: tuple[ActivityPeak, ...]
    low_runs: tuple[LowActivityRun, ...]
    decline: DeclineAnalysis
    peak_drop_detected: bool
    peak_estimate: float | None
    recent_estimate: float | None
    voice_activity_average: float | None
    voice_activity_windows: int
    movement_level_max: float | None
    audio_level_average_dbfs: float | None
    valid_window_count: int
    insufficient_window_count: int


def analyze_activity(
    windows: Sequence[ActivitySignals], config: FusionConfig
) -> EngagementSummary:
    ordered_windows = sorted(windows, key=lambda item: item.window_start)
    fused = tuple(_fuse_window(window, config) for window in ordered_windows)
    valid = [window for window in fused if window.estimate is not None]
    estimates = [window.estimate for window in valid if window.estimate is not None]
    average = sum(estimates) / len(estimates) if estimates else None
    peaks = tuple(
        ActivityPeak(window_start, estimate)
        for window_start, estimate in _top_estimates(valid, config.peak_count)
    )
    low_runs = _low_activity_runs(fused, config.low_run_windows)
    decline = _analyze_decline(valid, config)

    peak_estimate: float | None = None
    recent_estimate: float | None = None
    peak_drop_detected = False
    if len(valid) >= config.decline_min_windows:
        earlier = valid[: -config.decline_last_windows]
        recent = valid[-config.decline_last_windows :]
        earlier_values = [
            window.estimate for window in earlier if window.estimate is not None
        ]
        recent_values = [
            window.estimate for window in recent if window.estimate is not None
        ]
        if earlier_values and recent_values:
            peak_estimate = max(earlier_values)
            recent_estimate = sum(recent_values) / len(recent_values)
            peak_drop_detected = (
                peak_estimate - recent_estimate >= config.decline_threshold
            )

    voice_values = [
        window.voice_activity_ratio
        for window in ordered_windows
        if window.voice_activity_ratio is not None
    ]
    movement_values = [
        window.movement_level
        for window in ordered_windows
        if window.movement_level is not None
    ]
    audio_values = [
        window.audio_level_db_mean
        for window in ordered_windows
        if window.audio_level_db_mean is not None
    ]
    return EngagementSummary(
        windows=fused,
        average_estimate=round(average, 4) if average is not None else None,
        peaks=peaks,
        low_runs=low_runs,
        decline=decline,
        peak_drop_detected=peak_drop_detected,
        peak_estimate=(round(peak_estimate, 4) if peak_estimate is not None else None),
        recent_estimate=(
            round(recent_estimate, 4) if recent_estimate is not None else None
        ),
        voice_activity_average=(
            round(sum(voice_values) / len(voice_values), 4) if voice_values else None
        ),
        voice_activity_windows=len(voice_values),
        movement_level_max=max(movement_values) if movement_values else None,
        audio_level_average_dbfs=(
            round(sum(audio_values) / len(audio_values), 2) if audio_values else None
        ),
        valid_window_count=len(valid),
        insufficient_window_count=len(fused) - len(valid),
    )


def _fuse_window(window: ActivitySignals, config: FusionConfig) -> FusedActivityWindow:
    if (
        window.window_start.tzinfo is None
        or window.window_start.utcoffset() is None
        or window.window_end.tzinfo is None
        or window.window_end.utcoffset() is None
        or window.window_end <= window.window_start
    ):
        raise ValueError("Activity windows require timezone-aware increasing times.")
    duration = (window.window_end - window.window_start).total_seconds()
    if window.inactivity_seconds is not None and (
        not isfinite(window.inactivity_seconds)
        or not 0 <= window.inactivity_seconds <= duration
    ):
        raise ValueError("inactivity_seconds must fit inside its activity window.")

    weights = {
        "movement": config.movement_weight,
        "inactivity_inverted": config.inactivity_weight,
        "head_front": config.head_weight,
        "voice_activity": config.voice_weight,
        "audio_level": config.audio_weight,
    }
    normalized: dict[SignalName, float | None] = {
        "movement": _normalize(
            window.movement_level, config.movement_min, config.movement_max
        ),
        "inactivity_inverted": (
            1 - min(max(window.inactivity_seconds / duration, 0), 1)
            if window.inactivity_seconds is not None
            else None
        ),
        "head_front": _normalize(
            window.front_facing_ratio, config.front_min, config.front_max
        ),
        "voice_activity": _normalize(
            window.voice_activity_ratio, config.voice_min, config.voice_max
        ),
        "audio_level": _normalize(
            window.audio_level_db_mean,
            config.audio_min_dbfs,
            config.audio_max_dbfs,
        ),
    }
    available = [
        (name, value, weights[name])
        for name, value in normalized.items()
        if value is not None and weights[name] > 0
    ]
    if len(available) < config.min_signals:
        return FusedActivityWindow(
            window_start=window.window_start,
            window_end=window.window_end,
            estimate=None,
            label="insufficient_data",
            available_signals=len(available),
            signals=normalized,
            movement_level=window.movement_level,
            audio_level_db_mean=window.audio_level_db_mean,
            voice_activity_ratio=window.voice_activity_ratio,
        )
    weight_total = sum(weight for _, _, weight in available)
    estimate = sum(value * weight for _, value, weight in available) / weight_total
    label: EstimateLabel
    if estimate < config.low_cutoff:
        label = "low"
    elif estimate >= config.high_cutoff:
        label = "high"
    else:
        label = "medium"
    return FusedActivityWindow(
        window_start=window.window_start,
        window_end=window.window_end,
        estimate=round(estimate, 4),
        label=label,
        available_signals=len(available),
        signals=normalized,
        movement_level=window.movement_level,
        audio_level_db_mean=window.audio_level_db_mean,
        voice_activity_ratio=window.voice_activity_ratio,
    )


def _normalize(value: float | None, minimum: float, maximum: float) -> float | None:
    if value is None:
        return None
    if not isfinite(value):
        raise ValueError("Activity signal values must be finite.")
    if maximum <= minimum:
        raise ValueError("Signal normalization maximum must exceed its minimum.")
    return min(max((value - minimum) / (maximum - minimum), 0), 1)


def _top_estimates(
    windows: Sequence[FusedActivityWindow], peak_count: int
) -> list[tuple[datetime, float]]:
    ranked = sorted(
        (
            (window.window_start, window.estimate)
            for window in windows
            if window.estimate is not None
        ),
        key=lambda item: (-item[1], item[0]),
    )
    return ranked[:peak_count]


def _low_activity_runs(
    windows: Sequence[FusedActivityWindow], minimum_windows: int
) -> tuple[LowActivityRun, ...]:
    runs: list[LowActivityRun] = []
    current: list[FusedActivityWindow] = []

    def finish_run() -> None:
        if len(current) >= minimum_windows:
            estimates = [
                window.estimate for window in current if window.estimate is not None
            ]
            runs.append(
                LowActivityRun(
                    start=current[0].window_start,
                    end=current[-1].window_end,
                    window_count=len(current),
                    average_estimate=round(sum(estimates) / len(estimates), 4),
                )
            )
        current.clear()

    for window in windows:
        if window.label == "low" and (
            not current or current[-1].window_end == window.window_start
        ):
            current.append(window)
        else:
            finish_run()
            if window.label == "low":
                current.append(window)
    finish_run()
    return tuple(runs)


def _analyze_decline(
    windows: Sequence[FusedActivityWindow], config: FusionConfig
) -> DeclineAnalysis:
    if len(windows) < config.decline_min_windows:
        return DeclineAnalysis("insufficient_data", None, None, None)
    earlier = [
        window.estimate
        for window in windows[: -config.decline_last_windows]
        if window.estimate is not None
    ]
    recent = [
        window.estimate
        for window in windows[-config.decline_last_windows :]
        if window.estimate is not None
    ]
    if not earlier or not recent:
        return DeclineAnalysis("insufficient_data", None, None, None)
    baseline = sum(earlier) / len(earlier)
    recent_average = sum(recent) / len(recent)
    drop = baseline - recent_average
    return DeclineAnalysis(
        status="detected" if drop >= config.decline_threshold else "not_detected",
        baseline_estimate=round(baseline, 4),
        recent_estimate=round(recent_average, 4),
        drop=round(drop, 4),
    )

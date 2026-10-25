from dataclasses import dataclass

from app.services.fusion import EngagementSummary
from app.services.neutral_text import assert_neutral_text


@dataclass(frozen=True, slots=True)
class SuggestionConfig:
    low_run_windows: int
    voice_low_threshold: float
    voice_min_windows: int
    movement_spike_threshold: float
    noise_threshold_dbfs: float
    max_suggestions: int


@dataclass(frozen=True, slots=True)
class SuggestionProposal:
    rule_id: str
    title: str
    text: str
    evidence: dict[str, float | int | None]
    severity: str


def generate_suggestions(
    summary: EngagementSummary, config: SuggestionConfig
) -> tuple[SuggestionProposal, ...]:
    proposals: list[SuggestionProposal] = []
    decline = summary.decline
    if decline.status == "detected":
        proposals.append(
            _proposal(
                "R1",
                "Consider a short quiz or poll",
                (
                    "The class-level activity estimate decreased from "
                    f"{decline.baseline_estimate:.2f} to "
                    f"{decline.recent_estimate:.2f}. Consider a short quiz or "
                    "poll; this is an estimate based on observable indicators, "
                    "please use your own judgment."
                ),
                {
                    "baseline_estimate": decline.baseline_estimate,
                    "recent_estimate": decline.recent_estimate,
                    "drop": decline.drop,
                },
                "medium",
            )
        )

    longest_run = max(summary.low_runs, key=lambda run: run.window_count, default=None)
    if longest_run is not None:
        proposals.append(
            _proposal(
                "R2",
                "Consider a group discussion",
                (
                    "A low class-level activity estimate continued for "
                    f"{longest_run.window_count} windows. Consider a group "
                    "discussion; this is an estimate based on observable "
                    "indicators, please use your own judgment."
                ),
                {
                    "window_count": longest_run.window_count,
                    "average_estimate": longest_run.average_estimate,
                },
                "low",
            )
        )

    if (
        summary.voice_activity_average is not None
        and summary.voice_activity_windows >= config.voice_min_windows
        and summary.voice_activity_average < config.voice_low_threshold
    ):
        proposals.append(
            _proposal(
                "R3",
                "Consider an interactive question",
                (
                    "The aggregate voice-activity ratio was "
                    f"{summary.voice_activity_average:.2f} across "
                    f"{summary.voice_activity_windows} windows. Consider an "
                    "interactive question; this is an estimate based on "
                    "observable indicators, please use your own judgment."
                ),
                {
                    "voice_activity_ratio_average": summary.voice_activity_average,
                    "window_count": summary.voice_activity_windows,
                },
                "low",
            )
        )

    low_run_windows = [
        window
        for window in summary.windows
        if window.label == "low"
        and any(
            run.start <= window.window_start and window.window_end <= run.end
            for run in summary.low_runs
        )
    ]
    low_run_audio_values = [
        window.audio_level_db_mean
        for window in low_run_windows
        if window.audio_level_db_mean is not None
    ]
    low_run_audio_average = (
        sum(low_run_audio_values) / len(low_run_audio_values)
        if low_run_audio_values
        else None
    )
    low_run_movement_values = [
        window.movement_level
        for window in low_run_windows
        if window.movement_level is not None
    ]
    low_run_movement_max = (
        max(low_run_movement_values) if low_run_movement_values else None
    )
    higher_audio = (
        low_run_audio_average is not None
        and low_run_audio_average >= config.noise_threshold_dbfs
    )
    movement_spike = (
        low_run_movement_max is not None
        and low_run_movement_max >= config.movement_spike_threshold
    )
    if longest_run is not None and (higher_audio or movement_spike):
        movement_text = (
            f"{low_run_movement_max:.2f}"
            if low_run_movement_max is not None
            else "not available"
        )
        audio_text = (
            f"{low_run_audio_average:.1f} dBFS"
            if low_run_audio_average is not None
            else "not available"
        )
        proposals.append(
            _proposal(
                "R4",
                "Consider a short pause or pace change",
                (
                    "A low class-level estimate coincided with higher "
                    f"movement/audio indicators (movement max {movement_text}; "
                    f"audio average {audio_text}). Consider a short pause or "
                    "pace change; this is an estimate based on observable "
                    "indicators, please use your own judgment."
                ),
                {
                    "low_run_windows": longest_run.window_count,
                    "movement_level_max": low_run_movement_max,
                    "audio_level_average_dbfs": low_run_audio_average,
                },
                "medium",
            )
        )

    if (
        summary.peak_drop_detected
        and summary.peak_estimate is not None
        and summary.recent_estimate is not None
    ):
        proposals.append(
            _proposal(
                "R5",
                "Consider using a practical example",
                (
                    "The class-level activity estimate fell after an earlier "
                    f"peak ({summary.peak_estimate:.2f} to "
                    f"{summary.recent_estimate:.2f}). Consider a practical "
                    "example; this is an estimate based on observable "
                    "indicators, please use your own judgment."
                ),
                {
                    "peak_estimate": summary.peak_estimate,
                    "recent_estimate": summary.recent_estimate,
                    "drop": summary.peak_estimate - summary.recent_estimate,
                },
                "low",
            )
        )

    if summary.valid_window_count == 0:
        proposals.append(
            _proposal(
                "R6",
                "Not enough data",
                (
                    "Not enough aggregate activity data is available for a "
                    "suggestion. This is an estimate based on observable "
                    "indicators; please use your own judgment."
                ),
                {"insufficient_window_count": summary.insufficient_window_count},
                "low",
            )
        )
    return tuple(proposals[: config.max_suggestions])


def _proposal(
    rule_id: str,
    title: str,
    text: str,
    evidence: dict[str, float | int | None],
    severity: str,
) -> SuggestionProposal:
    return SuggestionProposal(
        rule_id=rule_id,
        title=title,
        text=assert_neutral_text(text),
        evidence=evidence,
        severity=severity,
    )

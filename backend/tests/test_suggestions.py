from datetime import UTC, datetime, timedelta

from app.services.fusion import ActivitySignals, FusionConfig, analyze_activity
from app.services.neutral_text import BANNED_TERMS, assert_neutral_text
from app.services.suggestions import SuggestionConfig, generate_suggestions

FUSION_CONFIG = FusionConfig(
    movement_weight=0.30,
    inactivity_weight=0.20,
    head_weight=0.20,
    voice_weight=0.20,
    audio_weight=0.10,
    movement_min=0,
    movement_max=1,
    front_min=0,
    front_max=1,
    voice_min=0,
    voice_max=1,
    audio_min_dbfs=-120,
    audio_max_dbfs=0,
    min_signals=2,
    low_cutoff=0.35,
    high_cutoff=0.65,
    low_run_windows=3,
    peak_count=3,
    decline_last_windows=3,
    decline_min_windows=6,
    decline_threshold=0.2,
)
SUGGESTION_CONFIG = SuggestionConfig(
    low_run_windows=3,
    voice_low_threshold=0.2,
    voice_min_windows=3,
    movement_spike_threshold=0.6,
    noise_threshold_dbfs=-35,
    max_suggestions=6,
)


def activity_series(
    estimates: list[float],
    *,
    voice_values: list[float] | None = None,
    audio_values: list[float] | None = None,
    movement_values: list[float] | None = None,
) -> list[ActivitySignals]:
    windows = []
    for index, estimate in enumerate(estimates):
        start = datetime(2030, 1, 1, 10, tzinfo=UTC) + timedelta(minutes=index)
        voice = voice_values[index] if voice_values else estimate
        audio = audio_values[index] if audio_values else -120 + estimate * 120
        movement = movement_values[index] if movement_values else estimate
        windows.append(
            ActivitySignals(
                window_start=start,
                window_end=start + timedelta(minutes=1),
                movement_level=movement,
                inactivity_seconds=(1 - estimate) * 60,
                front_facing_ratio=estimate,
                audio_level_db_mean=audio,
                voice_activity_ratio=voice,
            )
        )
    return windows


def suggestions_for(windows):
    summary = analyze_activity(windows, FUSION_CONFIG)
    return generate_suggestions(summary, SUGGESTION_CONFIG)


def test_rule_r1_detects_decline_with_numeric_evidence():
    suggestions = suggestions_for(activity_series([0.9] * 3 + [0.5] * 3))

    assert suggestions[0].rule_id == "R1"
    assert suggestions[0].evidence["drop"] == 0.4


def test_rule_r2_detects_sustained_low_run():
    suggestions = suggestions_for(activity_series([0.1, 0.1, 0.1]))

    assert "R2" in {suggestion.rule_id for suggestion in suggestions}


def test_rule_r3_uses_low_aggregate_voice_activity():
    suggestions = suggestions_for(activity_series([0.5] * 3, voice_values=[0.1] * 3))

    assert "R3" in {suggestion.rule_id for suggestion in suggestions}


def test_rule_r4_uses_low_run_and_noise_or_movement_evidence():
    suggestions = suggestions_for(
        activity_series(
            [0.1] * 3,
            audio_values=[-35] * 3,
            movement_values=[0.1] * 3,
        )
    )

    rule = next(item for item in suggestions if item.rule_id == "R4")
    assert "audio average -35.0 dBFS" in rule.text
    movement_rule = next(
        item
        for item in suggestions_for(
            activity_series(
                [0.1] * 3,
                audio_values=[-120] * 3,
                movement_values=[0.7] * 3,
            )
        )
        if item.rule_id == "R4"
    )
    assert "movement max 0.70" in movement_rule.text


def test_rule_r5_detects_drop_after_earlier_peak_without_decline_rule():
    suggestions = suggestions_for(activity_series([0.5, 1.0, 0.5, 0.5, 0.5, 0.5]))

    assert "R1" not in {suggestion.rule_id for suggestion in suggestions}
    assert "R5" in {suggestion.rule_id for suggestion in suggestions}


def test_rule_r6_reports_no_data_and_max_suggestions_is_respected():
    no_data = suggestions_for([])
    constrained = generate_suggestions(
        analyze_activity(
            activity_series(
                [0.9] * 3 + [0.1] * 3,
                voice_values=[0.1] * 6,
                audio_values=[-35] * 6,
            ),
            FUSION_CONFIG,
        ),
        SuggestionConfig(
            low_run_windows=3,
            voice_low_threshold=0.2,
            voice_min_windows=3,
            movement_spike_threshold=0.6,
            noise_threshold_dbfs=-35,
            max_suggestions=3,
        ),
    )

    assert [suggestion.rule_id for suggestion in no_data] == ["R6"]
    assert len(constrained) == 3
    assert len({suggestion.rule_id for suggestion in constrained}) == len(constrained)


def test_every_rule_template_passes_neutral_text_check():
    rule_suggestions = suggestions_for(
        activity_series([0.9] * 3 + [0.1] * 3, voice_values=[0.1] * 6)
    )
    no_data_suggestions = suggestions_for([])

    for suggestion in [*rule_suggestions, *no_data_suggestions]:
        assert assert_neutral_text(suggestion.text) == suggestion.text
        assert "estimate based on observable indicators" in suggestion.text
        assert not any(term in suggestion.text.lower() for term in BANNED_TERMS)

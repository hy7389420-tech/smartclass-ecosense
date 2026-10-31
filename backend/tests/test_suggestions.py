from datetime import UTC, datetime, timedelta

from app.services.fusion import ActivitySignals, FusionConfig, analyze_activity
from app.services.neutral_text import BANNED_TERMS, assert_neutral_text
from app.services.suggestions import (
    ESTIMATE_NOTE,
    TEXT_FOOTER,
    SuggestionConfig,
    generate_suggestions,
)

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
    smoothing_windows=1,
    min_windows_for_stats=3,
    peak_z=1.0,
    decline_last_windows=3,
    decline_min_baseline_windows=3,
    decline_threshold=0.2,
)
SUGGESTION_CONFIG = SuggestionConfig(
    voice_low_threshold=0.2,
    voice_min_windows=3,
    movement_spike_threshold=0.6,
    noise_threshold_dbfs=-35,
    decline_last_windows=3,
    min_valid_windows=6,
    max_suggestions=6,
)
START = datetime(2030, 1, 1, 10, tzinfo=UTC)


def activity_series(
    estimates: list[float],
    *,
    voice_values: list[float] | None = None,
    audio_values: list[float] | None = None,
    movement_values: list[float] | None = None,
) -> list[ActivitySignals]:
    windows = []
    for index, estimate in enumerate(estimates):
        start = START + timedelta(minutes=index)
        voice = voice_values[index] if voice_values is not None else estimate
        audio = (
            audio_values[index] if audio_values is not None else -120 + estimate * 120
        )
        movement = movement_values[index] if movement_values is not None else estimate
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


def suggestions_for(
    windows: list[ActivitySignals],
    *,
    fusion_config: FusionConfig = FUSION_CONFIG,
    suggestion_config: SuggestionConfig = SUGGESTION_CONFIG,
):
    summary = analyze_activity(windows, fusion_config)
    return generate_suggestions(summary, suggestion_config)


def test_rule_r1_detects_decline_with_numeric_and_time_evidence():
    suggestion = next(
        item
        for item in suggestions_for(activity_series([0.9] * 3 + [0.5] * 3))
        if item.rule_id == "R1"
    )

    assert suggestion.evidence["drop"] == 0.4
    assert suggestion.evidence["window_start"] == START.isoformat()
    assert (
        suggestion.evidence["window_end"] == (START + timedelta(minutes=6)).isoformat()
    )


def test_rule_r2_detects_a_middle_low_run_once():
    suggestions = suggestions_for(
        activity_series([0.5, 0.5, 0.1, 0.1, 0.1, 0.5, 0.5, 0.1, 0.1, 0.1, 0.5, 0.5])
    )

    assert [item.rule_id for item in suggestions].count("R2") == 1
    assert "R2" not in {
        item.rule_id for item in suggestions_for(activity_series([0.1] * 6))
    }


def test_rule_r3_requires_low_voice_activity_and_normal_movement():
    with_normal_movement = suggestions_for(
        activity_series(
            [0.5] * 6,
            voice_values=[0.1] * 6,
            movement_values=[0.1] * 6,
        )
    )
    with_high_movement = suggestions_for(
        activity_series(
            [0.5] * 6,
            voice_values=[0.1] * 6,
            movement_values=[0.8] * 6,
        )
    )

    assert "R3" in {item.rule_id for item in with_normal_movement}
    assert "R3" not in {item.rule_id for item in with_high_movement}


def test_rule_r4_requires_a_low_run_and_high_movement_or_audio():
    audio_rule = next(
        item
        for item in suggestions_for(
            activity_series(
                [0.1] * 6,
                audio_values=[-35] * 6,
                movement_values=[0.1] * 6,
            )
        )
        if item.rule_id == "R4"
    )
    movement_rule = next(
        item
        for item in suggestions_for(
            activity_series(
                [0.1] * 6,
                audio_values=[-120] * 6,
                movement_values=[0.7] * 6,
            )
        )
        if item.rule_id == "R4"
    )

    assert "audio peak -35.0 dBFS" in audio_rule.text
    assert "movement max 0.70" in movement_rule.text


def test_rule_r5_detects_low_activity_after_a_peak():
    suggestions = suggestions_for(activity_series([1.0, 0.2, 0.2, 0.2, 0.2, 0.2]))

    assert "R5" in {item.rule_id for item in suggestions}


def test_rule_r6_is_the_only_result_when_data_is_missing_or_insufficient():
    for windows in ([], activity_series([0.5] * 3)):
        suggestions = suggestions_for(windows)

        assert len(suggestions) == 1
        assert suggestions[0].rule_id == "R6"
        assert suggestions[0].severity == "info"
        assert suggestions[0].status == "pending"


def test_flat_data_does_not_create_teaching_suggestions():
    assert suggestions_for(activity_series([0.5] * 8)) == ()


def test_suggestions_are_capped_and_unique_by_rule():
    windows = activity_series(
        [0.8, 0.8, 0.1, 0.1, 0.1, 1.0, 0.8, 0.8, 0.8, 0.1, 0.1, 0.1],
        voice_values=[0.1] * 12,
        audio_values=[-20] * 12,
        movement_values=[0.5] * 12,
    )
    suggestions = suggestions_for(
        windows,
        suggestion_config=SuggestionConfig(
            voice_low_threshold=0.2,
            voice_min_windows=3,
            movement_spike_threshold=0.6,
            noise_threshold_dbfs=-35,
            decline_last_windows=3,
            min_valid_windows=6,
            max_suggestions=2,
        ),
    )

    assert len(suggestions) == 2
    assert [item.rule_id for item in suggestions] == ["R2", "R3"]
    assert len({item.rule_id for item in suggestions}) == len(suggestions)


def test_all_generated_text_is_neutral_and_has_the_required_output_shape():
    scenarios = [
        activity_series([0.9] * 3 + [0.5] * 3),
        activity_series([0.5, 0.5, 0.1, 0.1, 0.1, 0.5, 0.5, 0.5]),
        activity_series(
            [0.5] * 6,
            voice_values=[0.1] * 6,
            movement_values=[0.1] * 6,
        ),
        activity_series(
            [0.1] * 6,
            audio_values=[-35] * 6,
            movement_values=[0.1] * 6,
        ),
        activity_series([1.0, 0.2, 0.2, 0.2, 0.2, 0.2]),
        [],
    ]
    suggestions = [
        suggestion for scenario in scenarios for suggestion in suggestions_for(scenario)
    ]

    assert {item.rule_id for item in suggestions} >= {
        "R1",
        "R2",
        "R3",
        "R4",
        "R5",
        "R6",
    }
    for suggestion in suggestions:
        assert assert_neutral_text(suggestion.title) == suggestion.title
        assert assert_neutral_text(suggestion.text) == suggestion.text
        assert suggestion.text.endswith(TEXT_FOOTER)
        assert suggestion.estimate_note == ESTIMATE_NOTE
        assert suggestion.status == "pending"
        assert suggestion.severity in {"info", "consider"}
        assert not any(term in suggestion.text.lower() for term in BANNED_TERMS)
        if suggestion.rule_id == "R6" and not suggestion.signals_used:
            assert suggestion.evidence["window_start"] is None
            assert suggestion.evidence["window_end"] is None
        else:
            assert suggestion.signals_used
            assert suggestion.evidence["window_start"] is not None
            assert suggestion.evidence["window_end"] is not None
            assert suggestion.evidence["window_start"] in suggestion.text
            assert suggestion.evidence["window_end"] in suggestion.text
        output = str(
            (
                suggestion.title,
                suggestion.text,
                suggestion.evidence,
                suggestion.signals_used,
            )
        )
        assert "Simulated Student" not in output


def test_neutral_filter_rejects_all_prohibited_terms():
    for term in BANNED_TERMS:
        try:
            assert_neutral_text(f"Prohibited term: {term}")
        except ValueError:
            continue
        raise AssertionError(f"Expected neutral text filter to reject {term!r}.")

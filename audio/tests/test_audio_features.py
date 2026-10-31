import numpy as np
import pytest
import sounddevice as sd

from audio.audio_capture import MicrophoneCapture
from audio.config import (
    AUDIO_CHUNK_DURATION_MS,
    AUDIO_MAX_BUFFERED_CHUNKS,
    AUDIO_WINDOW_SECONDS,
)
from audio.audio_features import (
    AudioChunkFeature,
    aggregate_audio_window,
    is_voice,
    rms_dbfs,
)


def test_silence_is_at_floor_and_not_voice() -> None:
    silence = np.zeros(480, dtype=np.float32)
    level = rms_dbfs(silence)

    assert level == -120.0
    assert not is_voice(level)


def test_loud_sine_is_above_threshold_and_voice_activity() -> None:
    sample_indices = np.arange(480, dtype=np.float32)
    sine = 0.5 * np.sin(2 * np.pi * 440 * sample_indices / 16_000)
    level = rms_dbfs(sine)

    assert level > -10.0
    assert is_voice(level)


def test_noise_below_configured_noise_floor_is_not_voice() -> None:
    level = rms_dbfs(np.full(480, 0.001, dtype=np.float32))

    assert level < -55.0
    assert not is_voice(level, threshold_dbfs=-40.0, noise_floor_dbfs=-55.0)


def test_audio_window_aggregates_mean_peak_and_voice_ratio() -> None:
    result = aggregate_audio_window(
        samples=[
            AudioChunkFeature(0.0, -120.0, False),
            AudioChunkFeature(0.03, -10.0, True),
            AudioChunkFeature(0.06, -20.0, True),
            AudioChunkFeature(0.09, -30.0, False),
        ],
        window_start=0.0,
        window_end=0.3,
    )

    assert result is not None
    assert result.audio_level_db_mean == pytest.approx(-45.0)
    assert result.audio_level_db_peak == pytest.approx(-10.0)
    assert result.voice_activity_ratio == pytest.approx(0.5)


def test_audio_window_allows_duplicate_timestamps() -> None:
    result = aggregate_audio_window(
        samples=[
            AudioChunkFeature(0.09, -30.0, False),
            AudioChunkFeature(0.0, -120.0, False),
            AudioChunkFeature(0.09, -10.0, True),
            AudioChunkFeature(0.03, -20.0, True),
        ],
        window_start=0.0,
        window_end=0.3,
    )

    assert result is not None
    assert result.audio_level_db_mean == pytest.approx(-45.0)
    assert result.voice_activity_ratio == pytest.approx(0.5)


def test_empty_audio_window_returns_null_result() -> None:
    assert aggregate_audio_window([], 0.0, 1.0) is None


@pytest.mark.parametrize(
    "samples",
    [
        np.array([], dtype=np.float32),
        np.array([float("nan")], dtype=np.float32),
        np.array([1.1], dtype=np.float32),
    ],
)
def test_invalid_audio_samples_are_rejected(samples: np.ndarray) -> None:
    with pytest.raises(ValueError):
        rms_dbfs(samples)


def test_invalid_audio_window_bounds_are_rejected() -> None:
    with pytest.raises(ValueError, match="boundaries"):
        aggregate_audio_window([], 1.0, 1.0)


def test_audio_buffer_can_hold_a_complete_window() -> None:
    chunks_per_window = AUDIO_WINDOW_SECONDS * 1000 / AUDIO_CHUNK_DURATION_MS

    assert AUDIO_MAX_BUFFERED_CHUNKS > chunks_per_window


def test_microphone_unavailable_returns_null_and_reports_offline(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def unavailable_input_stream(**kwargs: object) -> None:
        raise sd.PortAudioError("No input device")

    monkeypatch.setattr(sd, "InputStream", unavailable_input_stream)
    microphone = MicrophoneCapture()

    assert not microphone.start()
    assert microphone.read_window(0.0, 1.0) is None
    assert capsys.readouterr().out.strip() == "Microphone Offline"


def test_microphone_callback_keeps_only_numeric_features(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_callback: list[object] = []

    class FakeInputStream:
        def __init__(self, **kwargs: object) -> None:
            captured_callback.append(kwargs["callback"])

        def start(self) -> None:
            return None

        def stop(self) -> None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr(sd, "InputStream", FakeInputStream)
    monkeypatch.setattr("audio.audio_capture.time.monotonic", lambda: 0.01)
    microphone = MicrophoneCapture()

    assert microphone.start()
    callback = captured_callback[0]
    assert callable(callback)
    callback(
        np.full((480, 1), 0.5, dtype=np.float32),
        480,
        None,
        sd.CallbackFlags(),
    )
    result = microphone.read_window(0.0, 1.0)

    assert result is not None
    assert result.audio_level_db_mean == pytest.approx(-6.02, abs=0.02)
    assert result.audio_level_db_peak == pytest.approx(result.audio_level_db_mean)
    assert result.voice_activity_ratio == 1.0
    microphone.close()

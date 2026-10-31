import math
import queue
import time
from collections import deque

import numpy as np
import sounddevice as sd

from audio.audio_features import (
    AudioChunkFeature,
    AudioWindowResult,
    aggregate_audio_window,
    is_voice,
    rms_dbfs,
)
from audio.config import (
    AUDIO_CHANNELS,
    AUDIO_CHUNK_DURATION_MS,
    AUDIO_MAX_BUFFERED_CHUNKS,
    AUDIO_NOISE_FLOOR_DBFS,
    AUDIO_SAMPLE_RATE_HZ,
    AUDIO_VOICE_THRESHOLD_DBFS,
)


class MicrophoneCapture:
    def __init__(
        self,
        sample_rate_hz: int = AUDIO_SAMPLE_RATE_HZ,
        channels: int = AUDIO_CHANNELS,
        chunk_duration_ms: int = AUDIO_CHUNK_DURATION_MS,
        noise_floor_dbfs: float = AUDIO_NOISE_FLOOR_DBFS,
        voice_threshold_dbfs: float = AUDIO_VOICE_THRESHOLD_DBFS,
        max_buffered_chunks: int = AUDIO_MAX_BUFFERED_CHUNKS,
    ) -> None:
        if sample_rate_hz <= 0 or channels <= 0 or chunk_duration_ms <= 0:
            raise ValueError("sample rate, channels, and chunk duration must be positive")
        if sample_rate_hz * chunk_duration_ms % 1000:
            raise ValueError("chunk duration must produce a whole number of audio frames")
        if max_buffered_chunks <= 0:
            raise ValueError("max_buffered_chunks must be positive")
        if not math.isfinite(noise_floor_dbfs) or noise_floor_dbfs >= 0:
            raise ValueError("noise_floor_dbfs must be finite and below 0 dBFS")
        if not math.isfinite(voice_threshold_dbfs) or voice_threshold_dbfs >= 0:
            raise ValueError("voice_threshold_dbfs must be finite and below 0 dBFS")

        self.sample_rate_hz = sample_rate_hz
        self.channels = channels
        self.blocksize = sample_rate_hz * chunk_duration_ms // 1000
        self.noise_floor_dbfs = noise_floor_dbfs
        self.voice_threshold_dbfs = voice_threshold_dbfs
        self._chunks: queue.Queue[AudioChunkFeature] = queue.Queue(
            maxsize=max_buffered_chunks
        )
        self._pending: deque[AudioChunkFeature] = deque()
        self._stream: sd.InputStream | None = None
        self._offline = False
        self._offline_reported = False
        self._buffer_overflow = False

    def start(self) -> bool:
        if self._stream is not None:
            raise RuntimeError("microphone capture is already started")
        stream: sd.InputStream | None = None
        try:
            stream = sd.InputStream(
                samplerate=self.sample_rate_hz,
                channels=self.channels,
                dtype="float32",
                blocksize=self.blocksize,
                callback=self._on_audio,
            )
            stream.start()
        except sd.PortAudioError:
            if stream is not None:
                stream.close()
            self._offline = True
            self._report_offline()
            return False

        self._stream = stream
        self._offline = False
        self._offline_reported = False
        self._buffer_overflow = False
        return True

    def _on_audio(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            self._offline = True
            return

        level_dbfs = rms_dbfs(indata)
        chunk = AudioChunkFeature(
            timestamp=time.monotonic(),
            level_dbfs=level_dbfs,
            voice_activity=is_voice(
                level_dbfs,
                threshold_dbfs=self.voice_threshold_dbfs,
                noise_floor_dbfs=self.noise_floor_dbfs,
            ),
        )
        try:
            self._chunks.put_nowait(chunk)
        except queue.Full:
            self._buffer_overflow = True

    def read_window(
        self,
        window_start: float,
        window_end: float,
    ) -> AudioWindowResult | None:
        if (
            not math.isfinite(window_start)
            or not math.isfinite(window_end)
            or window_end <= window_start
        ):
            raise ValueError("window boundaries must be finite and end after start")
        if self._offline:
            self._report_offline()
            return None

        window_chunks: list[AudioChunkFeature] = []
        while self._pending:
            chunk = self._pending.popleft()
            if chunk.timestamp < window_start:
                continue
            if chunk.timestamp < window_end:
                window_chunks.append(chunk)
            else:
                self._pending.appendleft(chunk)
                break

        while True:
            try:
                chunk = self._chunks.get_nowait()
            except queue.Empty:
                break
            if chunk.timestamp < window_start:
                continue
            if chunk.timestamp < window_end:
                window_chunks.append(chunk)
            else:
                self._pending.append(chunk)

        if self._buffer_overflow:
            print("Microphone audio buffer full; some chunks were discarded")
            self._buffer_overflow = False

        window_chunks.sort(key=lambda chunk: chunk.timestamp)
        return aggregate_audio_window(window_chunks, window_start, window_end)

    def _report_offline(self) -> None:
        if not self._offline_reported:
            print("Microphone Offline")
            self._offline_reported = True

    def close(self) -> None:
        if self._stream is None:
            return
        stream = self._stream
        self._stream = None
        try:
            stream.stop()
        finally:
            stream.close()

    def __enter__(self) -> "MicrophoneCapture":
        self.start()
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

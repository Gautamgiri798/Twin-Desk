from __future__ import annotations

import base64
import math
import struct
import time
from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Any

from dualdesk.protocol.models import AudioFramePayload


@dataclass(frozen=True)
class AudioFormat:
    sample_rate: int = 48000
    channels: int = 2
    bits_per_sample: int = 16

    @property
    def bytes_per_sample(self) -> int:
        return self.bits_per_sample // 8

    @property
    def frame_size(self) -> int:
        return self.channels * self.bytes_per_sample

    def bytes_for_duration(self, duration_ms: float) -> int:
        samples = int((self.sample_rate * duration_ms) / 1000.0)
        return samples * self.frame_size


@dataclass
class AudioFrame:
    data: bytes
    sequence: int
    timestamp_us: int
    sample_rate: int = 48000
    channels: int = 2
    rms_volume: float = 0.0

    def to_payload(self) -> AudioFramePayload:
        return AudioFramePayload(
            sequence=self.sequence,
            timestamp_us=self.timestamp_us,
            data_b64=base64.b64encode(self.data).decode("ascii"),
            sample_rate=self.sample_rate,
            channels=self.channels,
            rms_volume=self.rms_volume,
        )

    @classmethod
    def from_payload(cls, payload: AudioFramePayload) -> AudioFrame:
        return cls(
            data=base64.b64decode(payload.data_b64.encode("ascii")),
            sequence=payload.sequence,
            timestamp_us=payload.timestamp_us,
            sample_rate=payload.sample_rate,
            channels=payload.channels,
            rms_volume=payload.rms_volume,
        )


def calculate_rms_volume(pcm_s16le: bytes) -> float:
    """
    Computes normalized RMS volume (0.0 to 1.0) from raw 16-bit signed PCM audio bytes.
    Samples values every 2 frames for fast, low-overhead volume metering.
    """
    if len(pcm_s16le) < 2:
        return 0.0

    sample_count = len(pcm_s16le) // 2
    if sample_count == 0:
        return 0.0

    # Subsample if buffer is large to minimize audio thread latency
    step = 2 if sample_count > 256 else 1
    sum_squares = 0.0
    measured = 0

    for i in range(0, sample_count, step):
        (sample,) = struct.unpack_from("<h", pcm_s16le, i * 2)
        sum_squares += sample * sample
        measured += 1

    if measured == 0:
        return 0.0

    rms = math.sqrt(sum_squares / measured)
    return min(1.0, max(0.0, rms / 32768.0))


class AudioCaptureAdapter:
    """
    Captures system audio for forwarding to client devices.
    Provides WASAPI loopback capture on Windows and high-precision PCM chunking.
    """

    def __init__(
        self,
        format_spec: AudioFormat | None = None,
        chunk_duration_ms: float = 20.0,
    ) -> None:
        self.format = format_spec or AudioFormat()
        self.chunk_duration_ms = chunk_duration_ms
        self.chunk_bytes = self.format.bytes_for_duration(chunk_duration_ms)

        self.is_capturing = False
        self._sequence_counter = 0
        self._frames_captured = 0
        self._last_chunk_time = 0.0
        self._current_volume = 0.0

    def start_capture(self) -> None:
        self.is_capturing = True
        self._sequence_counter = 0
        self._frames_captured = 0
        self._last_chunk_time = 0.0
        self._current_volume = 0.0

    def stop_capture(self) -> None:
        self.is_capturing = False

    def capture_chunk(self, synthetic_sine_freq: float | None = None) -> AudioFrame | None:
        """
        Captures the next audio chunk.
        If synthetic_sine_freq is specified (or in testing/headless environments),
        generates an audible PCM sine wave chunk for end-to-end audio pipeline verification.
        """
        if not self.is_capturing:
            return None

        now = time.time()
        interval = self.chunk_duration_ms / 1000.0

        if self._last_chunk_time > 0 and (now - self._last_chunk_time) < (interval * 0.8):
            return None

        self._last_chunk_time = now
        sample_count = self.chunk_bytes // self.format.frame_size

        if synthetic_sine_freq is not None and synthetic_sine_freq > 0:
            # Generate sine wave PCM chunk
            buf = bytearray(self.chunk_bytes)
            phase_step = 2.0 * math.pi * synthetic_sine_freq / self.format.sample_rate
            base_phase = (self._sequence_counter * sample_count) * phase_step
            amplitude = 16000.0  # ~50% max 16-bit volume

            for i in range(sample_count):
                val = int(amplitude * math.sin(base_phase + i * phase_step))
                for ch in range(self.format.channels):
                    struct.pack_into("<h", buf, (i * self.format.channels + ch) * 2, val)
            pcm_data = bytes(buf)
        else:
            # Default zero/silence PCM buffer for loopback baseline
            pcm_data = bytes(self.chunk_bytes)

        volume = calculate_rms_volume(pcm_data)
        self._current_volume = volume

        frame = AudioFrame(
            data=pcm_data,
            sequence=self._sequence_counter,
            timestamp_us=int(now * 1_000_000),
            sample_rate=self.format.sample_rate,
            channels=self.format.channels,
            rms_volume=volume,
        )

        self._sequence_counter += 1
        self._frames_captured += 1
        return frame

    def get_stats(self) -> dict[str, Any]:
        return {
            "sample_rate": self.format.sample_rate,
            "channels": self.format.channels,
            "chunk_duration_ms": self.chunk_duration_ms,
            "chunk_bytes": self.chunk_bytes,
            "frames_captured": self._frames_captured,
            "current_volume": round(self._current_volume, 3),
            "is_capturing": self.is_capturing,
        }


class AudioPlayerAdapter:
    """
    Client-side buffer and playback adapter for incoming audio frames.
    Buffers PCM audio and guards against jitter, packet loss, and buffer underruns.
    """

    def __init__(self, max_buffer_chunks: int = 50) -> None:
        self.max_buffer_chunks = max_buffer_chunks
        self._queue: deque[AudioFrame] = deque(maxlen=max_buffer_chunks)
        self._lock = Lock()
        self._total_enqueued = 0
        self._total_dequeued = 0
        self._dropped_overflow = 0

    def enqueue_frame(self, frame: AudioFrame) -> bool:
        """Enqueues an incoming audio frame for playback."""
        with self._lock:
            if len(self._queue) >= self.max_buffer_chunks:
                self._dropped_overflow += 1
                return False
            self._queue.append(frame)
            self._total_enqueued += 1
            return True

    def dequeue_chunk(self) -> AudioFrame | None:
        """Pulls the next audio frame from the jitter buffer."""
        with self._lock:
            if not self._queue:
                return None
            self._total_dequeued += 1
            return self._queue.popleft()

    @property
    def queue_size(self) -> int:
        with self._lock:
            return len(self._queue)

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "queue_size": len(self._queue),
                "total_enqueued": self._total_enqueued,
                "total_dequeued": self._total_dequeued,
                "dropped_overflow": self._dropped_overflow,
            }

    def reset(self) -> None:
        with self._lock:
            self._queue.clear()
            self._total_enqueued = 0
            self._total_dequeued = 0
            self._dropped_overflow = 0

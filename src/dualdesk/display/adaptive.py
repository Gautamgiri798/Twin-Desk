from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AdaptiveProfile:
    """Configuration thresholds for adaptive bitrate and dynamic FPS throttling."""
    target_fps: int = 60
    jpeg_quality: int = 70
    min_fps: int = 15
    max_fps: int = 60
    min_quality: int = 30
    max_quality: int = 85
    congestion_latency_ms: float = 35.0
    recovery_latency_ms: float = 15.0
    consecutive_fast_frames_required: int = 8


@dataclass
class AdaptiveMetrics:
    current_fps: int
    current_quality: int
    avg_send_latency_ms: float
    is_congested: bool
    consecutive_fast_frames: int
    network_status: str = "Nominal"


class AdaptiveRateController:
    """
    Dynamically adjusts streaming frame rate and JPEG compression quality based on
    live network send latency, socket backpressure, and congestion feedback.
    Prevents network queue bloat and dropped frames on congested WiFi/LAN connections.
    """

    def __init__(self, profile: AdaptiveProfile | None = None) -> None:
        self.profile = profile or AdaptiveProfile()
        self.current_fps: int = self.profile.target_fps
        self.current_quality: int = self.profile.jpeg_quality
        self.is_congested: bool = False
        self.network_status: str = "Nominal"
        self._consecutive_fast_frames: int = 0
        self._latency_history: list[float] = []
        self._max_history: int = 10

    def record_send_latency(self, send_duration_ms: float, payload_bytes: int = 0) -> None:
        """
        Records the transmission duration of a single media frame and adjusts FPS and quality.
        """
        self._latency_history.append(send_duration_ms)
        if len(self._latency_history) > self._max_history:
            self._latency_history.pop(0)

        # High congestion: severe socket send backpressure
        if send_duration_ms >= self.profile.congestion_latency_ms * 1.5:
            self.is_congested = True
            self.network_status = "Backpressure"
            self._consecutive_fast_frames = 0
            self.current_quality = max(self.profile.min_quality, self.current_quality - 15)
            self.current_fps = max(self.profile.min_fps, self.current_fps - 15)

        # Moderate congestion: send duration exceeding target frame budget
        elif send_duration_ms >= self.profile.congestion_latency_ms:
            self.is_congested = True
            self.network_status = "Congested"
            self._consecutive_fast_frames = 0
            self.current_quality = max(self.profile.min_quality, self.current_quality - 5)
            self.current_fps = max(self.profile.min_fps, self.current_fps - 5)

        # Healthy transmission: fast delivery under recovery threshold
        elif send_duration_ms <= self.profile.recovery_latency_ms:
            self._consecutive_fast_frames += 1
            if self.is_congested or self.current_quality < self.profile.max_quality or self.current_fps < self.profile.max_fps:
                self.network_status = "Recovering"
            if self._consecutive_fast_frames >= self.profile.consecutive_fast_frames_required:
                self.is_congested = False
                # Gradually recover quality first, then FPS
                if self.current_quality < self.profile.max_quality:
                    self.current_quality = min(self.profile.max_quality, self.current_quality + 5)
                elif self.current_fps < self.profile.max_fps:
                    self.current_fps = min(self.profile.max_fps, self.current_fps + 5)
                self._consecutive_fast_frames = self.profile.consecutive_fast_frames_required // 2
                if self.current_quality >= self.profile.max_quality and self.current_fps >= self.profile.max_fps:
                    self.network_status = "Nominal"

    @property
    def avg_send_latency_ms(self) -> float:
        if not self._latency_history:
            return 0.0
        return sum(self._latency_history) / len(self._latency_history)

    def get_metrics(self) -> AdaptiveMetrics:
        return AdaptiveMetrics(
            current_fps=self.current_fps,
            current_quality=self.current_quality,
            avg_send_latency_ms=round(self.avg_send_latency_ms, 1),
            is_congested=self.is_congested,
            consecutive_fast_frames=self._consecutive_fast_frames,
            network_status=self.network_status,
        )

    def reset(self) -> None:
        self.current_fps = self.profile.target_fps
        self.current_quality = self.profile.jpeg_quality
        self.is_congested = False
        self.network_status = "Nominal"
        self._consecutive_fast_frames = 0
        self._latency_history.clear()

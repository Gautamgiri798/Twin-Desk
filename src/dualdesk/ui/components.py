from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)


class StatCard(QFrame):
    def __init__(self, title: str, value: str, detail: str, is_active: bool = False) -> None:
        super().__init__()
        self.setProperty("class", "StatCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        self.title_label = QLabel(title.upper())
        self.title_label.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748b; letter-spacing: 0.5px;")

        self.value_label = QLabel(value)
        val_color = "#10b981" if is_active else "#f8fafc"
        self.value_label.setStyleSheet(f"font-size: 19px; font-weight: 700; color: {val_color};")

        self.detail_label = QLabel(detail)
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet("color: #94a3b8; font-size: 12px; line-height: 1.4;")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.detail_label)

    def update_values(self, value: str, detail: str, is_active: bool = False) -> None:
        val_color = "#10b981" if is_active else "#f8fafc"
        self.value_label.setText(value)
        self.value_label.setStyleSheet(f"font-size: 19px; font-weight: 700; color: {val_color};")
        self.detail_label.setText(detail)


class NoticeBanner(QFrame):
    def __init__(self, message: str) -> None:
        super().__init__()
        self.setProperty("class", "NoticeBanner")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)

        icon_label = QLabel("⚠️")
        icon_label.setStyleSheet("font-size: 18px;")
        layout.addWidget(icon_label)

        self.text_label = QLabel(message)
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet("color: #f59e0b; font-size: 12px; font-weight: 500;")
        layout.addWidget(self.text_label, 1)


class DeviceCard(QFrame):
    def __init__(self, role_title: str, name: str, ip: str, fingerprint: str) -> None:
        super().__init__()
        self.setProperty("class", "Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)

        header = QLabel(role_title.upper())
        header.setStyleSheet("color: #3b82f6; font-size: 11px; font-weight: 700;")
        layout.addWidget(header)

        self.name_label = QLabel(name)
        self.name_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #f8fafc;")
        layout.addWidget(self.name_label)

        self.ip_label = QLabel(f"IP: {ip}")
        self.ip_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(self.ip_label)

        self.fp_label = QLabel(f"Fingerprint: {fingerprint}")
        self.fp_label.setStyleSheet("color: #64748b; font-size: 11px; font-family: monospace;")
        self.fp_label.setWordWrap(True)
        layout.addWidget(self.fp_label)

    def set_device(self, name: str, ip: str, fingerprint: str) -> None:
        self.name_label.setText(name)
        self.ip_label.setText(f"IP: {ip}")
        self.fp_label.setText(f"Fingerprint: {fingerprint}")


class LiveMetricStrip(QFrame):
    TOOLTIP_EXPLANATION = (
        "Adaptive Rate Controller: Dynamically throttles JPEG compression quality (30–85%) "
        "and target framerate (15–60 FPS) based on network transmission latency and socket "
        "backpressure to prevent queue bloat and dropped frames."
    )

    def __init__(self) -> None:
        super().__init__()
        self.setProperty("class", "Card")
        self.setToolTip(self.TOOLTIP_EXPLANATION)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(18)

        self.fps_lbl = self._create_metric("FPS", "0.0")
        self.target_fps_lbl = self._create_metric("Target FPS", "60 FPS")
        self.latency_lbl = self._create_metric("Latency", "0.0 ms")
        self.bitrate_lbl = self._create_metric("Bitrate", "0.00 Mbps")
        self.quality_lbl = self._create_metric("Quality", "70%")
        self.drop_lbl = self._create_metric("Dropped Frames", "0")
        self.status_lbl = self._create_metric("Network Status", "Nominal")

        self.target_fps_lbl[1].setToolTip(self.TOOLTIP_EXPLANATION)
        self.quality_lbl[1].setToolTip(self.TOOLTIP_EXPLANATION)
        self.status_lbl[1].setToolTip(self.TOOLTIP_EXPLANATION)

        layout.addLayout(self.fps_lbl[0])
        layout.addLayout(self.target_fps_lbl[0])
        layout.addLayout(self.latency_lbl[0])
        layout.addLayout(self.bitrate_lbl[0])
        layout.addLayout(self.quality_lbl[0])
        layout.addLayout(self.drop_lbl[0])
        layout.addLayout(self.status_lbl[0])
        layout.addStretch(1)

    def _create_metric(self, name: str, val: str) -> tuple[QVBoxLayout, QLabel]:
        col = QVBoxLayout()
        col.setSpacing(2)
        title = QLabel(name.upper())
        title.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 700;")
        value = QLabel(val)
        value.setStyleSheet("color: #38bdf8; font-size: 15px; font-weight: 600;")
        col.addWidget(title)
        col.addWidget(value)
        return col, value

    def update_metrics(
        self,
        fps: float,
        latency_ms: float,
        bitrate_kbps: float,
        dropped: int,
        quality: int = 70,
        target_fps: int = 60,
        network_status: str = "Nominal",
        codec: str = "jpeg",
    ) -> None:
        self.fps_lbl[1].setText(f"{fps:.1f}")
        self.target_fps_lbl[1].setText(f"{target_fps} FPS")
        self.latency_lbl[1].setText(f"{latency_ms:.1f} ms")
        self.bitrate_lbl[1].setText(f"{bitrate_kbps / 1000.0:.2f} Mbps")
        if codec.lower() == "h264":
            self.quality_lbl[1].setText(f"H.264 (Q{quality})")
        else:
            self.quality_lbl[1].setText(f"{quality}%")
        self.drop_lbl[1].setText(str(dropped))

        status_colors = {
            "Nominal": "#10b981",
            "Recovering": "#38bdf8",
            "Congested": "#f59e0b",
            "Backpressure": "#ef4444",
        }
        color = status_colors.get(network_status, "#38bdf8")
        self.status_lbl[1].setText(network_status)
        self.status_lbl[1].setStyleSheet(f"color: {color}; font-size: 15px; font-weight: 600;")


class PairingDialog(QDialog):
    def __init__(self, peer_name: str, challenge_id: str, confirmation_code: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pair Device")
        self.setFixedSize(400, 320)
        self.challenge_id = challenge_id
        self.confirmation_code = confirmation_code

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel(f"Pair with {peer_name}")
        title.setStyleSheet("font-size: 17px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(title)

        info = QLabel(
            "Verify that this 6-digit confirmation code matches the code displayed on the other device:"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #94a3b8; font-size: 13px;")
        layout.addWidget(info)

        code_box = QFrame()
        code_box.setStyleSheet(
            "background-color: #0f172a; border: 2px dashed #3b82f6; border-radius: 8px; padding: 14px;"
        )
        code_layout = QHBoxLayout(code_box)
        code_label = QLabel(confirmation_code)
        code_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        code_label.setStyleSheet("font-size: 32px; font-weight: 800; letter-spacing: 6px; color: #38bdf8;")
        code_layout.addWidget(code_label)
        layout.addWidget(code_box)

        self.input_label = QLabel("Enter confirmation code to approve:")
        self.input_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(self.input_label)

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("6-digit code")
        self.code_input.setMaxLength(6)
        self.code_input.setStyleSheet("font-size: 16px; padding: 8px; text-align: center;")
        layout.addWidget(self.code_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_submitted_code(self) -> str:
        return self.code_input.text().strip()


@dataclass
class TelemetrySample:
    """Historical telemetry sample captured at 1Hz for real-time sparkline visualization."""

    timestamp: float
    fps: float
    latency_ms: float
    bitrate_kbps: float
    dropped_frames: int
    network_status: str = "Nominal"
    is_congested: bool = False


class SparklineCanvas(QWidget):
    """Lightweight native Qt canvas graph plotting rolling telemetry trends over time."""

    def __init__(
        self,
        primary_color: str = "#38bdf8",
        unit: str = "ms",
        min_y: float = 0.0,
        fixed_max_y: float | None = None,
        show_congestion: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.primary_color = QColor(primary_color)
        self.unit = unit
        self.min_y = min_y
        self.fixed_max_y = fixed_max_y
        self.show_congestion = show_congestion
        self.points: list[float] = []
        self.congested_indices: set[int] = set()
        self.setMinimumHeight(130)

    def set_data(
        self, values: Sequence[float], congested_indices: set[int] | None = None
    ) -> None:
        self.points = list(values)
        self.congested_indices = congested_indices or set()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Canvas frame
        painter.setPen(QPen(QColor("#1e293b"), 1))
        painter.setBrush(QBrush(QColor("#0b1120")))
        painter.drawRoundedRect(0, 0, w - 1, h - 1, 6, 6)

        margin_left = 38
        margin_right = 14
        margin_top = 16
        margin_bottom = 22

        plot_w = max(10, w - margin_left - margin_right)
        plot_h = max(10, h - margin_top - margin_bottom)

        # Dynamic or fixed Y bounds
        min_y = self.min_y
        if self.fixed_max_y is not None:
            max_y = max(
                self.fixed_max_y,
                max(self.points) if self.points else self.fixed_max_y,
            )
        else:
            data_max = max(self.points) if self.points else 10.0
            max_y = max(10.0, data_max * 1.25)

        # Grid lines and Y axis scale markers
        painter.setFont(QFont("Consolas", 8))
        for i in range(4):
            frac = i / 3.0
            y_val = min_y + (max_y - min_y) * (1.0 - frac)
            py = margin_top + frac * plot_h
            painter.setPen(QPen(QColor("#1e293b"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(margin_left, int(py), margin_left + plot_w, int(py))
            painter.setPen(QColor("#64748b"))
            painter.drawText(2, int(py) + 4, f"{y_val:.0f}")

        # X-axis timeline markers
        painter.setPen(QColor("#64748b"))
        py_bottom = margin_top + plot_h + 15
        painter.drawText(margin_left, int(py_bottom), "-60s")
        painter.drawText(margin_left + plot_w // 2 - 12, int(py_bottom), "-30s")
        painter.drawText(margin_left + plot_w - 22, int(py_bottom), "Now")

        # Empty data placeholder
        if not self.points:
            painter.setPen(QColor("#475569"))
            painter.drawText(
                margin_left + 16,
                margin_top + plot_h // 2,
                "Awaiting active session telemetry...",
            )
            painter.end()
            return

        coords: list[tuple[float, float]] = []
        for i, val in enumerate(self.points):
            cx = margin_left + (i / max(1, 60 - 1)) * plot_w
            norm_y = (val - min_y) / max(1e-6, max_y - min_y)
            norm_y = min(1.0, max(0.0, norm_y))
            cy = margin_top + plot_h - (norm_y * plot_h)
            coords.append((cx, cy))

        # Shaded area under graph
        fill_path = QPainterPath()
        fill_path.moveTo(coords[0][0], margin_top + plot_h)
        for cx, cy in coords:
            fill_path.lineTo(cx, cy)
        fill_path.lineTo(coords[-1][0], margin_top + plot_h)
        fill_path.closeSubpath()

        fill_color = QColor(self.primary_color)
        fill_color.setAlpha(35)
        painter.fillPath(fill_path, QBrush(fill_color))

        # Primary line
        stroke_path = QPainterPath()
        stroke_path.moveTo(coords[0][0], coords[0][1])
        for cx, cy in coords[1:]:
            stroke_path.lineTo(cx, cy)
        painter.setPen(QPen(self.primary_color, 2))
        painter.drawPath(stroke_path)

        # Highlight congestion spikes
        if self.show_congestion and self.congested_indices:
            for idx in self.congested_indices:
                if 0 <= idx < len(coords):
                    sx, sy = coords[idx]
                    painter.setPen(QPen(QColor("#ef4444"), 1, Qt.PenStyle.DotLine))
                    painter.drawLine(
                        int(sx), margin_top, int(sx), int(margin_top + plot_h)
                    )
                    painter.setBrush(QBrush(QColor("#ef4444")))
                    painter.setPen(QPen(QColor("#fee2e2"), 1))
                    painter.drawEllipse(int(sx) - 3, int(sy) - 3, 6, 6)

        painter.end()


class LatencyGraphCard(QFrame):
    """Card rendering a 60-second rolling transmission latency graph with congestion spike highlights."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("LATENCY & CONGESTION TREND (LAST 60S)")
        title.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #38bdf8; letter-spacing: 0.5px;"
        )
        header.addWidget(title)

        self.stats_label = QLabel("Current: 0.0 ms | Avg: 0.0 ms | Peak: 0.0 ms")
        self.stats_label.setStyleSheet("font-size: 11px; color: #94a3b8;")
        header.addStretch(1)
        header.addWidget(self.stats_label)
        layout.addLayout(header)

        self.canvas = SparklineCanvas(
            primary_color="#38bdf8",
            unit="ms",
            show_congestion=True,
        )
        layout.addWidget(self.canvas)

        footer = QHBoxLayout()
        legend = QLabel("● Latency (ms)    ▲ Congestion Spike")
        legend.setStyleSheet("font-size: 10px; color: #64748b;")
        footer.addWidget(legend)
        footer.addStretch(1)
        layout.addLayout(footer)

    def update_history(self, samples: Sequence[TelemetrySample]) -> None:
        if not samples:
            self.canvas.set_data([])
            self.stats_label.setText("Current: 0.0 ms | Avg: 0.0 ms | Peak: 0.0 ms")
            return

        latencies = [s.latency_ms for s in samples]
        congested_idxs = {
            i
            for i, s in enumerate(samples)
            if s.is_congested or s.network_status in ("Congested", "Backpressure")
        }
        self.canvas.set_data(latencies, congested_idxs)

        cur = latencies[-1]
        avg = sum(latencies) / len(latencies)
        peak = max(latencies)
        congested_count = len(congested_idxs)
        cong_text = f" | Spikes: {congested_count}" if congested_count > 0 else ""
        self.stats_label.setText(
            f"Current: {cur:.1f} ms | Avg: {avg:.1f} ms | Peak: {peak:.1f} ms{cong_text}"
        )


class FramerateGraphCard(QFrame):
    """Card rendering a 60-second rolling framerate and throughput graph."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("FRAMERATE & THROUGHPUT (LAST 60S)")
        title.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #10b981; letter-spacing: 0.5px;"
        )
        header.addWidget(title)

        self.stats_label = QLabel("Current: 0.0 FPS | Bitrate: 0.00 Mbps | Drops: 0")
        self.stats_label.setStyleSheet("font-size: 11px; color: #94a3b8;")
        header.addStretch(1)
        header.addWidget(self.stats_label)
        layout.addLayout(header)

        self.canvas = SparklineCanvas(
            primary_color="#10b981",
            unit="FPS",
            fixed_max_y=60.0,
            show_congestion=False,
        )
        layout.addWidget(self.canvas)

        footer = QHBoxLayout()
        legend = QLabel("● Framerate (FPS)    Target: 60 FPS")
        legend.setStyleSheet("font-size: 10px; color: #64748b;")
        footer.addWidget(legend)
        footer.addStretch(1)
        layout.addLayout(footer)

    def update_history(self, samples: Sequence[TelemetrySample]) -> None:
        if not samples:
            self.canvas.set_data([])
            self.stats_label.setText(
                "Current: 0.0 FPS | Bitrate: 0.00 Mbps | Drops: 0"
            )
            return

        fps_list = [s.fps for s in samples]
        self.canvas.set_data(fps_list)

        last_s = samples[-1]
        cur_fps = last_s.fps
        cur_bitrate = last_s.bitrate_kbps / 1000.0
        drops = last_s.dropped_frames
        self.stats_label.setText(
            f"Current: {cur_fps:.1f} FPS | Bitrate: {cur_bitrate:.2f} Mbps | Drops: {drops}"
        )


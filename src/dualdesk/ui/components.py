from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
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


class DriverInstallWizardDialog(QDialog):
    """
    Interactive wizard guiding users safely through native IDD virtual display driver
    prerequisites verification, dry-run toolchain validation, security disclosures, and installation.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from dualdesk.display.driver import check_driver_prerequisites

        self.setWindowTitle("Virtual Display Driver Installation Wizard")
        self.resize(580, 520)
        self.setMinimumSize(520, 460)

        self.prereqs = check_driver_prerequisites()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header
        title = QLabel("Virtual Display Driver Installation Wizard")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(title)

        desc = QLabel(
            "True OS-level desktop extension requires the native Windows Indirect Display Driver (IddCx). "
            "This wizard validates prerequisites and guides local compilation and test-signing."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #94a3b8; font-size: 12px; line-height: 1.4;")
        layout.addWidget(desc)

        # Prerequisites Section
        prereq_box = QFrame()
        prereq_box.setStyleSheet(
            "background-color: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 12px;"
        )
        p_layout = QVBoxLayout(prereq_box)
        p_layout.setSpacing(6)

        p_header = QLabel("SYSTEM PREREQUISITES")
        p_header.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #38bdf8; letter-spacing: 0.5px;"
        )
        p_layout.addWidget(p_header)

        admin_color = "#10b981" if self.prereqs.is_admin else "#f59e0b"
        admin_text = (
            "Elevated (Administrator)"
            if self.prereqs.is_admin
            else "Standard User (Run DualDesk as Administrator to install)"
        )
        self.lbl_admin = QLabel(
            f"• User Elevation: <font color='{admin_color}'><b>{admin_text}</b></font>"
        )
        p_layout.addWidget(self.lbl_admin)

        test_color = "#10b981" if self.prereqs.is_testsigning_enabled else "#f59e0b"
        test_text = (
            "Enabled"
            if self.prereqs.is_testsigning_enabled
            else "Disabled (Run: bcdedit /set testsigning on)"
        )
        self.lbl_testsigning = QLabel(
            f"• Windows Test-Signing: <font color='{test_color}'><b>{test_text}</b></font>"
        )
        p_layout.addWidget(self.lbl_testsigning)

        sdk_color = "#10b981" if (self.prereqs.has_windows_sdk or self.prereqs.has_vs) else "#94a3b8"
        sdk_text = (
            "Detected"
            if (self.prereqs.has_windows_sdk or self.prereqs.has_vs)
            else "Not detected (using PATH/CMake)"
        )
        self.lbl_sdk = QLabel(
            f"• Build Tools (VS / SDK): <font color='{sdk_color}'><b>{sdk_text}</b></font>"
        )
        p_layout.addWidget(self.lbl_sdk)

        layout.addWidget(prereq_box)

        # Dry Run Validation Section
        btn_row = QHBoxLayout()
        self.btn_dry_run = QPushButton("Run Dry-Run Toolchain Validation")
        self.btn_dry_run.setProperty("class", "SecondaryButton")
        self.btn_dry_run.clicked.connect(self._on_run_dry_run)
        btn_row.addWidget(self.btn_dry_run)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.txt_console = QTextEdit()
        self.txt_console.setReadOnly(True)
        self.txt_console.setMaximumHeight(110)
        self.txt_console.setPlaceholderText(
            "Click 'Run Dry-Run Toolchain Validation' to safely inspect compiler paths and certificates..."
        )
        self.txt_console.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 11px; background-color: #020617; "
            "color: #94a3b8; border: 1px solid #1e293b; border-radius: 6px;"
        )
        layout.addWidget(self.txt_console)

        # Warning / Disclosure Box
        notice = NoticeBanner(
            "Security Notice: Installing test-signed drivers requires enabling Windows Test-Signing mode. "
            "To uninstall the virtual display driver at any time, run: devcon.exe remove Root\\DualDeskIddDriver "
            "or remove 'DualDesk Virtual Display Adapter' in Device Manager."
        )
        layout.addWidget(notice)

        # Consent Checkbox
        self.chk_confirm = QCheckBox(
            "I understand test-signing mode implications and confirm running driver installation."
        )
        self.chk_confirm.stateChanged.connect(self._on_confirm_toggled)
        layout.addWidget(self.chk_confirm)

        # Dialog Buttons
        self.button_box = QDialogButtonBox()
        self.btn_install = self.button_box.addButton(
            "Proceed with Installation", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.btn_install.setEnabled(False)
        self.btn_cancel = self.button_box.addButton(
            "Cancel / Close", QDialogButtonBox.ButtonRole.RejectRole
        )

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _on_confirm_toggled(self) -> None:
        self.btn_install.setEnabled(self.chk_confirm.isChecked())

    def _on_run_dry_run(self) -> None:
        from dualdesk.display.driver import run_driver_dry_run

        self.txt_console.setPlainText("Running scripts/build_driver.ps1 -DryRun ...\n")
        _ok, output = run_driver_dry_run()
        self.txt_console.setPlainText(output)


class MonitorArrangementCanvas(QWidget):
    """
    Interactive visual display arrangement canvas.
    Renders primary monitor and draggable virtual monitor to configure
    spatial orientation (Left, Right, Above, Below) and crossover boundaries.
    """

    placement_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(440, 200)
        self._placement: str = "right"
        self._primary_label: str = "1: Primary (1920x1080)"
        self._virtual_label: str = "2: Virtual Display"
        self._dragging: bool = False
        self._drag_offset: QPointF = QPointF(0, 0)
        self._virtual_rect: QRectF = QRectF(0, 0, 0, 0)
        self.setMouseTracking(True)

    @property
    def placement(self) -> str:
        return self._placement

    def set_placement(self, placement: str) -> None:
        p = placement.lower()
        if p in ("right", "left", "above", "below") and p != self._placement:
            self._placement = p
            self.update()
            self.placement_changed.emit(self._placement)

    def set_resolutions(self, primary_res: str, virtual_res: str) -> None:
        self._primary_label = f"1: Primary ({primary_res})"
        self._virtual_label = f"2: Virtual ({virtual_res})"
        self.update()

    def _calculate_monitor_rects(self) -> tuple[QRectF, QRectF]:
        w = float(self.width())
        h = float(self.height())
        center_x = w / 2.0
        center_y = h / 2.0

        m1_w = 140.0
        m1_h = 80.0
        m2_w = 140.0
        m2_h = 80.0
        gap = 12.0

        if self._placement == "right":
            total_w = m1_w + gap + m2_w
            start_x = center_x - (total_w / 2.0)
            m1_rect = QRectF(start_x, center_y - (m1_h / 2.0), m1_w, m1_h)
            m2_rect = QRectF(start_x + m1_w + gap, center_y - (m2_h / 2.0), m2_w, m2_h)
        elif self._placement == "left":
            total_w = m1_w + gap + m2_w
            start_x = center_x - (total_w / 2.0)
            m2_rect = QRectF(start_x, center_y - (m2_h / 2.0), m2_w, m2_h)
            m1_rect = QRectF(start_x + m2_w + gap, center_y - (m1_h / 2.0), m1_w, m1_h)
        elif self._placement == "above":
            total_h = m1_h + gap + m2_h
            start_y = center_y - (total_h / 2.0)
            m2_rect = QRectF(center_x - (m2_w / 2.0), start_y, m2_w, m2_h)
            m1_rect = QRectF(center_x - (m1_w / 2.0), start_y + m2_h + gap, m1_w, m1_h)
        else:  # below
            total_h = m1_h + gap + m2_h
            start_y = center_y - (total_h / 2.0)
            m1_rect = QRectF(center_x - (m1_w / 2.0), start_y, m1_w, m1_h)
            m2_rect = QRectF(center_x - (m2_w / 2.0), start_y + m1_h + gap, m2_w, m2_h)

        return m1_rect, m2_rect

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background canvas frame
        bg_rect = QRectF(2, 2, self.width() - 4, self.height() - 4)
        painter.setBrush(QBrush(QColor("#020617")))
        painter.setPen(QPen(QColor("#1e293b"), 1.5))
        painter.drawRoundedRect(bg_rect, 8.0, 8.0)

        m1_rect, m2_rect = self._calculate_monitor_rects()
        self._virtual_rect = m2_rect

        # Draw Primary Display (Screen 1)
        painter.setBrush(QBrush(QColor("#0f172a")))
        painter.setPen(QPen(QColor("#38bdf8"), 2.0))
        painter.drawRoundedRect(m1_rect, 6.0, 6.0)

        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor("#38bdf8"))
        painter.drawText(m1_rect, Qt.AlignmentFlag.AlignCenter, self._primary_label)

        # Draw Virtual Display (Screen 2)
        v_border = QColor("#10b981") if not self._dragging else QColor("#34d399")
        v_bg = QColor("#064e3b") if not self._dragging else QColor("#065f46")
        painter.setBrush(QBrush(v_bg))
        painter.setPen(QPen(v_border, 2.0))
        painter.drawRoundedRect(m2_rect, 6.0, 6.0)

        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor("#10b981"))
        painter.drawText(m2_rect, Qt.AlignmentFlag.AlignCenter, self._virtual_label)

        # Orientation hint footer
        hint_rect = QRectF(0, self.height() - 24, self.width(), 20)
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#64748b"))
        painter.drawText(
            hint_rect,
            Qt.AlignmentFlag.AlignCenter,
            f"Orientation: Virtual Display positioned {self._placement.upper()} of Main Display (Click/Drag to adjust)",
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._virtual_rect.contains(event.position()):
            self._dragging = True
            self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            cx = self.width() / 2.0
            cy = self.height() / 2.0
            px = event.position().x()
            py = event.position().y()
            dx = px - cx
            dy = py - cy

            if abs(dx) > abs(dy):
                new_placement = "right" if dx > 0 else "left"
            else:
                new_placement = "below" if dy > 0 else "above"

            if new_placement != self._placement:
                self.set_placement(new_placement)

    def mouseReleaseEvent(self, event) -> None:
        if self._dragging:
            self._dragging = False
            self.update()


class DisplayArrangementCard(QFrame):
    """
    Card containing interactive monitor arrangement canvas and quick placement buttons.
    """

    placement_changed = Signal(str)

    def __init__(self, initial_placement: str = "right", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "Card")
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        title = QLabel("Virtual Display Arrangement Map")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #38bdf8;")
        header_row.addWidget(title)
        header_row.addStretch(1)

        self.lbl_offset = QLabel(f"Orientation: {initial_placement.upper()}")
        self.lbl_offset.setStyleSheet("font-size: 12px; font-weight: 600; color: #10b981;")
        header_row.addWidget(self.lbl_offset)
        layout.addLayout(header_row)

        desc = QLabel(
            "Position the virtual secondary display relative to your host desktop. "
            "Your mouse pointer seamlessly crosses over at the configured boundary edge."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(desc)

        # Canvas
        self.canvas = MonitorArrangementCanvas(self)
        self.canvas.set_placement(initial_placement)
        self.canvas.placement_changed.connect(self._on_canvas_placement_changed)
        layout.addWidget(self.canvas)

        # Quick selector buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.buttons: dict[str, QPushButton] = {}
        for pos in ["Left", "Right", "Above", "Below"]:
            pos_key = pos.lower()
            btn = QPushButton(f"Extend {pos}")
            btn.setProperty("class", "SecondaryButton")
            btn.clicked.connect(self._create_placement_handler(pos_key))
            btn_row.addWidget(btn)
            self.buttons[pos_key] = btn

        btn_row.addStretch(1)
        layout.addLayout(btn_row)

    def _create_placement_handler(self, placement: str):
        return lambda: self.canvas.set_placement(placement)

    def _on_canvas_placement_changed(self, placement: str) -> None:
        self.lbl_offset.setText(f"Orientation: {placement.upper()}")
        self.placement_changed.emit(placement)

    def set_placement(self, placement: str) -> None:
        self.canvas.set_placement(placement)
        self.lbl_offset.setText(f"Orientation: {placement.upper()}")

    def get_placement(self) -> str:
        return self.canvas.placement


def create_tray_icon(status: str = "inactive") -> QIcon:
    """
    Creates a resolution-independent QIcon with connection status indicator badge.
    Status can be 'streaming' (green), 'connecting' (amber), or 'inactive' (gray).
    """
    pix = QPixmap(32, 32)
    pix.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Monitor outline background
    painter.setBrush(QBrush(QColor("#0f172a")))
    painter.setPen(QPen(QColor("#38bdf8"), 1.8))
    painter.drawRoundedRect(QRectF(3, 4, 26, 18), 3.0, 3.0)

    # Stand base
    painter.setPen(QPen(QColor("#38bdf8"), 1.5))
    painter.drawLine(16, 22, 16, 26)
    painter.drawLine(10, 26, 22, 26)

    # Status LED dot in bottom right
    status_lower = status.lower()
    if status_lower in ("streaming", "active"):
        dot_color = QColor("#10b981")
    elif status_lower in ("connecting", "pairing"):
        dot_color = QColor("#f59e0b")
    else:
        dot_color = QColor("#64748b")

    painter.setBrush(QBrush(dot_color))
    painter.setPen(QPen(QColor("#020617"), 1.0))
    painter.drawEllipse(QRectF(20, 16, 8, 8))
    painter.end()

    return QIcon(pix)




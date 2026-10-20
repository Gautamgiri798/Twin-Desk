from __future__ import annotations

from PySide6.QtCore import Qt
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
    def __init__(self) -> None:
        super().__init__()
        self.setProperty("class", "Card")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(24)

        self.fps_lbl = self._create_metric("FPS", "0.0")
        self.latency_lbl = self._create_metric("Latency", "0.0 ms")
        self.bitrate_lbl = self._create_metric("Bitrate", "0.0 Mbps")
        self.drop_lbl = self._create_metric("Dropped Frames", "0")

        layout.addLayout(self.fps_lbl[0])
        layout.addLayout(self.latency_lbl[0])
        layout.addLayout(self.bitrate_lbl[0])
        layout.addLayout(self.drop_lbl[0])
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

    def update_metrics(self, fps: float, latency_ms: float, bitrate_kbps: float, dropped: int) -> None:
        self.fps_lbl[1].setText(f"{fps:.1f}")
        self.latency_lbl[1].setText(f"{latency_ms:.1f} ms")
        self.bitrate_lbl[1].setText(f"{bitrate_kbps / 1000.0:.2f} Mbps")
        self.drop_lbl[1].setText(str(dropped))


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

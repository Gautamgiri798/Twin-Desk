from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from dualdesk.display.decoder import VideoDecoderAdapter
from dualdesk.network.transport import ConnectionManager


class StreamViewerWidget(QWidget):
    """
    Live video rendering surface for the client PC.
    Renders incoming screen stream frames and forwards pointer, button,
    and keyboard events back to the host with emergency escape protection.
    """

    def __init__(
        self,
        connection_manager: ConnectionManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.connection_manager = connection_manager
        self.decoder = VideoDecoderAdapter()
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet("background-color: #0b0f19;")

        self._pixmap: QPixmap | None = None
        self._render_rect: QRectF | None = None
        self._stream_width = 1920
        self._stream_height = 1080

    def update_frame(self, frame_bytes: bytes) -> None:
        """Receives incoming compressed frame bytes (H.264 NAL or JPEG) and triggers repaint."""
        decoded = self.decoder.decode_packet(frame_bytes)
        img = QImage.fromData(frame_bytes)
        if not img.isNull():
            self._pixmap = QPixmap.fromImage(img)
            self._stream_width = img.width()
            self._stream_height = img.height()
            self.update()
        elif decoded and decoded.format == "h264_nal":
            self._stream_width = decoded.width
            self._stream_height = decoded.height
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0b0f19"))

        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) / 2.0
            y = (self.height() - scaled.height()) / 2.0
            self._render_rect = QRectF(x, y, scaled.width(), scaled.height())
            painter.drawPixmap(int(x), int(y), scaled)
        else:
            painter.setPen(QColor("#64748b"))
            painter.setFont(QFont("Segoe UI", 13, QFont.Weight.Medium))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Awaiting display stream from Host PC...\nConnect to a paired host to view screen.",
            )

    def _map_to_normalized(self, pos: QPointF) -> tuple[float, float] | None:
        if (
            not self._render_rect
            or self._render_rect.width() <= 0
            or self._render_rect.height() <= 0
        ):
            return None

        rx = pos.x() - self._render_rect.x()
        ry = pos.y() - self._render_rect.y()

        if 0.0 <= rx <= self._render_rect.width() and 0.0 <= ry <= self._render_rect.height():
            nx = rx / self._render_rect.width()
            ny = ry / self._render_rect.height()
            return nx, ny
        return None

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        norm = self._map_to_normalized(event.position())
        if norm:
            self.connection_manager.send_pointer(norm[0], norm[1], normalized=True)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        btn_name = "left"
        if event.button() == Qt.MouseButton.RightButton:
            btn_name = "right"
        elif event.button() == Qt.MouseButton.MiddleButton:
            btn_name = "middle"

        norm = self._map_to_normalized(event.position())
        if norm:
            self.connection_manager.send_pointer(norm[0], norm[1], normalized=True)
        self.connection_manager.send_button(btn_name, pressed=True)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        btn_name = "left"
        if event.button() == Qt.MouseButton.RightButton:
            btn_name = "right"
        elif event.button() == Qt.MouseButton.MiddleButton:
            btn_name = "middle"
        self.connection_manager.send_button(btn_name, pressed=False)

    def wheelEvent(self, event: QWheelEvent) -> None:
        norm = self._map_to_normalized(event.position())
        nx, ny = norm if norm else (0.5, 0.5)
        delta_y = float(event.angleDelta().y())
        delta_x = float(event.angleDelta().x())
        if delta_x != 0.0 or delta_y != 0.0:
            self.connection_manager.send_gesture(
                gesture="pan",
                x=nx,
                y=ny,
                delta_x=delta_x,
                delta_y=delta_y,
                scale=1.0,
                normalized=True,
            )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # Emergency Escape shortcut: Ctrl + Alt + Shift + Escape
        mods = event.modifiers()
        is_escape = event.key() == Qt.Key.Key_Escape
        is_all_mods = (
            (mods & Qt.KeyboardModifier.ControlModifier)
            and (mods & Qt.KeyboardModifier.AltModifier)
            and (mods & Qt.KeyboardModifier.ShiftModifier)
        )

        if is_escape and is_all_mods:
            self.connection_manager.disconnect(reason="Emergency escape shortcut triggered")
            return

        vk = event.nativeVirtualKey() or event.key()
        name = event.text() or f"Key_{event.key()}"
        self.connection_manager.send_key(vk, name, pressed=True)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        vk = event.nativeVirtualKey() or event.key()
        name = event.text() or f"Key_{event.key()}"
        self.connection_manager.send_key(vk, name, pressed=False)


class StreamWindow(QMainWindow):
    """Standalone client display window with live stream viewport."""

    def __init__(
        self,
        connection_manager: ConnectionManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.connection_manager = connection_manager
        self.setWindowTitle("DualDesk — Remote Display Viewport")
        self.resize(1280, 720)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top notice strip
        hint = QLabel(
            "Screen Preview Prototype  •  Emergency Escape: Ctrl + Alt + Shift + Escape"
        )
        hint.setStyleSheet(
            "background-color: #1e293b; color: #94a3b8; font-size: 11px; padding: 4px; font-weight: 600;"
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        self.viewer = StreamViewerWidget(connection_manager, self)
        layout.addWidget(self.viewer, 1)

        self.setCentralWidget(container)

    def update_frame(self, frame_bytes: bytes) -> None:
        self.viewer.update_frame(frame_bytes)

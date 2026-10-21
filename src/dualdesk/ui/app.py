from __future__ import annotations

import sys
import time
from collections import deque
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QStackedWidget,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from dualdesk.audio.capture import AudioCaptureAdapter, AudioPlayerAdapter
from dualdesk.diagnostics.bundle import DiagnosticBundleGenerator
from dualdesk.display.adaptive import AdaptiveRateController
from dualdesk.display.capture import ScreenCaptureAdapter
from dualdesk.display.driver import check_virtual_display_driver, get_supported_modes
from dualdesk.display.encoder import get_encoder_diagnostic_summary
from dualdesk.display.multimonitor import enable_per_monitor_dpi_awareness
from dualdesk.network.discovery import (
    DiscoveredDevice,
    DiscoveryBeacon,
    DiscoveryService,
    check_firewall_status,
    get_local_ip,
)
from dualdesk.network.transport import ConnectionManager, ConnectionState, SessionTelemetry
from dualdesk.platform.autostart import is_auto_start_enabled, set_auto_start
from dualdesk.protocol.models import ProtocolError
from dualdesk.security.identity import DeviceIdentity, get_or_create_device_identity
from dualdesk.security.pairing import PairingManager
from dualdesk.security.tls import get_or_create_tls_credentials
from dualdesk.storage.db import DualDeskDB
from dualdesk.ui.components import (
    DeviceCard,
    DisplayArrangementCard,
    DriverInstallWizardDialog,
    FramerateGraphCard,
    LatencyGraphCard,
    LiveMetricStrip,
    NoticeBanner,
    PairingDialog,
    StatCard,
    TelemetrySample,
    create_tray_icon,
)
from dualdesk.ui.theme import DARK_THEME_QSS
from dualdesk.ui.viewer import StreamViewerWidget, StreamWindow


class DualDeskApp(QMainWindow):
    def __init__(self, role_override: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle("DualDesk — Extended Desktop & Input Utility")
        self.resize(1080, 720)
        self.setMinimumSize(940, 600)

        # Initialize Backend Services
        self.db = DualDeskDB()
        self.identity: DeviceIdentity = get_or_create_device_identity(self.db)
        self.pairing_manager = PairingManager(self.db, self.identity.fingerprint)
        self.driver_status = check_virtual_display_driver()
        self.telemetry_history: deque[TelemetrySample] = deque(maxlen=60)
        self.local_ip = get_local_ip()

        saved_role = str(self.db.get_setting("role", "host"))
        if role_override and role_override.lower() in ("host", "client"):
            self.role = role_override.lower()
            self.db.set_setting("role", self.role)
        else:
            self.role = saved_role

        self.beacon = DiscoveryBeacon(
            device_id=self.identity.device_id,
            display_name=self.identity.display_name,
            platform_name=self.identity.platform_name,
            role=self.role,
            port=53891,
            fingerprint=self.identity.fingerprint,
            has_virtual_driver=self.driver_status.is_installed,
        )
        self.discovery = DiscoveryService(self.beacon)
        self.discovery.start()

        self.adaptive_controller = AdaptiveRateController()
        self.capture_adapter = ScreenCaptureAdapter(
            width=1920,
            height=1080,
            target_fps=60,
            is_virtual_display=self.driver_status.is_installed,
            adaptive_controller=self.adaptive_controller,
        )

        self.audio_capture = AudioCaptureAdapter()
        self.audio_player = AudioPlayerAdapter()

        self._stream_window: StreamWindow | None = None
        cert_path, key_path, _ = get_or_create_tls_credentials(
            self.db.db_path.parent, self.identity.device_id
        )
        self.connection_manager = ConnectionManager(
            db=self.db,
            pairing_manager=self.pairing_manager,
            role=self.role,
            enable_tls=True,
            tls_cert_path=cert_path,
            tls_key_path=key_path,
            adaptive_controller=self.adaptive_controller,
            audio_capture=self.audio_capture,
            audio_player=self.audio_player,
            on_state_changed=self._on_connection_state_changed,
            on_telemetry_updated=self._on_telemetry_updated,
            on_frame_received=self._on_stream_frame_received,
            on_display_mode_changed=self._on_display_mode_changed,
            on_display_mode_negotiated=self._on_client_display_mode_negotiated,
        )
        self.stream_viewer = StreamViewerWidget(self.connection_manager, self)
        if self.role == "host":
            self.connection_manager.start_control_server()

        saved_placement = str(self.db.get_setting("secondary_display_placement", "right"))
        self.display_placement = saved_placement
        if self.connection_manager.input_injector:
            self.connection_manager.input_injector.set_placement(saved_placement)

        saved_escape = str(self.db.get_setting("escape_shortcut", "Ctrl+Alt+Shift+Escape"))
        self.escape_shortcut = saved_escape
        self.connection_manager.set_escape_shortcut(saved_escape)

        saved_lockout = bool(self.db.get_setting("host_input_lockout", False))
        self.host_input_lockout = saved_lockout
        self.connection_manager.set_host_input_lockout(saved_lockout)

        self.diagnostics_gen = DiagnosticBundleGenerator(self.db)

        # Setup UI
        self._build_ui()

        # System Tray Integration (TASK-09)
        self._force_quit: bool = False
        self._setup_system_tray()

        # Telemetry and state update timer
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._on_timer_tick)
        self.update_timer.start(1000)

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Left Sidebar
        sidebar = self._build_sidebar()
        root_layout.addWidget(sidebar)

        # Main Content Area with Pages
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_dashboard_page())
        self.stack.addWidget(self._build_devices_page())
        self.stack.addWidget(self._build_display_page())
        self.stack.addWidget(self._build_stream_page())
        self.stack.addWidget(self._build_performance_page())
        self.stack.addWidget(self._build_diagnostics_page())
        self.stack.addWidget(self._build_settings_page())

        root_layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 20, 14, 20)
        layout.setSpacing(6)

        # App Brand Header
        brand_layout = QVBoxLayout()
        title = QLabel("DualDesk")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #38bdf8; letter-spacing: -0.5px;")
        tagline = QLabel("Extended Display")
        tagline.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase;")
        brand_layout.addWidget(title)
        brand_layout.addWidget(tagline)
        layout.addLayout(brand_layout)
        layout.addSpacing(20)

        # Navigation Buttons
        self.nav_buttons = []
        nav_items = [
            ("Dashboard", 0),
            ("Devices", 1),
            ("Display", 2),
            ("Stream View", 3),
            ("Performance", 4),
            ("Diagnostics", 5),
            ("Settings", 6),
        ]

        for text, idx in nav_items:
            btn = QPushButton(text)
            btn.setProperty("class", "NavButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, i=idx: self._switch_page(i))
            layout.addWidget(btn)
            self.nav_buttons.append(btn)

        self.nav_buttons[0].setChecked(True)
        layout.addStretch(1)

        # Bottom System Info
        sys_info = QLabel(f"Host: {self.identity.display_name}\nv0.1.0 MVP")
        sys_info.setStyleSheet("color: #475569; font-size: 11px;")
        layout.addWidget(sys_info)

        return sidebar

    def _switch_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        if index == 1:
            self._refresh_devices_table()
        elif index == 5:
            self._refresh_diagnostics_table()

    # 1. Dashboard Page
    def _build_dashboard_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Top Header
        top_row = QHBoxLayout()
        heading_col = QVBoxLayout()
        heading = QLabel("Workspace Overview")
        heading.setStyleSheet("font-size: 24px; font-weight: 700; color: #f8fafc;")
        subheading = QLabel("Manage your dual-PC extended desktop, input routing, and stream.")
        subheading.setStyleSheet("color: #94a3b8; font-size: 13px;")
        heading_col.addWidget(heading)
        heading_col.addWidget(subheading)
        top_row.addLayout(heading_col)
        top_row.addStretch(1)

        # Role Selector Pill
        role_box = QHBoxLayout()
        role_label = QLabel("Role:")
        role_label.setStyleSheet("color: #94a3b8; font-weight: 600;")
        self.role_combo = QComboBox()
        self.role_combo.addItems(["Host (Primary PC)", "Client (Second PC)"])
        self.role_combo.setCurrentIndex(0 if self.role == "host" else 1)
        self.role_combo.currentIndexChanged.connect(self._on_role_changed)
        role_box.addWidget(role_label)
        role_box.addWidget(self.role_combo)
        top_row.addLayout(role_box)
        layout.addLayout(top_row)

        # Status Cards Grid
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)
        self.card_conn = StatCard("Connection", "Not connected", "Awaiting peer selection.")
        self.card_driver = StatCard(
            "Virtual Display",
            "Active" if self.driver_status.is_installed else "Not Installed",
            self.driver_status.status_summary,
            is_active=self.driver_status.is_installed,
        )
        self.card_stream = StatCard("Stream State", "Inactive", "No active frame transmission.")
        cards_layout.addWidget(self.card_conn)
        cards_layout.addWidget(self.card_driver)
        cards_layout.addWidget(self.card_stream)
        layout.addLayout(cards_layout)

        # Persistent honest disclosure notice
        self.notice = NoticeBanner(
            "Screen Preview Prototype: True extended desktop requires the native Windows IDD/IddCx driver. "
            "Without the driver, this prototype streams an existing screen preview. Applications execute on the host."
        )
        layout.addWidget(self.notice)

        # Live Metrics Strip
        self.metric_strip = LiveMetricStrip()
        layout.addWidget(self.metric_strip)

        # Action Buttons
        btn_row = QHBoxLayout()
        self.btn_connect = QPushButton("Start Session")
        self.btn_connect.setProperty("class", "PrimaryButton")
        self.btn_connect.clicked.connect(self._toggle_connection)

        self.btn_devices = QPushButton("Discover & Pair Devices")
        self.btn_devices.setProperty("class", "SecondaryButton")
        self.btn_devices.clicked.connect(lambda: self._switch_page(1))

        btn_row.addWidget(self.btn_connect)
        btn_row.addWidget(self.btn_devices)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # Host & Client Device Cards
        devices_row = QHBoxLayout()
        self.host_card = DeviceCard(
            "Local Machine (Host)",
            self.identity.display_name,
            "127.0.0.1",
            self.identity.fingerprint,
        )
        self.client_card = DeviceCard(
            "Remote Client",
            "None Connected",
            "—",
            "—",
        )
        devices_row.addWidget(self.host_card)
        devices_row.addWidget(self.client_card)
        layout.addLayout(devices_row)

        layout.addStretch(1)
        return page

    # 2. Devices Page
    def _build_devices_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title = QLabel("Device Management")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(title)

        # Firewall Status Banner
        self.firewall_status = check_firewall_status()
        if not self.firewall_status.is_firewall_ok:
            self.firewall_banner = NoticeBanner(
                f"Windows Defender Firewall may restrict local discovery. Blocked ports: {self.firewall_status.blocked_ports}. "
                "Run scripts/configure_firewall.ps1 to configure rules."
            )
            layout.addWidget(self.firewall_banner)

        # Manual Connect Box
        manual_box = QFrame()
        manual_box.setProperty("class", "Card")
        m_layout = QHBoxLayout(manual_box)
        m_layout.addWidget(QLabel("Connect by IP:"))
        self.manual_ip_input = QLineEdit()
        self.manual_ip_input.setPlaceholderText("192.168.1.xxx")
        self.btn_manual_connect = QPushButton("Add & Connect")
        self.btn_manual_connect.setProperty("class", "SecondaryButton")
        self.btn_manual_connect.clicked.connect(self._on_manual_connect)
        m_layout.addWidget(self.manual_ip_input)
        m_layout.addWidget(self.btn_manual_connect)
        layout.addWidget(manual_box)

        # Discovered Devices
        layout.addWidget(QLabel("Discovered LAN Peers"))
        self.discovered_table = QTableWidget(0, 5)
        self.discovered_table.setHorizontalHeaderLabels(["Device Name", "IP Address", "Role", "Driver", "Action"])
        self.discovered_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.discovered_table)

        # Paired Devices
        layout.addWidget(QLabel("Paired & Trusted Devices"))
        self.paired_table = QTableWidget(0, 4)
        self.paired_table.setHorizontalHeaderLabels(["Device Name", "Fingerprint", "Trust Status", "Action"])
        self.paired_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.paired_table)

        return page

    # 3. Display Page
    def _build_display_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title = QLabel("Display Settings")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(title)

        form_card = QFrame()
        form_card.setProperty("class", "Card")
        f_layout = QVBoxLayout(form_card)

        # Virtual Display Toggle
        v_row = QHBoxLayout()
        v_row.addWidget(QLabel("Virtual Extended Monitor:"))
        self.chk_virtual_display = QCheckBox("Enable Virtual Display")
        self.chk_virtual_display.setChecked(self.driver_status.is_installed)
        self.chk_virtual_display.setEnabled(self.driver_status.is_installed)
        v_row.addWidget(self.chk_virtual_display)
        v_row.addStretch(1)
        f_layout.addLayout(v_row)

        if not self.driver_status.is_installed:
            f_layout.addWidget(
                QLabel("⚠️ IDD driver is not installed. To enable true extended display, compile and install native driver in native/.")
            )

        self.btn_driver_wizard = QPushButton("Open Driver Installation Wizard")
        self.btn_driver_wizard.setProperty("class", "SecondaryButton")
        self.btn_driver_wizard.clicked.connect(self._open_driver_wizard)
        f_layout.addWidget(self.btn_driver_wizard)

        f_layout.addSpacing(10)

        # Resolution Selector
        res_row = QHBoxLayout()
        res_row.addWidget(QLabel("Target Resolution:"))
        self.res_combo = QComboBox()
        for mode in get_supported_modes():
            self.res_combo.addItem(mode.name, mode)
        self.res_combo.currentIndexChanged.connect(self._on_resolution_changed)
        res_row.addWidget(self.res_combo)
        res_row.addStretch(1)
        f_layout.addLayout(res_row)

        # Fullscreen Client
        self.chk_fullscreen = QCheckBox("Client Fullscreen on Connection")
        self.chk_fullscreen.setChecked(True)
        f_layout.addWidget(self.chk_fullscreen)

        layout.addWidget(form_card)

        # Multi-Monitor Virtual Display Arrangement Map (TASK-08)
        self.arrangement_card = DisplayArrangementCard(initial_placement=self.display_placement)
        self.arrangement_card.placement_changed.connect(self._on_display_placement_changed)
        layout.addWidget(self.arrangement_card)

        layout.addStretch(1)
        return page

    def _on_display_placement_changed(self, placement: str) -> None:
        self.display_placement = placement
        self.db.set_setting("secondary_display_placement", placement)
        if self.connection_manager.input_injector:
            self.connection_manager.input_injector.set_placement(placement)

    # 4. Stream View Page
    def _build_stream_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Remote Stream Viewport")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #f8fafc;")
        header.addWidget(title)
        header.addStretch(1)

        btn_popout = QPushButton("Pop Out Window")
        btn_popout.setProperty("class", "SecondaryButton")
        btn_popout.clicked.connect(self._popout_stream_window)
        header.addWidget(btn_popout)
        layout.addLayout(header)

        layout.addWidget(self.stream_viewer, 1)
        return page

    def _popout_stream_window(self) -> None:
        if not self._stream_window:
            self._stream_window = StreamWindow(self.connection_manager)
        self._stream_window.show()
        self._stream_window.raise_()
        self._stream_window.activateWindow()

    def _open_driver_wizard(self) -> None:
        wizard = DriverInstallWizardDialog(self)
        wizard.exec()

    def _on_stream_frame_received(self, frame_bytes: bytes) -> None:
        self.stream_viewer.update_frame(frame_bytes)
        if self._stream_window and self._stream_window.isVisible():
            self._stream_window.update_frame(frame_bytes)

    # 5. Performance Page
    def _build_performance_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title = QLabel("Performance & Codec Tuning")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(title)

        card = QFrame()
        card.setProperty("class", "Card")
        c_layout = QVBoxLayout(card)

        # Quality Preset
        p_row = QHBoxLayout()
        p_row.addWidget(QLabel("Quality Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["Low Latency (Interactive)", "Balanced (Default)", "High Fidelity (Crisp Text)"])
        self.preset_combo.setCurrentIndex(1)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        p_row.addWidget(self.preset_combo)
        c_layout.addLayout(p_row)

        # Bitrate Slider
        b_row = QHBoxLayout()
        b_row.addWidget(QLabel("Bitrate Limit:"))
        self.bitrate_slider = QSlider(Qt.Orientation.Horizontal)
        self.bitrate_slider.setRange(1000, 25000)
        self.bitrate_slider.setValue(6000)
        self.bitrate_val_label = QLabel("6000 kbps")
        self.bitrate_slider.valueChanged.connect(self._on_bitrate_changed)
        b_row.addWidget(self.bitrate_slider)
        b_row.addWidget(self.bitrate_val_label)
        c_layout.addLayout(b_row)

        layout.addWidget(card)

        # Hardware Video Encoder Status & Diagnostics Card (TASK-07)
        enc_card = QFrame()
        enc_card.setProperty("class", "Card")
        e_layout = QVBoxLayout(enc_card)

        e_header = QHBoxLayout()
        e_title = QLabel("Hardware Video Encoder Diagnostics")
        e_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #38bdf8;")
        e_header.addWidget(e_title)
        e_header.addStretch(1)

        self.lbl_encoder_badge = QLabel()
        e_header.addWidget(self.lbl_encoder_badge)
        e_layout.addLayout(e_header)

        e_details_grid = QVBoxLayout()
        e_details_grid.setSpacing(6)

        self.lbl_encoder_backend = QLabel()
        self.lbl_encoder_backend.setStyleSheet("font-size: 13px; font-weight: 600; color: #f8fafc;")
        e_details_grid.addWidget(self.lbl_encoder_backend)

        self.lbl_encoder_profile = QLabel()
        self.lbl_encoder_profile.setStyleSheet("font-size: 12px; color: #94a3b8;")
        e_details_grid.addWidget(self.lbl_encoder_profile)

        self.lbl_encoder_explanation = QLabel()
        self.lbl_encoder_explanation.setWordWrap(True)
        self.lbl_encoder_explanation.setStyleSheet("font-size: 12px; color: #64748b; margin-top: 4px;")
        e_details_grid.addWidget(self.lbl_encoder_explanation)

        e_layout.addLayout(e_details_grid)
        self._refresh_encoder_diagnostics()
        layout.addWidget(enc_card)

        # Performance History Graphs Row
        graphs_row = QHBoxLayout()
        graphs_row.setSpacing(16)
        self.latency_graph = LatencyGraphCard()
        self.fps_graph = FramerateGraphCard()
        graphs_row.addWidget(self.latency_graph)
        graphs_row.addWidget(self.fps_graph)
        layout.addLayout(graphs_row)

        # Adaptive Rate Controller Info Card
        adapt_card = QFrame()
        adapt_card.setProperty("class", "Card")
        a_layout = QVBoxLayout(adapt_card)
        a_title = QLabel("Adaptive Rate Controller")
        a_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #38bdf8;")
        a_layout.addWidget(a_title)

        a_desc = QLabel(
            "Dynamically modulates compression quality and target framerate in response to network send latency "
            "and socket backpressure to maintain real-time responsiveness."
        )
        a_desc.setWordWrap(True)
        a_desc.setStyleSheet("color: #94a3b8; font-size: 12px;")
        a_layout.addWidget(a_desc)

        a_metrics_row = QHBoxLayout()
        self.perf_fps_target_label = QLabel("Target FPS: 60")
        self.perf_fps_target_label.setStyleSheet("color: #f8fafc; font-size: 13px; font-weight: 600;")
        self.perf_quality_label = QLabel("Quality Target: 70%")
        self.perf_quality_label.setStyleSheet("color: #f8fafc; font-size: 13px; font-weight: 600;")
        self.perf_network_status_label = QLabel("Network Status: Nominal")
        self.perf_network_status_label.setStyleSheet("color: #10b981; font-size: 13px; font-weight: 600;")

        a_metrics_row.addWidget(self.perf_fps_target_label)
        a_metrics_row.addWidget(self.perf_quality_label)
        a_metrics_row.addWidget(self.perf_network_status_label)
        a_metrics_row.addStretch(1)
        a_layout.addLayout(a_metrics_row)

        layout.addWidget(adapt_card)
        layout.addStretch(1)
        return page

    # 5. Diagnostics Page
    def _build_diagnostics_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title = QLabel("System Diagnostics & Health")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(title)

        btn_row = QHBoxLayout()
        self.btn_export_diag = QPushButton("Export Redacted Diagnostic Bundle")
        self.btn_export_diag.setProperty("class", "PrimaryButton")
        self.btn_export_diag.clicked.connect(self._export_diagnostics)

        self.btn_refresh_diag = QPushButton("Refresh Events")
        self.btn_refresh_diag.setProperty("class", "SecondaryButton")
        self.btn_refresh_diag.clicked.connect(self._refresh_diagnostics_table)

        btn_row.addWidget(self.btn_export_diag)
        btn_row.addWidget(self.btn_refresh_diag)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.diag_table = QTableWidget(0, 4)
        self.diag_table.setHorizontalHeaderLabels(["Timestamp", "Level", "Component", "Event Code & Message"])
        self.diag_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.diag_table)

        return page

    # 6. Settings Page
    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title = QLabel("Preferences & Security")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(title)

        card = QFrame()
        card.setProperty("class", "Card")
        c_layout = QVBoxLayout(card)

        # Discovery setting
        self.chk_lan_discovery = QCheckBox("Enable Local Network Discovery Broadcast")
        self.chk_lan_discovery.setChecked(True)
        c_layout.addWidget(self.chk_lan_discovery)

        # Clipboard synchronization setting
        self.chk_clipboard_sync = QCheckBox("Enable Encrypted Bidirectional Clipboard Synchronization")
        sync_enabled = bool(self.db.get_setting("clipboard_sync_enabled", True))
        self.chk_clipboard_sync.setChecked(sync_enabled)
        self.chk_clipboard_sync.toggled.connect(self._on_clipboard_sync_toggled)
        self.connection_manager.clipboard_guard.enabled = sync_enabled
        c_layout.addWidget(self.chk_clipboard_sync)

        # Audio Streaming & Playback Controls Card
        c_layout.addSpacing(10)
        audio_card = QFrame()
        audio_card.setStyleSheet("background: #0f172a; border: 1px solid #1e293b; border-radius: 6px; padding: 12px;")
        a_layout = QVBoxLayout(audio_card)

        a_title = QLabel("REMOTE AUDIO STREAMING & JITTER BUFFER")
        a_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #38bdf8; letter-spacing: 0.5px;")
        a_layout.addWidget(a_title)

        self.chk_audio_forwarding = QCheckBox("Enable Audio Forwarding (16-bit PCM @ 48kHz Stereo)")
        audio_forwarding_enabled = bool(self.db.get_setting("audio_forwarding_enabled", True))
        self.chk_audio_forwarding.setChecked(audio_forwarding_enabled)
        self.chk_audio_forwarding.toggled.connect(self._on_audio_forwarding_toggled)
        a_layout.addWidget(self.chk_audio_forwarding)

        # Volume & Mute Row
        v_row = QHBoxLayout()
        self.chk_audio_mute = QCheckBox("Mute Audio")
        self.chk_audio_mute.setChecked(False)
        self.chk_audio_mute.toggled.connect(self._on_audio_mute_toggled)
        v_row.addWidget(self.chk_audio_mute)

        v_row.addWidget(QLabel("Volume:"))
        self.audio_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.audio_volume_slider.setRange(0, 150)
        self.audio_volume_slider.setValue(100)
        self.audio_volume_slider.valueChanged.connect(self._on_audio_volume_changed)
        v_row.addWidget(self.audio_volume_slider)

        self.lbl_audio_volume = QLabel("100%")
        self.lbl_audio_volume.setStyleSheet("font-weight: 600; color: #38bdf8;")
        v_row.addWidget(self.lbl_audio_volume)
        a_layout.addLayout(v_row)

        # Jitter Buffer Health Gauge
        self.lbl_audio_jitter_stats = QLabel(
            "Jitter Buffer: 0 frames (0.0 ms) | Overflows: 0 (0.0%) | Underruns: 0"
        )
        self.lbl_audio_jitter_stats.setStyleSheet("font-size: 11px; color: #94a3b8; font-family: monospace;")
        a_layout.addWidget(self.lbl_audio_jitter_stats)

        self.btn_reset_audio_stats = QPushButton("Reset Audio Buffer Counters")
        self.btn_reset_audio_stats.setProperty("class", "SecondaryButton")
        self.btn_reset_audio_stats.clicked.connect(self._on_reset_audio_stats)
        a_layout.addWidget(self.btn_reset_audio_stats)

        c_layout.addWidget(audio_card)

        # System Tray & Startup Card (TASK-09)
        c_layout.addSpacing(10)
        tray_card = QFrame()
        tray_card.setStyleSheet("background: #0f172a; border: 1px solid #1e293b; border-radius: 6px; padding: 12px;")
        t_layout = QVBoxLayout(tray_card)

        t_title = QLabel("SYSTEM TRAY & WINDOWS STARTUP")
        t_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #38bdf8; letter-spacing: 0.5px;")
        t_layout.addWidget(t_title)

        self.chk_minimize_to_tray = QCheckBox("Minimize to System Tray on Window Close")
        min_to_tray = bool(self.db.get_setting("minimize_to_tray", True))
        self.chk_minimize_to_tray.setChecked(min_to_tray)
        self.chk_minimize_to_tray.toggled.connect(lambda chk: self.db.set_setting("minimize_to_tray", chk))
        t_layout.addWidget(self.chk_minimize_to_tray)

        self.chk_auto_start = QCheckBox("Start DualDesk Minimized with Windows on Login")
        self.chk_auto_start.setChecked(is_auto_start_enabled())
        self.chk_auto_start.toggled.connect(self._on_auto_start_toggled)
        t_layout.addWidget(self.chk_auto_start)

        c_layout.addWidget(tray_card)

        # Security & Input Controls Card (TASK-10)
        c_layout.addSpacing(10)
        sec_input_card = QFrame()
        sec_input_card.setStyleSheet("background: #0f172a; border: 1px solid #1e293b; border-radius: 6px; padding: 12px;")
        s_layout = QVBoxLayout(sec_input_card)

        s_title = QLabel("INPUT ROUTING & EMERGENCY ESCAPE SHORTCUT")
        s_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #38bdf8; letter-spacing: 0.5px;")
        s_layout.addWidget(s_title)

        esc_row = QHBoxLayout()
        esc_row.addWidget(QLabel("Emergency Escape Combination:"))
        self.combo_escape = QComboBox()
        from dualdesk.security.input_filter import AVAILABLE_ESCAPE_SHORTCUTS

        for sc in AVAILABLE_ESCAPE_SHORTCUTS:
            self.combo_escape.addItem(sc)
        cur_idx = self.combo_escape.findText(self.escape_shortcut)
        if cur_idx != -1:
            self.combo_escape.setCurrentIndex(cur_idx)
        self.combo_escape.currentTextChanged.connect(self._on_escape_shortcut_changed)
        esc_row.addWidget(self.combo_escape)
        esc_row.addStretch(1)
        s_layout.addLayout(esc_row)

        self.chk_host_lockout = QCheckBox("Enable Host Physical Input Lockout during Active Remote Control")
        self.chk_host_lockout.setToolTip(
            "Suppresses local host physical mouse/keyboard events while remote client is actively controlling. "
            "The emergency escape shortcut always immediately revokes remote authority and restores host control."
        )
        self.chk_host_lockout.setChecked(self.host_input_lockout)
        self.chk_host_lockout.toggled.connect(self._on_host_lockout_toggled)
        s_layout.addWidget(self.chk_host_lockout)

        esc_desc = QLabel(
            "Pressing the emergency shortcut at any time unconditionally revokes remote input authority, "
            "synthesizes release of all keys/buttons, and returns immediate control to the host."
        )
        esc_desc.setWordWrap(True)
        esc_desc.setStyleSheet("color: #38bdf8; font-size: 11px; margin-top: 4px;")
        s_layout.addWidget(esc_desc)

        c_layout.addWidget(sec_input_card)

        c_layout.addSpacing(10)

        # Clear Data button
        self.btn_clear_data = QPushButton("Clear Trust Store & Connection History")
        self.btn_clear_data.setProperty("class", "DangerButton")
        self.btn_clear_data.clicked.connect(self._clear_all_data)
        c_layout.addWidget(self.btn_clear_data)

        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _on_audio_forwarding_toggled(self, checked: bool) -> None:
        self.db.set_setting("audio_forwarding_enabled", checked)
        if not checked:
            self.connection_manager.set_audio_muted(True)
        else:
            self.connection_manager.set_audio_muted(self.chk_audio_mute.isChecked())

    def _on_audio_mute_toggled(self, checked: bool) -> None:
        self.connection_manager.set_audio_muted(checked)

    def _on_audio_volume_changed(self, value: int) -> None:
        volume = value / 100.0
        self.lbl_audio_volume.setText(f"{value}%")
        self.connection_manager.set_audio_volume(volume)

    def _on_reset_audio_stats(self) -> None:
        self.audio_player.reset()
        stats = self.audio_player.get_stats()
        self.lbl_audio_jitter_stats.setText(
            f"Jitter Buffer: {stats['queue_size']} frames ({stats['buffer_latency_ms']:.1f} ms) | "
            f"Overflows: {stats['dropped_overflow']} ({stats['drop_percentage']:.1f}%) | "
            f"Underruns: {stats['underruns']}"
        )

    def _on_escape_shortcut_changed(self, text: str) -> None:
        self.escape_shortcut = text
        self.db.set_setting("escape_shortcut", text)
        self.connection_manager.set_escape_shortcut(text)

    def _on_host_lockout_toggled(self, checked: bool) -> None:
        self.host_input_lockout = checked
        self.db.set_setting("host_input_lockout", checked)
        self.connection_manager.set_host_input_lockout(checked)

    # Event handlers
    def _on_resolution_changed(self, idx: int) -> None:
        mode = self.res_combo.currentData()
        if not mode:
            return

        if self.role == "client":
            if self.connection_manager.state == ConnectionState.STREAMING:
                self.connection_manager.request_display_mode(mode.width, mode.height, mode.refresh_rate)
        else:
            self.capture_adapter.set_resolution(mode.width, mode.height, mode.refresh_rate)
            if self.connection_manager.input_filter:
                self.connection_manager.input_filter.update_bounds(mode.width, mode.height)
            if self.connection_manager.input_injector:
                self.connection_manager.input_injector.update_bounds(mode.width, mode.height)
            if hasattr(self, "arrangement_card"):
                self.arrangement_card.canvas.set_resolutions("1920x1080", f"{mode.width}x{mode.height}")
            if self.connection_manager.state == ConnectionState.STREAMING:
                self.connection_manager.broadcast_display_mode(mode)

    def _on_preset_changed(self, idx: int) -> None:
        bitrates = [4000, 6000, 12000]
        bitrate = bitrates[idx] if idx < len(bitrates) else 6000
        self.bitrate_slider.setValue(bitrate)

    def _on_bitrate_changed(self, value: int) -> None:
        self.bitrate_val_label.setText(f"{value} kbps")
        self.capture_adapter._estimated_bitrate_kbps = float(value)

    def _on_role_changed(self, idx: int) -> None:
        new_role = "host" if idx == 0 else "client"
        self.role = new_role
        self.db.set_setting("role", new_role)
        self.beacon.role = new_role
        self.connection_manager.role = new_role
        if new_role == "host":
            self.connection_manager.start_control_server()
        else:
            self.connection_manager.stop_control_server()

    def _toggle_connection(self) -> None:
        if self.connection_manager.state == ConnectionState.STREAMING:
            self.capture_adapter.stop_capture()
            self.connection_manager.disconnect()
            self.btn_connect.setText("Start Session")
        else:
            # Check if there is a paired device or connect locally
            paired_devices = self.db.list_devices(trust_status="paired")
            if not paired_devices:
                # Prompt user to pair first or pair with demo loopback peer for testing
                res = QMessageBox.question(
                    self,
                    "Pairing Required",
                    "No paired devices found. Would you like to pair with a local loopback client for testing?",
                )
                if res == QMessageBox.StandardButton.Yes:
                    test_dev_id = "test-client-01"
                    challenge = self.connection_manager.start_pairing(
                        peer_device_id=test_dev_id,
                        peer_name="Test Client PC",
                        peer_fingerprint="SHA256:TEST-0000-1111-2222",
                    )
                    diag = PairingDialog("Test Client PC", challenge.challenge_id, challenge.code, self)
                    if diag.exec():
                        submitted = diag.get_submitted_code()
                        # Auto verify
                        self.connection_manager.confirm_pairing(
                            challenge_id=challenge.challenge_id,
                            code=submitted,
                            peer_fingerprint="SHA256:TEST-0000-1111-2222",
                        )
                        QMessageBox.information(self, "Paired", "Test Client successfully paired!")
                        self._refresh_devices_table()
                return

            peer = paired_devices[0]
            self.capture_adapter.start_capture()
            success = self.connection_manager.connect(
                peer_device_id=peer.device_id,
                peer_fingerprint=peer.public_key_fingerprint or "",
                peer_address="127.0.0.1",
            )
            if success:
                self.btn_connect.setText("Disconnect Session")
                self.client_card.set_device(
                    peer.display_name,
                    "127.0.0.1",
                    peer.public_key_fingerprint or "—",
                )

    def _on_manual_connect(self) -> None:
        ip = self.manual_ip_input.text().strip()
        if not ip:
            return
        self.discovery.add_manual_device(ip)
        self._refresh_devices_table()
        QMessageBox.information(self, "Manual Device Added", f"Added manual target {ip}. Use Pair button to verify.")

    def _on_clipboard_sync_toggled(self, checked: bool) -> None:
        self.db.set_setting("clipboard_sync_enabled", checked)
        self.connection_manager.clipboard_guard.enabled = checked
        if checked:
            if self.connection_manager.state == ConnectionState.STREAMING:
                self.connection_manager.clipboard_adapter.start_monitoring()
        else:
            self.connection_manager.clipboard_adapter.stop_monitoring()

    def _on_connection_state_changed(self, state: ConnectionState, detail: str) -> None:
        is_active = state == ConnectionState.STREAMING
        self.card_conn.update_values(state.value, detail or "Session state updated", is_active=is_active)
        if hasattr(self, "tray_icon"):
            self.tray_icon.setIcon(create_tray_icon(state.value))
        if hasattr(self, "tray_status_action"):
            self.tray_status_action.setText(f"Status: {state.value.capitalize()}")
        if hasattr(self, "tray_connect_action"):
            self.tray_connect_action.setText("Disconnect Session" if is_active else "Start Session")

        if state == ConnectionState.STREAMING:
            self.card_stream.update_values(
                "Streaming",
                self.capture_adapter.source_label,
                is_active=True,
            )
            self.btn_connect.setText("Disconnect Session")
            if self.chk_clipboard_sync.isChecked():
                self.connection_manager.clipboard_adapter.start_monitoring()
        elif state == ConnectionState.RECOVERING:
            self.card_conn.update_values("Recovering", detail or "Attempting automatic reconnection...", is_active=False)
            self.card_stream.update_values("Interrupted", "Attempting automatic reconnect...", is_active=False)
            self.btn_connect.setText("Cancel Reconnect")
        elif state in (ConnectionState.DISCONNECTED, ConnectionState.NOT_CONNECTED):
            self.card_stream.update_values("Inactive", "No active frame transmission.", is_active=False)
            self.btn_connect.setText("Start Session")
            self.connection_manager.clipboard_adapter.stop_monitoring()

    def _toggle_connection(self) -> None:
        if self.connection_manager.state == ConnectionState.STREAMING:
            self.connection_manager.disconnect(reason="User disconnect")
        elif self.connection_manager.state == ConnectionState.RECOVERING:
            self.connection_manager.cancel_reconnect()
        else:
            if self.role == "client":
                paired = self.db.list_devices()
                if paired:
                    dev = paired[0]
                    self.connection_manager.connect(
                        peer_device_id=dev.device_id,
                        peer_fingerprint=dev.fingerprint,
                        peer_address=dev.last_known_ip or "127.0.0.1",
                    )
                else:
                    self._switch_page(1)
            else:
                self._switch_page(1)

    def _on_display_mode_changed(self, width: int, height: int, fps: int) -> None:
        """Adapts capture resolution on host when remote client negotiates target mode."""
        self.capture_adapter.set_resolution(width, height, fps)
        if self.connection_manager.input_filter:
            self.connection_manager.input_filter.update_bounds(width, height)
        if self.connection_manager.input_injector:
            self.connection_manager.input_injector.display_width = width
            self.connection_manager.input_injector.display_height = height
        self._sync_res_combo(width, height, fps)

    def _on_client_display_mode_negotiated(self, width: int, height: int, fps: int) -> None:
        """Synchronizes target resolution dropdown when host accepts negotiated mode."""
        self._sync_res_combo(width, height, fps)

    def _sync_res_combo(self, width: int, height: int, fps: int) -> None:
        if not hasattr(self, "res_combo"):
            return
        self.res_combo.blockSignals(True)
        try:
            matched_idx = -1
            for i in range(self.res_combo.count()):
                mode = self.res_combo.itemData(i)
                if mode and mode.width == width and mode.height == height and mode.refresh_rate == fps:
                    matched_idx = i
                    break
            if matched_idx == -1:
                for i in range(self.res_combo.count()):
                    mode = self.res_combo.itemData(i)
                    if mode and mode.width == width and mode.height == height:
                        matched_idx = i
                        break
            if matched_idx != -1:
                self.res_combo.setCurrentIndex(matched_idx)
        finally:
            self.res_combo.blockSignals(False)

    def _on_telemetry_updated(self, telemetry: SessionTelemetry) -> None:
        quality = getattr(telemetry, "quality", 70)
        target_fps = getattr(telemetry, "target_fps", 60)
        network_status = getattr(telemetry, "network_status", "Nominal")
        codec = getattr(telemetry, "codec", "jpeg")
        is_congested = network_status in ("Congested", "Backpressure")

        self.metric_strip.update_metrics(
            fps=telemetry.fps,
            latency_ms=telemetry.latency_ms,
            bitrate_kbps=telemetry.bitrate_kbps,
            dropped=telemetry.dropped_frames,
            quality=quality,
            target_fps=target_fps,
            network_status=network_status,
            codec=codec,
        )

        sample = TelemetrySample(
            timestamp=time.time(),
            fps=telemetry.fps,
            latency_ms=telemetry.latency_ms,
            bitrate_kbps=telemetry.bitrate_kbps,
            dropped_frames=telemetry.dropped_frames,
            network_status=network_status,
            is_congested=is_congested,
        )
        self.telemetry_history.append(sample)

        if hasattr(self, "latency_graph"):
            self.latency_graph.update_history(self.telemetry_history)
        if hasattr(self, "fps_graph"):
            self.fps_graph.update_history(self.telemetry_history)

        if hasattr(self, "perf_fps_target_label"):
            self.perf_fps_target_label.setText(f"Target FPS: {target_fps}")
        if hasattr(self, "perf_quality_label"):
            self.perf_quality_label.setText(f"Quality Target: {quality}%")
        if hasattr(self, "perf_network_status_label"):
            status_colors = {
                "Nominal": "#10b981",
                "Recovering": "#38bdf8",
                "Congested": "#f59e0b",
                "Backpressure": "#ef4444",
            }
            color = status_colors.get(network_status, "#38bdf8")
            self.perf_network_status_label.setText(f"Network Status: {network_status}")
            self.perf_network_status_label.setStyleSheet(
                f"color: {color}; font-size: 13px; font-weight: 600;"
            )

    def _on_timer_tick(self) -> None:
        if self.connection_manager.state == ConnectionState.STREAMING and self.role == "host":
            frame_bytes, stats = self.capture_adapter.capture_next_frame()
            if frame_bytes:
                self.connection_manager.broadcast_frame(frame_bytes)

            target_fps = 60
            network_status = "Nominal"
            quality = stats.quality
            if self.adaptive_controller:
                target_fps = self.adaptive_controller.current_fps
                quality = self.adaptive_controller.current_quality
                network_status = self.adaptive_controller.network_status

            self.connection_manager.update_telemetry(
                fps=stats.fps,
                latency_ms=stats.latency_ms,
                bitrate_kbps=stats.bitrate_kbps,
                dropped_frames=stats.dropped_frames,
                quality=quality,
                target_fps=target_fps,
                network_status=network_status,
                codec=stats.codec,
            )

        if hasattr(self, "lbl_audio_jitter_stats"):
            astats = self.audio_player.get_stats()
            self.lbl_audio_jitter_stats.setText(
                f"Jitter Buffer: {astats['queue_size']} frames ({astats['buffer_latency_ms']:.1f} ms) | "
                f"Overflows: {astats['dropped_overflow']} ({astats['drop_percentage']:.1f}%) | "
                f"Underruns: {astats['underruns']}"
            )


    def _refresh_devices_table(self) -> None:
        # Discovered peers
        discovered = self.discovery.get_discovered_devices()
        self.discovered_table.setRowCount(len(discovered))
        for row, dev in enumerate(discovered):
            self.discovered_table.setItem(row, 0, QTableWidgetItem(dev.display_name))
            self.discovered_table.setItem(row, 1, QTableWidgetItem(f"{dev.ip_address}:{dev.port}"))
            self.discovered_table.setItem(row, 2, QTableWidgetItem(dev.role))
            self.discovered_table.setItem(row, 3, QTableWidgetItem("IDD Virtual" if dev.has_virtual_driver else "Scaffold"))

            pair_btn = QPushButton("Pair Device")
            pair_btn.setProperty("class", "SecondaryButton")
            pair_btn.clicked.connect(lambda _, d=dev: self._pair_discovered_device(d))
            self.discovered_table.setCellWidget(row, 4, pair_btn)

        # Paired peers
        paired = self.db.list_devices()
        self.paired_table.setRowCount(len(paired))
        for row, p in enumerate(paired):
            self.paired_table.setItem(row, 0, QTableWidgetItem(p.display_name))
            self.paired_table.setItem(row, 1, QTableWidgetItem(p.public_key_fingerprint or "None"))
            self.paired_table.setItem(row, 2, QTableWidgetItem(p.trust_status))

            action_widget = QWidget()
            a_layout = QHBoxLayout(action_widget)
            a_layout.setContentsMargins(0, 0, 0, 0)
            if p.trust_status == "paired":
                revoke_btn = QPushButton("Revoke")
                revoke_btn.setProperty("class", "DangerButton")
                revoke_btn.clicked.connect(lambda _, d_id=p.device_id: self._revoke_device(d_id))
                a_layout.addWidget(revoke_btn)
            else:
                unpair_btn = QPushButton("Remove")
                unpair_btn.setProperty("class", "SecondaryButton")
                unpair_btn.clicked.connect(lambda _, d_id=p.device_id: self._delete_device(d_id))
                a_layout.addWidget(unpair_btn)
            self.paired_table.setCellWidget(row, 3, action_widget)

    def _pair_discovered_device(self, dev: DiscoveredDevice) -> None:
        challenge = self.connection_manager.start_pairing(
            peer_device_id=dev.device_id,
            peer_name=dev.display_name,
            peer_fingerprint=dev.fingerprint,
        )
        diag = PairingDialog(dev.display_name, challenge.challenge_id, challenge.code, self)
        if diag.exec():
            sub = diag.get_submitted_code()
            try:
                self.connection_manager.confirm_pairing(
                    challenge_id=challenge.challenge_id,
                    code=sub,
                    peer_fingerprint=dev.fingerprint,
                )
                QMessageBox.information(self, "Success", f"Paired with {dev.display_name}!")
                self._refresh_devices_table()
            except ProtocolError as e:
                QMessageBox.warning(self, "Pairing Failed", str(e))

    def _revoke_device(self, device_id: str) -> None:
        self.pairing_manager.revoke_peer(device_id)
        self._refresh_devices_table()

    def _delete_device(self, device_id: str) -> None:
        self.db.delete_device(device_id)
        self._refresh_devices_table()

    def _refresh_diagnostics_table(self) -> None:
        events = self.db.list_diagnostic_events(limit=50)
        self.diag_table.setRowCount(len(events))
        for row, ev in enumerate(events):
            self.diag_table.setItem(row, 0, QTableWidgetItem(ev.created_at))
            self.diag_table.setItem(row, 1, QTableWidgetItem(ev.level))
            self.diag_table.setItem(row, 2, QTableWidgetItem(ev.component))
            self.diag_table.setItem(row, 3, QTableWidgetItem(f"[{ev.event_code}] {ev.message_redacted}"))

    def _export_diagnostics(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Redacted Diagnostic Bundle",
            str(Path.home() / "dualdesk_diagnostics.json"),
            "JSON Files (*.json)",
        )
        if file_path:
            self.diagnostics_gen.export_to_file(Path(file_path))
            QMessageBox.information(
                self,
                "Bundle Exported",
                f"Redacted diagnostic bundle successfully saved to:\n{file_path}\n\nIPs and secrets have been redacted.",
            )

    def _refresh_encoder_diagnostics(self) -> None:
        summary = get_encoder_diagnostic_summary()
        self.encoder_summary = summary
        is_hw = summary["is_hardware_accelerated"]
        if is_hw:
            self.lbl_encoder_badge.setText("HARDWARE ACCELERATED")
            self.lbl_encoder_badge.setStyleSheet(
                "background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid #10b981; "
                "padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 700;"
            )
        else:
            self.lbl_encoder_badge.setText("SOFTWARE FALLBACK")
            self.lbl_encoder_badge.setStyleSheet(
                "background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid #f59e0b; "
                "padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 700;"
            )

        self.lbl_encoder_backend.setText(f"Active Backend: {summary['preferred_backend_name']}")
        codecs_str = ", ".join(c.upper() for c in summary["supported_codecs"])
        self.lbl_encoder_profile.setText(
            f"Profile: {summary['profile']} | Codecs: {codecs_str} | Max: {summary['max_resolution']} @ {summary['max_fps']} FPS"
        )
        self.lbl_encoder_explanation.setText(summary["explanation"])

    def _clear_all_data(self) -> None:
        res = QMessageBox.question(
            self,
            "Confirm Clear",
            "This will delete all paired device trust records, diagnostic events, and connection history. Continue?",
        )
        if res == QMessageBox.StandardButton.Yes:
            self.db.clear_diagnostic_events()
            self.db.clear_connection_history()
            for dev in self.db.list_devices():
                self.db.delete_device(dev.device_id)
            self._refresh_devices_table()
            self._refresh_diagnostics_table()
            QMessageBox.information(self, "Data Cleared", "Trust store and local history cleared.")

    def _setup_system_tray(self) -> None:
        self.tray_icon = QSystemTrayIcon(create_tray_icon("inactive"), self)
        self.tray_icon.setToolTip("DualDesk — Extended Display Utility")

        tray_menu = QMenu()
        act_show = tray_menu.addAction("Show DualDesk")
        act_show.triggered.connect(self._show_from_tray)

        self.tray_status_action = tray_menu.addAction("Status: Disconnected")
        self.tray_status_action.setEnabled(False)

        self.tray_connect_action = tray_menu.addAction("Start Session")
        self.tray_connect_action.triggered.connect(self._toggle_connection)

        tray_menu.addSeparator()

        act_exit = tray_menu.addAction("Exit DualDesk")
        act_exit.triggered.connect(self._quit_application)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            if self.isVisible():
                self.hide()
            else:
                self._show_from_tray()

    def _quit_application(self) -> None:
        self._force_quit = True
        self.close()

    def _on_auto_start_toggled(self, checked: bool) -> None:
        success = set_auto_start(checked)
        self.db.set_setting("auto_start_enabled", checked)
        if not success and checked:
            QMessageBox.warning(
                self,
                "Registry Access",
                "Could not update Windows startup registry key. Ensure sufficient user permissions.",
            )
            self.chk_auto_start.setChecked(False)

    def closeEvent(self, event) -> None:
        if not self._force_quit and hasattr(self, "chk_minimize_to_tray") and self.chk_minimize_to_tray.isChecked():
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "DualDesk",
                "DualDesk minimized to system tray. Active sessions remain connected.",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
            return

        self.tray_icon.hide()
        self.discovery.stop()
        self.connection_manager.stop_control_server()
        self.connection_manager.disconnect(reason="App closed")
        self.db.close()
        event.accept()


def main() -> int:
    enable_per_monitor_dpi_awareness()
    app = QApplication(sys.argv)
    app.setApplicationName("DualDesk")
    app.setStyleSheet(DARK_THEME_QSS)
    window = DualDeskApp()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import sys
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
    QMessageBox,
    QPushButton,
    QSlider,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from dualdesk.diagnostics.bundle import DiagnosticBundleGenerator
from dualdesk.display.capture import ScreenCaptureAdapter
from dualdesk.display.driver import check_virtual_display_driver, get_supported_modes
from dualdesk.network.discovery import DiscoveredDevice, DiscoveryBeacon, DiscoveryService
from dualdesk.network.transport import ConnectionManager, ConnectionState, SessionTelemetry
from dualdesk.security.identity import DeviceIdentity, get_or_create_device_identity
from dualdesk.security.pairing import PairingManager
from dualdesk.storage.db import DualDeskDB
from dualdesk.ui.components import (
    DeviceCard,
    LiveMetricStrip,
    NoticeBanner,
    PairingDialog,
    StatCard,
)
from dualdesk.ui.theme import DARK_THEME_QSS


class DualDeskApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DualDesk — Extended Desktop & Input Utility")
        self.resize(1080, 720)
        self.setMinimumSize(940, 600)

        # Initialize Backend Services
        self.db = DualDeskDB()
        self.identity: DeviceIdentity = get_or_create_device_identity(self.db)
        self.pairing_manager = PairingManager(self.db, self.identity.fingerprint)
        self.driver_status = check_virtual_display_driver()

        saved_role = self.db.get_setting("role", "host")
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

        self.capture_adapter = ScreenCaptureAdapter(
            width=1920,
            height=1080,
            target_fps=60,
            is_virtual_display=self.driver_status.is_installed,
        )

        self.connection_manager = ConnectionManager(
            db=self.db,
            pairing_manager=self.pairing_manager,
            role=self.role,
            on_state_changed=self._on_connection_state_changed,
            on_telemetry_updated=self._on_telemetry_updated,
        )

        self.diagnostics_gen = DiagnosticBundleGenerator(self.db)

        # Setup UI
        self._build_ui()

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
            ("Performance", 3),
            ("Diagnostics", 4),
            ("Settings", 5),
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
        elif index == 4:
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

        f_layout.addSpacing(10)

        # Resolution Selector
        res_row = QHBoxLayout()
        res_row.addWidget(QLabel("Target Resolution:"))
        self.res_combo = QComboBox()
        for mode in get_supported_modes():
            self.res_combo.addItem(mode.name, mode)
        res_row.addWidget(self.res_combo)
        res_row.addStretch(1)
        f_layout.addLayout(res_row)

        # Fullscreen Client
        self.chk_fullscreen = QCheckBox("Client Fullscreen on Connection")
        self.chk_fullscreen.setChecked(True)
        f_layout.addWidget(self.chk_fullscreen)

        layout.addWidget(form_card)
        layout.addStretch(1)
        return page

    # 4. Performance Page
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
        p_row.addWidget(self.preset_combo)
        c_layout.addLayout(p_row)

        # Bitrate Slider
        b_row = QHBoxLayout()
        b_row.addWidget(QLabel("Bitrate Limit:"))
        self.bitrate_slider = QSlider(Qt.Orientation.Horizontal)
        self.bitrate_slider.setRange(1000, 25000)
        self.bitrate_slider.setValue(6000)
        self.bitrate_val_label = QLabel("6000 kbps")
        self.bitrate_slider.valueChanged.connect(lambda v: self.bitrate_val_label.setText(f"{v} kbps"))
        b_row.addWidget(self.bitrate_slider)
        b_row.addWidget(self.bitrate_val_label)
        c_layout.addLayout(b_row)

        # Hardware Encoding
        hw_label = QLabel("Encoder: DXGI Desktop Duplication + H.264 Software Fallback")
        hw_label.setStyleSheet("color: #94a3b8;")
        c_layout.addWidget(hw_label)

        layout.addWidget(card)
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

        # Emergency Escape Info
        escape_info = QLabel(
            "Emergency Pointer/Keyboard Escape: Press Ctrl + Alt + Shift + Escape at any time "
            "to revoke remote input authority and return control to the host."
        )
        escape_info.setWordWrap(True)
        escape_info.setStyleSheet("color: #38bdf8; padding: 10px; background: #0f172a; border-radius: 6px;")
        c_layout.addWidget(escape_info)

        c_layout.addSpacing(10)

        # Clear Data button
        self.btn_clear_data = QPushButton("Clear Trust Store & Connection History")
        self.btn_clear_data.setProperty("class", "DangerButton")
        self.btn_clear_data.clicked.connect(self._clear_all_data)
        c_layout.addWidget(self.btn_clear_data)

        layout.addWidget(card)
        layout.addStretch(1)
        return page

    # Event handlers
    def _on_role_changed(self, idx: int) -> None:
        new_role = "host" if idx == 0 else "client"
        self.role = new_role
        self.db.set_setting("role", new_role)
        self.beacon.role = new_role

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
                    code = self.connection_manager.start_pairing(
                        peer_device_id=test_dev_id,
                        peer_name="Test Client PC",
                        peer_fingerprint="SHA256:TEST-0000-1111-2222",
                    )
                    diag = PairingDialog("Test Client PC", test_dev_id, code, self)
                    if diag.exec():
                        submitted = diag.get_submitted_code()
                        # Auto verify
                        self.connection_manager.confirm_pairing(
                            challenge_id=test_dev_id,
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

    def _on_connection_state_changed(self, state: ConnectionState, detail: str) -> None:
        is_active = state == ConnectionState.STREAMING
        self.card_conn.update_values(state.value, detail or "Session state updated", is_active=is_active)
        if state == ConnectionState.STREAMING:
            self.card_stream.update_values(
                "Streaming",
                self.capture_adapter.source_label,
                is_active=True,
            )
        elif state in (ConnectionState.DISCONNECTED, ConnectionState.NOT_CONNECTED):
            self.card_stream.update_values("Inactive", "No active frame transmission.", is_active=False)
            self.btn_connect.setText("Start Session")

    def _on_telemetry_updated(self, telemetry: SessionTelemetry) -> None:
        self.metric_strip.update_metrics(
            fps=telemetry.fps,
            latency_ms=telemetry.latency_ms,
            bitrate_kbps=telemetry.bitrate_kbps,
            dropped=telemetry.dropped_frames,
        )

    def _on_timer_tick(self) -> None:
        if self.connection_manager.state == ConnectionState.STREAMING:
            _, stats = self.capture_adapter.capture_next_frame()
            self.connection_manager.update_telemetry(
                fps=stats.fps,
                latency_ms=stats.latency_ms,
                bitrate_kbps=stats.bitrate_kbps,
                dropped_frames=stats.dropped_frames,
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
        code = self.connection_manager.start_pairing(
            peer_device_id=dev.device_id,
            peer_name=dev.display_name,
            peer_fingerprint=dev.fingerprint,
        )
        diag = PairingDialog(dev.display_name, dev.device_id, code, self)
        if diag.exec():
            sub = diag.get_submitted_code()
            try:
                self.connection_manager.confirm_pairing(
                    challenge_id=dev.device_id,
                    code=sub,
                    peer_fingerprint=dev.fingerprint,
                )
                QMessageBox.information(self, "Success", f"Paired with {dev.display_name}!")
                self._refresh_devices_table()
            except Exception as e:
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

    def closeEvent(self, event) -> None:
        self.discovery.stop()
        self.connection_manager.disconnect(reason="App closed")
        self.db.close()
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("DualDesk")
    app.setStyleSheet(DARK_THEME_QSS)
    window = DualDeskApp()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

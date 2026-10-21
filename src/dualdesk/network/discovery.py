from __future__ import annotations

import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from dualdesk.protocol.models import AnnouncePayload, MessageEnvelope, MessageType


@dataclass
class DiscoveredDevice:
    device_id: str
    display_name: str
    platform: str
    role: str
    ip_address: str
    port: int
    fingerprint: str
    has_virtual_driver: bool
    last_seen_at: float


class DiscoveryBeacon:
    def __init__(
        self,
        device_id: str,
        display_name: str,
        platform_name: str,
        role: str,
        port: int,
        fingerprint: str,
        has_virtual_driver: bool = False,
    ) -> None:
        self.device_id = device_id
        self.display_name = display_name
        self.platform_name = platform_name
        self.role = role
        self.port = port
        self.fingerprint = fingerprint
        self.has_virtual_driver = has_virtual_driver

    def to_envelope(self) -> MessageEnvelope:
        payload = AnnouncePayload(
            device_id=self.device_id,
            display_name=self.display_name,
            platform=self.platform_name,
            role=self.role,
            port=self.port,
            fingerprint=self.fingerprint,
            has_virtual_driver=self.has_virtual_driver,
        )
        return MessageEnvelope(
            type=MessageType.DISCOVERY_ANNOUNCE.value,
            payload={
                "device_id": payload.device_id,
                "display_name": payload.display_name,
                "platform": payload.platform,
                "role": payload.role,
                "port": payload.port,
                "fingerprint": payload.fingerprint,
                "has_virtual_driver": payload.has_virtual_driver,
            },
        )


class DiscoveryService:
    DEFAULT_PORT = 53891
    BROADCAST_INTERVAL = 3.0
    DEVICE_TIMEOUT = 12.0

    def __init__(
        self,
        beacon: DiscoveryBeacon,
        broadcast_port: int = DEFAULT_PORT,
        on_device_discovered: Callable[[DiscoveredDevice], None] | None = None,
    ) -> None:
        self.beacon = beacon
        self.broadcast_port = broadcast_port
        self.on_device_discovered = on_device_discovered
        self._running = False
        self._listener_thread: threading.Thread | None = None
        self._broadcaster_thread: threading.Thread | None = None
        self._discovered_devices: dict[str, DiscoveredDevice] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._running:
            return
        self._running = True

        self._listener_thread = threading.Thread(
            target=self._listen_loop, daemon=True, name="DiscoveryListener"
        )
        self._listener_thread.start()

        self._broadcaster_thread = threading.Thread(
            target=self._broadcast_loop, daemon=True, name="DiscoveryBroadcaster"
        )
        self._broadcaster_thread.start()

    def stop(self) -> None:
        self._running = False

    def get_discovered_devices(self) -> list[DiscoveredDevice]:
        now = time.time()
        with self._lock:
            # Prune stale devices
            valid = [
                dev
                for dev in self._discovered_devices.values()
                if (now - dev.last_seen_at) <= self.DEVICE_TIMEOUT
            ]
            return valid

    def add_manual_device(self, ip_address: str, port: int = DEFAULT_PORT) -> DiscoveredDevice:
        """Allows manual device connection when broadcast is disabled or blocked on LAN."""
        dev = DiscoveredDevice(
            device_id=f"manual-{ip_address}:{port}",
            display_name=f"Manual Host ({ip_address})",
            platform="Unknown",
            role="host",
            ip_address=ip_address,
            port=port,
            fingerprint="",
            has_virtual_driver=False,
            last_seen_at=time.time(),
        )
        with self._lock:
            self._discovered_devices[dev.device_id] = dev
        if self.on_device_discovered:
            self.on_device_discovered(dev)
        return dev

    def _broadcast_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(1.0)

        while self._running:
            try:
                env = self.beacon.to_envelope()
                msg = env.serialize().encode("utf-8")
                sock.sendto(msg, ("<broadcast>", self.broadcast_port))
            except OSError:
                # Network interface may be offline or broadcast restricted
                time.sleep(self.BROADCAST_INTERVAL)
                continue
            time.sleep(self.BROADCAST_INTERVAL)

        sock.close()

    def _listen_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", self.broadcast_port))
        except OSError:
            # If port is occupied or permission denied
            return
        sock.settimeout(1.0)

        while self._running:
            try:
                data, addr = sock.recvfrom(4096)
                if not data:
                    continue
                envelope = MessageEnvelope.deserialize(data.decode("utf-8"))
                if envelope.type != MessageType.DISCOVERY_ANNOUNCE.value:
                    continue

                p = envelope.payload
                sender_id = p.get("device_id")
                # Do not discover oneself
                if sender_id == self.beacon.device_id:
                    continue

                dev = DiscoveredDevice(
                    device_id=sender_id,
                    display_name=p.get("display_name", "Unknown"),
                    platform=p.get("platform", "Unknown"),
                    role=p.get("role", "host"),
                    ip_address=addr[0],
                    port=p.get("port", self.broadcast_port),
                    fingerprint=p.get("fingerprint", ""),
                    has_virtual_driver=bool(p.get("has_virtual_driver", False)),
                    last_seen_at=time.time(),
                )

                with self._lock:
                    self._discovered_devices[sender_id] = dev

                if self.on_device_discovered:
                    self.on_device_discovered(dev)
            except TimeoutError:
                continue
            except (OSError, UnicodeDecodeError):
                # Ignore non-fatal network receive and encoding errors
                continue

        sock.close()


@dataclass
class FirewallStatus:
    is_firewall_checked: bool
    is_firewall_ok: bool
    blocked_ports: list[int]
    status_summary: str
    can_configure: bool


def check_firewall_status(
    discovery_port: int = 53891,
    control_port: int = 53892,
    media_port: int = 53893,
) -> FirewallStatus:
    """Checks if Windows Defender Firewall has explicit rules for DualDesk ports."""
    import platform
    import subprocess
    from pathlib import Path

    if platform.system() != "Windows":
        return FirewallStatus(
            is_firewall_checked=True,
            is_firewall_ok=True,
            blocked_ports=[],
            status_summary="Non-Windows platform; Windows Firewall not applicable.",
            can_configure=False,
        )

    script_path = (
        Path(__file__).resolve().parents[3] / "scripts" / "configure_firewall.ps1"
    )
    if script_path.exists():
        try:
            proc = subprocess.run(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script_path),
                    "-CheckOnly",
                    "-DiscoveryPort",
                    str(discovery_port),
                    "-ControlPort",
                    str(control_port),
                    "-MediaPort",
                    str(media_port),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=6.0,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            output = proc.stdout
            missing: list[int] = []
            if f"UDP {discovery_port}" in output and "Missing rule" in output:
                missing.append(discovery_port)
            if f"TCP {control_port}" in output and "Missing rule" in output:
                missing.append(control_port)
            if f"TCP {media_port}" in output and "Missing rule" in output:
                missing.append(media_port)

            if missing:
                return FirewallStatus(
                    is_firewall_checked=True,
                    is_firewall_ok=False,
                    blocked_ports=missing,
                    status_summary=(
                        f"Firewall rules missing for ports: {missing}. "
                        "Run scripts/configure_firewall.ps1 to allow."
                    ),
                    can_configure=True,
                )
            return FirewallStatus(
                is_firewall_checked=True,
                is_firewall_ok=True,
                blocked_ports=[],
                status_summary="Windows Firewall allows inbound DualDesk traffic.",
                can_configure=True,
            )
        except (OSError, subprocess.SubprocessError):
            pass

    return FirewallStatus(
        is_firewall_checked=False,
        is_firewall_ok=True,
        blocked_ports=[],
        status_summary="Firewall check skipped or toolchain unavailable.",
        can_configure=True,
    )


def get_local_ip() -> str:
    """Detect active local LAN IP address for peer connection."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return str(s.getsockname()[0])
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"



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

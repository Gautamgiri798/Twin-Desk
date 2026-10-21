"""DualDesk network module: LAN UDP discovery, transport connection manager, and session lifecycle."""
from dualdesk.network.discovery import (
    DiscoveredDevice,
    DiscoveryBeacon,
    DiscoveryService,
    get_local_ip,
)
from dualdesk.network.transport import ConnectionManager, ConnectionState

__all__ = [
    "ConnectionManager",
    "ConnectionState",
    "DiscoveredDevice",
    "DiscoveryBeacon",
    "DiscoveryService",
    "get_local_ip",
]

"""DualDesk security module: identity, pairing challenge management, and input validation."""
from dualdesk.security.clipboard_guard import ClipboardGuard
from dualdesk.security.identity import DeviceIdentity, get_or_create_device_identity
from dualdesk.security.input_filter import InputFilter, InputSecurityError
from dualdesk.security.pairing import PairingManager, PairingSession

__all__ = [
    "ClipboardGuard",
    "DeviceIdentity",
    "InputFilter",
    "InputSecurityError",
    "PairingManager",
    "PairingSession",
    "get_or_create_device_identity",
]

from __future__ import annotations

import hashlib
import os
import platform
import socket
import uuid
from dataclasses import dataclass

from dualdesk.storage.db import DualDeskDB


@dataclass
class DeviceIdentity:
    device_id: str
    display_name: str
    platform_name: str
    fingerprint: str


def get_or_create_device_identity(db: DualDeskDB | None = None) -> DeviceIdentity:
    """Retrieves or creates a stable local device identity."""
    existing_id = db.get_setting("device_id") if db else None
    existing_fingerprint = db.get_setting("fingerprint") if db else None
    display_name = (
        db.get_setting("display_name")
        if (db and db.get_setting("display_name"))
        else socket.gethostname()
    )

    if not existing_id:
        existing_id = str(uuid.uuid4())
        if db:
            db.set_setting("device_id", existing_id)

    if not existing_fingerprint:
        # Cryptographic fingerprint derived from random machine token
        token = os.urandom(32)
        digest = hashlib.sha256(token).hexdigest()
        # Formatted in standard 8-character hex blocks (e.g. SHA256:abcd-ef01-...)
        formatted_fp = f"SHA256:{digest[:8]}-{digest[8:16]}-{digest[16:24]}-{digest[24:32]}".upper()
        existing_fingerprint = formatted_fp
        if db:
            db.set_setting("fingerprint", existing_fingerprint)

    plat = f"{platform.system()} {platform.release()}"

    return DeviceIdentity(
        device_id=existing_id,
        display_name=display_name,
        platform_name=plat,
        fingerprint=existing_fingerprint,
    )

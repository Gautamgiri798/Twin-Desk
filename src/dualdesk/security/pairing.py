from __future__ import annotations

import secrets
import time
import uuid
from dataclasses import dataclass

from dualdesk.protocol.models import ErrorCode, ProtocolError
from dualdesk.storage.db import DualDeskDB


@dataclass
class PairingSession:
    challenge_id: str
    peer_device_id: str
    peer_name: str
    peer_fingerprint: str
    code: str
    created_at: float
    expires_at: float
    attempts_remaining: int = 3
    is_confirmed: bool = False

    def __str__(self) -> str:
        return self.code


class PairingManager:
    """Manages secure, short-lived pairing challenges, verification, rate-limiting and trust store."""

    CHALLENGE_TIMEOUT_SECONDS = 60.0
    MAX_ATTEMPTS = 3

    def __init__(self, db: DualDeskDB, local_fingerprint: str) -> None:
        self.db = db
        self.local_fingerprint = local_fingerprint
        self._active_challenges: dict[str, PairingSession] = {}

    def create_challenge(
        self, peer_device_id: str, peer_name: str, peer_fingerprint: str
    ) -> PairingSession:
        """Generates a cryptographically random 6-digit code bound to peer identity."""
        # 6-digit PIN (100000 - 999999)
        code = f"{secrets.randbelow(900000) + 100000}"
        challenge_id = str(uuid.uuid4())
        now = time.time()

        session = PairingSession(
            challenge_id=challenge_id,
            peer_device_id=peer_device_id,
            peer_name=peer_name,
            peer_fingerprint=peer_fingerprint,
            code=code,
            created_at=now,
            expires_at=now + self.CHALLENGE_TIMEOUT_SECONDS,
            attempts_remaining=self.MAX_ATTEMPTS,
        )
        self._active_challenges[challenge_id] = session
        return session

    def get_challenge(self, challenge_id: str) -> PairingSession | None:
        session = self._active_challenges.get(challenge_id)
        if not session:
            for s in list(self._active_challenges.values()):
                if s.peer_device_id == challenge_id:
                    session = s
                    break
        if not session:
            return None
        if time.time() > session.expires_at:
            self._active_challenges.pop(session.challenge_id, None)
            return None
        return session

    def verify_code(
        self,
        challenge_id: str,
        submitted_code: str,
        peer_fingerprint: str,
    ) -> bool:
        """Verifies the code against the active challenge with rate-limiting and expiration."""
        session = self._active_challenges.get(challenge_id)
        if not session:
            for s in list(self._active_challenges.values()):
                if s.peer_device_id == challenge_id:
                    session = s
                    break
        if not session:
            raise ProtocolError(ErrorCode.SESSION_EXPIRED, "Pairing challenge does not exist or expired")

        actual_challenge_id = session.challenge_id
        now = time.time()
        if now > session.expires_at:
            self._active_challenges.pop(actual_challenge_id, None)
            raise ProtocolError(ErrorCode.SESSION_EXPIRED, "Pairing challenge expired")

        # Identity binding check
        if session.peer_fingerprint != peer_fingerprint:
            raise ProtocolError(
                ErrorCode.AUTHENTICATION_FAILED,
                "Peer fingerprint mismatch during pairing verification",
            )

        if session.attempts_remaining <= 0:
            self._active_challenges.pop(actual_challenge_id, None)
            raise ProtocolError(
                ErrorCode.PAIRING_REJECTED, "Too many failed attempts. Pairing challenge rejected."
            )

        # Constant-time comparison
        if secrets.compare_digest(session.code, submitted_code.strip()):
            session.is_confirmed = True
            # Persist device trust status in database
            self.db.upsert_device(
                device_id=session.peer_device_id,
                display_name=session.peer_name,
                platform="Windows",
                trust_status="paired",
                public_key_fingerprint=session.peer_fingerprint,
            )
            self._active_challenges.pop(actual_challenge_id, None)
            return True
        else:
            session.attempts_remaining -= 1
            if session.attempts_remaining <= 0:
                self._active_challenges.pop(actual_challenge_id, None)
                raise ProtocolError(
                    ErrorCode.PAIRING_REJECTED, "Invalid pairing code. Challenge invalidated."
                )
            return False

    def is_peer_paired(self, peer_device_id: str, peer_fingerprint: str) -> bool:
        """Checks if a peer device is paired and fingerprint matches."""
        device = self.db.get_device(peer_device_id)
        if not device or device.trust_status != "paired":
            return False
        return device.public_key_fingerprint == peer_fingerprint

    def revoke_peer(self, peer_device_id: str) -> bool:
        """Revokes trust for a peer device."""
        return self.db.update_trust_status(peer_device_id, "revoked")

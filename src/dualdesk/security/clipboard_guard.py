from __future__ import annotations

import hashlib
import time

from dualdesk.protocol.models import ErrorCode, ProtocolError


class ClipboardGuard:
    """
    Security and privacy guard for bidirectional clipboard synchronization.
    Enforces user opt-in policy, message size limits (1MB max), update rate limiting,
    null byte stripping, and SHA-256 hash tracking for loop suppression.
    """

    MAX_PAYLOAD_BYTES: int = 1_048_576  # 1 MB
    MAX_UPDATES_PER_SECOND: int = 5

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._rate_window_start = time.time()
        self._rate_count = 0

    @staticmethod
    def hash_text(text: str) -> str:
        """Returns SHA-256 hex digest for loop suppression."""
        return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()

    def _check_rate_limit(self) -> None:
        now = time.time()
        if now - self._rate_window_start > 1.0:
            self._rate_window_start = now
            self._rate_count = 0
        self._rate_count += 1
        if self._rate_count > self.MAX_UPDATES_PER_SECOND:
            raise ProtocolError(
                ErrorCode.INPUT_REJECTED,
                "Clipboard update rate limit exceeded (possible flood attack)",
            )

    def sanitize_and_validate(self, text: str) -> str:
        """
        Validates user policy, rate limits, strips null bytes, and clamps length to 1MB.
        Raises ProtocolError if clipboard sync is disabled or rate limit is exceeded.
        """
        if not self.enabled:
            raise ProtocolError(
                ErrorCode.INPUT_REJECTED,
                "Clipboard synchronization is disabled by user privacy policy",
            )

        self._check_rate_limit()

        if not text:
            return ""

        # Strip null bytes to prevent injection/truncation attacks
        cleaned = text.replace("\x00", "")

        # Enforce maximum byte length
        encoded = cleaned.encode("utf-8", errors="replace")
        if len(encoded) > self.MAX_PAYLOAD_BYTES:
            encoded = encoded[: self.MAX_PAYLOAD_BYTES]
            cleaned = encoded.decode("utf-8", errors="ignore")

        return cleaned

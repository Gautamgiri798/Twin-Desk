import base64
import binascii
import hashlib
import os
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dualdesk.protocol.models import (
    ErrorCode,
    FileTransferAcceptPayload,
    FileTransferChunkPayload,
    FileTransferRequestPayload,
    ProtocolError,
)

MAX_FILE_SIZE_BYTES = 250 * 1024 * 1024  # 250 MB
CHUNK_SIZE_BYTES = 64 * 1024  # 64 KB


def sanitize_filename(name: str) -> str:
    """
    Sanitizes filenames to prevent directory traversal and path injection attacks.
    Strips directory separators, relative path markers (..), null bytes, and colons.
    """
    if not name:
        return "transferred_file.bin"

    # Strip null bytes and control chars
    clean = re.sub(r"[\x00-\x1f\x7f]", "", name)
    # Extract only the basename (strips unix and windows path separators)
    clean = os.path.basename(clean.replace("\\", "/"))
    # Remove traversal dots and trailing whitespace/dots
    clean = re.sub(r"^\.+", "", clean).strip(". ")
    # Remove Windows prohibited chars: < > : " / \ | ? *
    clean = re.sub(r'[<>:"/\\|?*]', "_", clean)

    if not clean or clean in (".", ".."):
        return "transferred_file.bin"
    return clean


@dataclass
class ActiveIncomingTransfer:
    transfer_id: str
    original_filename: str
    safe_filename: str
    total_bytes: int
    expected_sha256: str
    part_file_path: Path
    bytes_received: int = 0
    received_chunks: int = 0
    hasher: Any = None

    def __post_init__(self) -> None:
        if self.hasher is None:
            self.hasher = hashlib.sha256()


class FileTransferManager:
    """
    Manages secure out-of-band file transfers over the TLS control channel.
    Enforces receiver consent, anti-directory traversal sanitization,
    250MB size limit, and per-chunk/full-file SHA-256 verification.
    """

    def __init__(
        self,
        save_dir: Path | None = None,
        auto_create_dir: bool = True,
        consent_callback: Callable[[FileTransferRequestPayload], bool] | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
        completion_callback: Callable[[str, bool, Path | None, str], None] | None = None,
    ) -> None:
        if save_dir is None:
            self.save_dir = Path.home() / "Downloads" / "DualDesk"
        else:
            self.save_dir = Path(save_dir)

        if auto_create_dir:
            self.save_dir.mkdir(parents=True, exist_ok=True)

        self.consent_callback = consent_callback
        self.progress_callback = progress_callback
        self.completion_callback = completion_callback

        self._incoming: dict[str, ActiveIncomingTransfer] = {}

    def prepare_outgoing_file(
        self, file_path: Path | str, sender_device_id: str = ""
    ) -> tuple[FileTransferRequestPayload, list[FileTransferChunkPayload]]:
        """Prepares a local file for streaming, validating bounds and generating chunks."""
        p = Path(file_path).resolve()
        if not p.is_file():
            raise FileNotFoundError(f"File not found: {p}")

        size = p.stat().st_size
        if size > MAX_FILE_SIZE_BYTES:
            raise ProtocolError(
                ErrorCode.FILE_TRANSFER_ERROR,
                f"File size ({size / (1024 * 1024):.1f}MB) exceeds 250MB limit.",
            )

        hasher = hashlib.sha256()
        raw_chunks: list[bytes] = []

        with open(p, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE_BYTES)
                if not chunk:
                    break
                hasher.update(chunk)
                raw_chunks.append(chunk)

        total_chunks = len(raw_chunks)
        transfer_id = str(uuid.uuid4())
        safe_name = sanitize_filename(p.name)

        req = FileTransferRequestPayload(
            transfer_id=transfer_id,
            file_name=safe_name,
            file_size_bytes=size,
            file_sha256=hasher.hexdigest(),
            sender_device_id=sender_device_id,
        )

        chunk_payloads: list[FileTransferChunkPayload] = []
        for idx, chunk_bytes in enumerate(raw_chunks):
            chunk_hash = hashlib.sha256(chunk_bytes).hexdigest()
            b64 = base64.b64encode(chunk_bytes).decode("ascii")
            chunk_payloads.append(
                FileTransferChunkPayload(
                    transfer_id=transfer_id,
                    chunk_index=idx,
                    total_chunks=total_chunks,
                    data_b64=b64,
                    chunk_sha256=chunk_hash,
                )
            )

        return req, chunk_payloads

    def handle_transfer_request(
        self, req: FileTransferRequestPayload, explicit_consent: bool | None = None
    ) -> FileTransferAcceptPayload:
        """Evaluates incoming transfer request, checks consent and constraints."""
        if req.file_size_bytes > MAX_FILE_SIZE_BYTES:
            return FileTransferAcceptPayload(
                transfer_id=req.transfer_id,
                accepted=False,
                reason=f"File exceeds maximum size limit of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.",
            )

        # Check explicit consent or prompt through callback
        consent = explicit_consent
        if consent is None and self.consent_callback is not None:
            consent = self.consent_callback(req)

        if not consent:
            return FileTransferAcceptPayload(
                transfer_id=req.transfer_id,
                accepted=False,
                reason="Transfer declined by receiver.",
            )

        safe_name = sanitize_filename(req.file_name)
        part_path = self.save_dir / f"{safe_name}.{req.transfer_id[:8]}.part"

        # Initialize transfer state
        self._incoming[req.transfer_id] = ActiveIncomingTransfer(
            transfer_id=req.transfer_id,
            original_filename=req.file_name,
            safe_filename=safe_name,
            total_bytes=req.file_size_bytes,
            expected_sha256=req.file_sha256,
            part_file_path=part_path,
        )

        # Reset or create part file
        if part_path.exists():
            part_path.unlink()
        part_path.touch()

        return FileTransferAcceptPayload(
            transfer_id=req.transfer_id,
            accepted=True,
            reason="Accepted by receiver",
        )

    def handle_chunk(self, chunk: FileTransferChunkPayload) -> bool:
        """Processes an incoming chunk, verifying chunk SHA-256 and appending to .part file."""
        incoming = self._incoming.get(chunk.transfer_id)
        if not incoming:
            return False

        try:
            raw_bytes = base64.b64decode(chunk.data_b64.encode("ascii"))
        except (ValueError, binascii.Error):
            self.cancel_transfer(chunk.transfer_id, reason="Corrupt base64 chunk payload")
            return False

        # Verify chunk hash
        actual_chunk_hash = hashlib.sha256(raw_bytes).hexdigest()
        if actual_chunk_hash.lower() != chunk.chunk_sha256.lower():
            self.cancel_transfer(chunk.transfer_id, reason="Chunk SHA-256 checksum mismatch")
            return False

        # Append to part file
        with open(incoming.part_file_path, "ab") as f:
            f.write(raw_bytes)

        incoming.hasher.update(raw_bytes)
        incoming.bytes_received += len(raw_bytes)
        incoming.received_chunks += 1

        if self.progress_callback:
            self.progress_callback(
                chunk.transfer_id, incoming.bytes_received, incoming.total_bytes
            )

        return True

    def finalize_transfer(self, transfer_id: str) -> tuple[bool, Path | None, str]:
        """Validates final SHA-256 checksum and renames .part file to target destination."""
        incoming = self._incoming.get(transfer_id)
        if not incoming:
            return False, None, "Transfer session not found"

        actual_sha256 = incoming.hasher.hexdigest().lower()
        if actual_sha256 != incoming.expected_sha256.lower():
            self.cancel_transfer(transfer_id, reason="Final file SHA-256 checksum mismatch")
            return False, None, "Integrity check failed: checksum mismatch"

        # Resolve destination path with collision avoidance
        dest = self.save_dir / incoming.safe_filename
        stem = dest.stem
        ext = dest.suffix
        counter = 1
        while dest.exists():
            dest = self.save_dir / f"{stem} ({counter}){ext}"
            counter += 1

        try:
            incoming.part_file_path.rename(dest)
        except OSError as e:
            self.cancel_transfer(transfer_id, reason=f"Failed to save destination file: {e}")
            return False, None, f"Disk write failure: {e}"

        del self._incoming[transfer_id]

        if self.completion_callback:
            self.completion_callback(transfer_id, True, dest, "Transfer complete")

        return True, dest, "File transfer successfully verified and saved"

    def cancel_transfer(self, transfer_id: str, reason: str = "Transfer cancelled") -> None:
        """Aborts active transfer and cleanly discards any partial or locked files."""
        incoming = self._incoming.pop(transfer_id, None)
        if incoming:
            if incoming.part_file_path.exists():
                try:
                    incoming.part_file_path.unlink()
                except OSError:
                    pass
            if self.completion_callback:
                self.completion_callback(transfer_id, False, None, reason)

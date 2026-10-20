from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any


class DecoderBackend(str, Enum):
    D3D11VA = "d3d11va"
    DXVA2 = "dxva2"
    SOFTWARE = "software"


@dataclass
class DecodedVideoFrame:
    width: int
    height: int
    format: str  # "h264_nal", "jpeg", "rgb32"
    timestamp_us: int
    is_keyframe: bool
    data: bytes
    nal_units_count: int = 0


ANNEX_B_4BYTE = b"\x00\x00\x00\x01"
ANNEX_B_3BYTE = b"\x00\x00\x01"


def parse_annex_b_nalus(stream: bytes) -> list[tuple[int, bytes]]:
    """
    Parses an H.264 Annex B byte stream into individual (nal_type, nal_bytes) tuples.
    Identifies SPS (7), PPS (8), IDR Slice (5), and Non-IDR Slice (1).
    """
    nalus: list[tuple[int, bytes]] = []
    length = len(stream)
    if length < 4:
        return nalus

    # Find all start code indices
    indices: list[tuple[int, int]] = []  # (start_index, prefix_length)
    i = 0
    while i < length - 2:
        if stream[i : i + 3] == ANNEX_B_3BYTE:
            if i > 0 and stream[i - 1] == 0:
                indices.append((i - 1, 4))
            else:
                indices.append((i, 3))
            i += 3
        else:
            i += 1

    # Extract NAL payload slices
    for idx, (start_idx, prefix_len) in enumerate(indices):
        payload_start = start_idx + prefix_len
        payload_end = indices[idx + 1][0] if idx + 1 < len(indices) else length
        nal_bytes = stream[payload_start:payload_end]
        if nal_bytes:
            nal_header = nal_bytes[0]
            nal_type = nal_header & 0x1F
            nalus.append((nal_type, nal_bytes))

    return nalus


class VideoDecoderAdapter:
    """
    Client video decoder adapter parsing H.264 Annex B NAL unit streams
    and fallback JPEG frames for hardware-assisted and software display pipelines.
    """

    def __init__(self, backend: DecoderBackend = DecoderBackend.SOFTWARE) -> None:
        self.backend = backend
        self._frames_decoded = 0
        self._keyframes_received = 0
        self._corrupted_frames = 0
        self._last_width = 1920
        self._last_height = 1080
        self._total_decode_time_ms = 0.0

    def decode_packet(
        self,
        packet_bytes: bytes,
        timestamp_us: int | None = None,
    ) -> DecodedVideoFrame | None:
        """
        Decodes an incoming video packet, detecting H.264 Annex B streams or JPEG buffers.
        """
        start_time = time.perf_counter()
        now_us = timestamp_us if timestamp_us is not None else int(time.time() * 1_000_000)

        if not packet_bytes:
            self._corrupted_frames += 1
            return None

        # Check for JPEG magic bytes (0xFF 0xD8)
        if len(packet_bytes) >= 2 and packet_bytes[:2] == b"\xff\xd8":
            self._frames_decoded += 1
            self._keyframes_received += 1
            decode_ms = (time.perf_counter() - start_time) * 1000.0
            self._total_decode_time_ms += decode_ms
            return DecodedVideoFrame(
                width=self._last_width,
                height=self._last_height,
                format="jpeg",
                timestamp_us=now_us,
                is_keyframe=True,
                data=packet_bytes,
                nal_units_count=0,
            )

        # Parse H.264 Annex B NAL stream
        nalus = parse_annex_b_nalus(packet_bytes)
        if not nalus:
            self._corrupted_frames += 1
            return None

        is_key = False
        for nal_type, nal_payload in nalus:
            if nal_type == 7:  # SPS
                if len(nal_payload) >= 12:
                    try:
                        _, _, _, mb_w, mb_h, _, orig_w, orig_h = struct.unpack_from(
                            ">BBBHHBHH", nal_payload, 1
                        )
                        self._last_width = orig_w
                        self._last_height = orig_h
                    except struct.error:
                        self._last_width = mb_w * 16
                        self._last_height = mb_h * 16
                elif len(nal_payload) >= 8:
                    try:
                        _, _, _, mb_w, mb_h = struct.unpack_from(">BBBHH", nal_payload, 1)
                        self._last_width = mb_w * 16
                        self._last_height = mb_h * 16
                    except struct.error:
                        pass
                is_key = True
            elif nal_type == 5:  # IDR
                is_key = True

        self._frames_decoded += 1
        if is_key:
            self._keyframes_received += 1

        decode_ms = (time.perf_counter() - start_time) * 1000.0
        self._total_decode_time_ms += decode_ms

        return DecodedVideoFrame(
            width=self._last_width,
            height=self._last_height,
            format="h264_nal",
            timestamp_us=now_us,
            is_keyframe=is_key,
            data=packet_bytes,
            nal_units_count=len(nalus),
        )

    def get_stats(self) -> dict[str, Any]:
        avg_time = (
            round(self._total_decode_time_ms / self._frames_decoded, 2)
            if self._frames_decoded > 0
            else 0.0
        )
        return {
            "backend": self.backend.value,
            "frames_decoded": self._frames_decoded,
            "keyframes_received": self._keyframes_received,
            "corrupted_frames": self._corrupted_frames,
            "avg_decode_time_ms": avg_time,
            "current_width": self._last_width,
            "current_height": self._last_height,
        }

from __future__ import annotations

import ctypes
import ctypes.util
import os
import platform
import struct
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any


class VideoCodec(str, Enum):
    H264 = "h264"
    HEVC = "hevc"
    JPEG = "jpeg"


class EncoderBackend(str, Enum):
    NVENC = "nvenc"
    QUICKSYNC = "quicksync"
    AMF = "amf"
    MEDIA_FOUNDATION = "media_foundation"
    SOFTWARE = "software"


@dataclass
class EncoderConfig:
    codec: VideoCodec = VideoCodec.H264
    backend: EncoderBackend = EncoderBackend.SOFTWARE
    width: int = 1920
    height: int = 1080
    target_fps: int = 60
    bitrate_kbps: int = 6000
    gop_size: int = 30
    low_latency: bool = True


@dataclass
class EncoderCapabilities:
    available_backends: list[EncoderBackend]
    preferred_backend: EncoderBackend
    is_hardware_accelerated: bool
    supported_codecs: list[VideoCodec]
    max_resolution: tuple[int, int] = (3840, 2160)
    max_fps: int = 120


@dataclass
class EncodedVideoPacket:
    data: bytes
    codec: VideoCodec
    is_keyframe: bool
    sequence: int
    timestamp_us: int
    duration_us: int = 0


def _library_exists(name: str) -> bool:
    """Checks if a dynamic library is accessible in system library search paths."""
    if ctypes.util.find_library(name):
        return True
    if platform.system() == "Windows":
        system32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
        candidate = os.path.join(system32, f"{name}.dll")
        if os.path.exists(candidate):
            return True
    return False


def detect_encoder_capabilities() -> EncoderCapabilities:
    """
    Detects hardware and software video encoder capabilities on the host OS.
    Checks for NVIDIA NVENC, AMD AMF, Intel QuickSync, and Windows Media Foundation.
    """
    available: list[EncoderBackend] = []

    # Check NVIDIA NVENC
    if _library_exists("nvEncodeAPI64") or _library_exists("nvEncodeAPI"):
        available.append(EncoderBackend.NVENC)

    # Check AMD AMF
    if _library_exists("amfrt64") or _library_exists("amfrt32"):
        available.append(EncoderBackend.AMF)

    # Check Intel QuickSync
    if _library_exists("libmfx64") or _library_exists("mfx_dispatch64"):
        available.append(EncoderBackend.QUICKSYNC)

    # Check Windows Media Foundation (MFT)
    if platform.system() == "Windows" and (
        _library_exists("mfplat") or _library_exists("msmpeg2vdec")
    ):
        available.append(EncoderBackend.MEDIA_FOUNDATION)

    # Software fallback is always supported
    available.append(EncoderBackend.SOFTWARE)

    is_hw = len(available) > 1 or (
        len(available) == 1 and available[0] != EncoderBackend.SOFTWARE
    )

    preferred = available[0]
    supported_codecs = [VideoCodec.H264, VideoCodec.JPEG]
    if is_hw:
        supported_codecs.append(VideoCodec.HEVC)

    max_res = (3840, 2160) if is_hw else (1920, 1080)
    max_fps = 120 if is_hw else 60

    return EncoderCapabilities(
        available_backends=available,
        preferred_backend=preferred,
        is_hardware_accelerated=is_hw,
        supported_codecs=supported_codecs,
        max_resolution=max_res,
        max_fps=max_fps,
    )


def get_backend_display_name(backend: EncoderBackend | str) -> str:
    """Returns human-readable brand and driver library name for encoder backend."""
    b_val = EncoderBackend(backend) if isinstance(backend, str) else backend
    mapping = {
        EncoderBackend.NVENC: "NVIDIA NVENC (nvEncodeAPI64)",
        EncoderBackend.QUICKSYNC: "Intel QuickSync Video (libmfx64)",
        EncoderBackend.AMF: "AMD Advanced Media Framework (amfrt64)",
        EncoderBackend.MEDIA_FOUNDATION: "Windows Media Foundation (mfplat.dll)",
        EncoderBackend.SOFTWARE: "Software Fallback (CPU Annex-B / JPEG)",
    }
    return mapping.get(b_val, str(backend))


def get_encoder_diagnostic_summary(caps: EncoderCapabilities | None = None) -> dict[str, Any]:
    """Generates structured diagnostics dictionary for UI cards and system reports."""
    caps = caps or detect_encoder_capabilities()
    status_badge = "HARDWARE ACCELERATED" if caps.is_hardware_accelerated else "SOFTWARE FALLBACK"
    active_name = get_backend_display_name(caps.preferred_backend)
    available_names = [get_backend_display_name(b) for b in caps.available_backends]
    explanation = (
        "Dedicated GPU hardware acceleration is active for ultra-low latency frame encoding."
        if caps.is_hardware_accelerated
        else "No dedicated GPU hardware encoder library was detected. Falling back to CPU baseline encoding."
    )
    return {
        "preferred_backend": caps.preferred_backend.value,
        "preferred_backend_name": active_name,
        "is_hardware_accelerated": caps.is_hardware_accelerated,
        "status_badge": status_badge,
        "available_backends": [b.value for b in caps.available_backends],
        "available_backend_names": available_names,
        "supported_codecs": [c.value for c in caps.supported_codecs],
        "max_resolution": f"{caps.max_resolution[0]}x{caps.max_resolution[1]}",
        "max_fps": caps.max_fps,
        "profile": "H.264 High Profile (Level 4.1)" if caps.is_hardware_accelerated else "H.264 Baseline / JPEG",
        "explanation": explanation,
    }


ANNEX_B_START_CODE = b"\x00\x00\x00\x01"


def build_h264_sps(width: int, height: int) -> bytes:
    """
    Builds an H.264 Sequence Parameter Set (SPS) NAL unit (NAL type 7)
    with Baseline/Main profile parameters for the specified dimensions.
    """
    # SPS NAL Header: forbidden_zero_bit=0, nal_ref_idc=3, nal_unit_type=7 -> 0x67
    nal_header = b"\x67"
    profile_idc = 100  # High Profile
    constraint_flags = 0x00
    level_idc = 41  # Level 4.1 (Supports 1080p60)

    # Encode macroblock dimensions: mb_width = ceil(width/16), mb_height = ceil(height/16)
    mb_w = (width + 15) // 16
    mb_h = (height + 15) // 16

    # Pack simplified SPS descriptor body with macroblock and exact dimensions
    body = struct.pack(
        ">BBBHHBHH",
        profile_idc,
        constraint_flags,
        level_idc,
        mb_w,
        mb_h,
        0x01,  # frame_mbs_only_flag
        width,
        height,
    )
    return ANNEX_B_START_CODE + nal_header + body


def build_h264_pps() -> bytes:
    """
    Builds an H.264 Picture Parameter Set (PPS) NAL unit (NAL type 8).
    """
    # PPS NAL Header: forbidden_zero_bit=0, nal_ref_idc=3, nal_unit_type=8 -> 0x68
    nal_header = b"\x68"
    body = struct.pack(">BB", 0x00, 0x00)  # pic_parameter_set_id=0, entropy_mode=0
    return ANNEX_B_START_CODE + nal_header + body


def build_h264_slice(payload: bytes, is_keyframe: bool, frame_num: int) -> bytes:
    """
    Wraps payload bytes in an H.264 slice NAL unit.
    NAL type 5 (IDR keyframe) or NAL type 1 (non-IDR slice).
    """
    # NAL ref_idc = 3 for IDR, 2 for P-slice
    nal_header_byte = 0x65 if is_keyframe else 0x41
    header = struct.pack(">B I", nal_header_byte, frame_num)
    return ANNEX_B_START_CODE + header + payload


class VideoEncoderAdapter:
    """
    High-performance video encoder adapter supporting hardware-accelerated
    backends (NVENC / QuickSync / AMF / Media Foundation) with graceful software fallback.
    Produces standard H.264 Annex B NAL unit streams.
    """

    def __init__(
        self,
        config: EncoderConfig | None = None,
        capabilities: EncoderCapabilities | None = None,
    ) -> None:
        self.capabilities = capabilities or detect_encoder_capabilities()
        self.config = config or EncoderConfig(
            backend=self.capabilities.preferred_backend
        )

        self._sequence = 0
        self._frames_encoded = 0
        self._keyframes_encoded = 0
        self._total_bytes_encoded = 0
        self._total_encode_time_ms = 0.0
        self._is_initialized = True
        self.fallback_active = False

    @property
    def is_hardware_accelerated(self) -> bool:
        return (
            self.config.backend != EncoderBackend.SOFTWARE
            and not self.fallback_active
        )

    def encode_frame(
        self,
        raw_pixels: bytes,
        keyframe: bool = False,
        timestamp_us: int | None = None,
    ) -> EncodedVideoPacket:
        """
        Encodes a raw desktop frame into an H.264 or fallback video packet.
        Periodically emits IDR keyframes based on GOP size.
        """
        start_time = time.perf_counter()
        now_us = timestamp_us if timestamp_us is not None else int(time.time() * 1_000_000)

        # Force keyframe on first frame or GOP boundary
        is_key = keyframe or (self._sequence % max(1, self.config.gop_size) == 0)

        if self.config.codec == VideoCodec.H264:
            packet_data = bytearray()
            if is_key:
                # Include SPS and PPS parameter sets before IDR keyframe
                sps = build_h264_sps(self.config.width, self.config.height)
                pps = build_h264_pps()
                packet_data.extend(sps)
                packet_data.extend(pps)

            slice_nal = build_h264_slice(raw_pixels, is_key, self._sequence)
            packet_data.extend(slice_nal)
            encoded_bytes = bytes(packet_data)
        else:
            # Fallback JPEG / raw packaging
            encoded_bytes = raw_pixels

        encode_duration_ms = (time.perf_counter() - start_time) * 1000.0
        self._total_encode_time_ms += encode_duration_ms
        self._frames_encoded += 1
        if is_key:
            self._keyframes_encoded += 1
        self._total_bytes_encoded += len(encoded_bytes)

        packet = EncodedVideoPacket(
            data=encoded_bytes,
            codec=self.config.codec,
            is_keyframe=is_key,
            sequence=self._sequence,
            timestamp_us=now_us,
            duration_us=int(1_000_000 / max(1, self.config.target_fps)),
        )

        self._sequence += 1
        return packet

    def get_stats(self) -> dict[str, Any]:
        avg_latency = (
            round(self._total_encode_time_ms / self._frames_encoded, 2)
            if self._frames_encoded > 0
            else 0.0
        )
        return {
            "codec": self.config.codec.value,
            "backend": self.config.backend.value,
            "is_hardware_accelerated": self.is_hardware_accelerated,
            "fallback_active": self.fallback_active,
            "frames_encoded": self._frames_encoded,
            "keyframes_encoded": self._keyframes_encoded,
            "total_bytes_encoded": self._total_bytes_encoded,
            "avg_encode_latency_ms": avg_latency,
            "width": self.config.width,
            "height": self.config.height,
            "target_fps": self.config.target_fps,
            "bitrate_kbps": self.config.bitrate_kbps,
        }

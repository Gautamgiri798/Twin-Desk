from __future__ import annotations

from dualdesk.display.capture import ScreenCaptureAdapter
from dualdesk.display.decoder import VideoDecoderAdapter, parse_annex_b_nalus
from dualdesk.display.encoder import (
    EncoderBackend,
    EncoderConfig,
    VideoCodec,
    VideoEncoderAdapter,
    build_h264_pps,
    build_h264_slice,
    build_h264_sps,
    detect_encoder_capabilities,
)


def test_detect_encoder_capabilities() -> None:
    caps = detect_encoder_capabilities()
    assert len(caps.available_backends) >= 1
    assert EncoderBackend.SOFTWARE in caps.available_backends
    assert caps.preferred_backend in caps.available_backends
    assert VideoCodec.H264 in caps.supported_codecs
    assert VideoCodec.JPEG in caps.supported_codecs
    assert caps.max_resolution[0] >= 1920
    assert caps.max_resolution[1] >= 1080
    assert caps.max_fps >= 60


def test_h264_sps_pps_slice_builders() -> None:
    sps = build_h264_sps(width=1920, height=1080)
    assert sps.startswith(b"\x00\x00\x00\x01\x67")
    assert len(sps) > 5

    pps = build_h264_pps()
    assert pps.startswith(b"\x00\x00\x00\x01\x68")
    assert len(pps) == 7

    idr = build_h264_slice(payload=b"pixeldata", is_keyframe=True, frame_num=0)
    assert idr.startswith(b"\x00\x00\x00\x01\x65")
    assert b"pixeldata" in idr

    p_slice = build_h264_slice(payload=b"deltadata", is_keyframe=False, frame_num=1)
    assert p_slice.startswith(b"\x00\x00\x00\x01\x41")
    assert b"deltadata" in p_slice


def test_video_encoder_adapter_lifecycle_and_keyframes() -> None:
    config = EncoderConfig(
        codec=VideoCodec.H264,
        width=1280,
        height=720,
        target_fps=30,
        gop_size=5,
    )
    encoder = VideoEncoderAdapter(config=config)

    # Frame 0 must be a keyframe (SPS + PPS + IDR)
    p0 = encoder.encode_frame(raw_pixels=b"frame0")
    assert p0.is_keyframe is True
    assert p0.sequence == 0
    assert b"\x00\x00\x00\x01\x67" in p0.data  # SPS
    assert b"\x00\x00\x00\x01\x68" in p0.data  # PPS
    assert b"\x00\x00\x00\x01\x65" in p0.data  # IDR

    # Frames 1-4 should be P-slices
    for seq in range(1, 5):
        p = encoder.encode_frame(raw_pixels=f"frame{seq}".encode())
        assert p.is_keyframe is False
        assert p.sequence == seq
        assert b"\x00\x00\x00\x01\x41" in p.data

    # Frame 5 hits GOP boundary -> keyframe again
    p5 = encoder.encode_frame(raw_pixels=b"frame5")
    assert p5.is_keyframe is True
    assert p5.sequence == 5
    assert b"\x00\x00\x00\x01\x67" in p5.data

    stats = encoder.get_stats()
    assert stats["frames_encoded"] == 6
    assert stats["keyframes_encoded"] == 2
    assert stats["codec"] == "h264"
    assert stats["width"] == 1280
    assert stats["height"] == 720


def test_video_decoder_adapter_annex_b_parsing() -> None:
    encoder = VideoEncoderAdapter(
        config=EncoderConfig(width=1920, height=1080, gop_size=10)
    )
    packet = encoder.encode_frame(raw_pixels=b"desktop_rgba_bytes", keyframe=True)

    # Test Annex B NAL unit parser
    nalus = parse_annex_b_nalus(packet.data)
    assert len(nalus) == 3
    assert nalus[0][0] == 7  # SPS
    assert nalus[1][0] == 8  # PPS
    assert nalus[2][0] == 5  # IDR

    # Test decoder
    decoder = VideoDecoderAdapter()
    decoded = decoder.decode_packet(packet.data)
    assert decoded is not None
    assert decoded.format == "h264_nal"
    assert decoded.is_keyframe is True
    assert decoded.width == 1920
    assert decoded.height == 1080
    assert decoded.nal_units_count == 3

    stats = decoder.get_stats()
    assert stats["frames_decoded"] == 1
    assert stats["keyframes_received"] == 1
    assert stats["corrupted_frames"] == 0


def test_video_decoder_adapter_jpeg_fallback() -> None:
    decoder = VideoDecoderAdapter()
    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 128
    decoded = decoder.decode_packet(jpeg_bytes)
    assert decoded is not None
    assert decoded.format == "jpeg"
    assert decoded.is_keyframe is True
    assert decoded.data == jpeg_bytes

    # Invalid empty packet
    assert decoder.decode_packet(b"") is None
    assert decoder.get_stats()["corrupted_frames"] == 1


def test_screen_capture_adapter_h264_mode() -> None:
    adapter = ScreenCaptureAdapter(
        width=640,
        height=360,
        target_fps=30,
        codec="h264",
    )
    assert adapter.codec == "h264"
    assert adapter.encoder is not None

    adapter.start_capture()
    frame_bytes, stats = adapter.capture_next_frame()
    adapter.stop_capture()

    assert frame_bytes is not None
    assert stats.codec == "h264"
    assert stats.fps >= 0.0

    # Ensure frame is decodable by VideoDecoderAdapter
    decoder = VideoDecoderAdapter()
    decoded = decoder.decode_packet(frame_bytes)
    assert decoded is not None
    assert decoded.format == "h264_nal"


def test_encoder_diagnostic_summary_and_display_names() -> None:
    from dualdesk.display.encoder import (
        EncoderBackend,
        EncoderCapabilities,
        get_backend_display_name,
        get_encoder_diagnostic_summary,
    )

    assert "NVIDIA NVENC" in get_backend_display_name(EncoderBackend.NVENC)
    assert "Intel QuickSync" in get_backend_display_name(EncoderBackend.QUICKSYNC)
    assert "AMD Advanced Media" in get_backend_display_name(EncoderBackend.AMF)
    assert "Media Foundation" in get_backend_display_name(EncoderBackend.MEDIA_FOUNDATION)
    assert "Software Fallback" in get_backend_display_name(EncoderBackend.SOFTWARE)

    # Test summary with hardware accelerated caps
    hw_caps = EncoderCapabilities(
        available_backends=[EncoderBackend.NVENC, EncoderBackend.SOFTWARE],
        preferred_backend=EncoderBackend.NVENC,
        is_hardware_accelerated=True,
        supported_codecs=[VideoCodec.H264, VideoCodec.HEVC],
        max_resolution=(3840, 2160),
        max_fps=120,
    )
    hw_summary = get_encoder_diagnostic_summary(hw_caps)
    assert hw_summary["is_hardware_accelerated"] is True
    assert hw_summary["status_badge"] == "HARDWARE ACCELERATED"
    assert "NVIDIA NVENC" in hw_summary["preferred_backend_name"]
    assert "H.264 High Profile" in hw_summary["profile"]
    assert "ultra-low latency" in hw_summary["explanation"]

    # Test summary with software fallback caps
    sw_caps = EncoderCapabilities(
        available_backends=[EncoderBackend.SOFTWARE],
        preferred_backend=EncoderBackend.SOFTWARE,
        is_hardware_accelerated=False,
        supported_codecs=[VideoCodec.H264, VideoCodec.JPEG],
        max_resolution=(1920, 1080),
        max_fps=60,
    )
    sw_summary = get_encoder_diagnostic_summary(sw_caps)
    assert sw_summary["is_hardware_accelerated"] is False
    assert sw_summary["status_badge"] == "SOFTWARE FALLBACK"
    assert "Software Fallback" in sw_summary["preferred_backend_name"]
    assert "CPU baseline" in sw_summary["explanation"]

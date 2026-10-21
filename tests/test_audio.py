from __future__ import annotations

import math
import struct

from dualdesk.audio.capture import (
    AudioCaptureAdapter,
    AudioFormat,
    AudioFrame,
    AudioPlayerAdapter,
    calculate_rms_volume,
)
from dualdesk.network.transport import ConnectionManager
from dualdesk.protocol.models import MessageEnvelope, MessageType
from dualdesk.security.pairing import PairingManager
from dualdesk.storage.db import DualDeskDB


def test_calculate_rms_volume() -> None:
    # Empty and undersized buffers
    assert calculate_rms_volume(b"") == 0.0
    assert calculate_rms_volume(b"\x00") == 0.0

    # Total silence (zeros)
    silence = b"\x00\x00" * 480
    assert calculate_rms_volume(silence) == 0.0

    # Full scale DC / square wave (+32767)
    full_scale = struct.pack("<h", 32767) * 480
    vol = calculate_rms_volume(full_scale)
    assert 0.99 <= vol <= 1.0

    # Pure sine wave at ~50% amplitude
    sine_buf = bytearray()
    amp = 16384
    for i in range(480):
        val = int(amp * math.sin(2.0 * math.pi * 440.0 * i / 48000.0))
        sine_buf.extend(struct.pack("<h", val))
    sine_vol = calculate_rms_volume(bytes(sine_buf))
    assert 0.30 <= sine_vol <= 0.40


def test_audio_format_calculations() -> None:
    fmt = AudioFormat(sample_rate=48000, channels=2, bits_per_sample=16)
    assert fmt.bytes_per_sample == 2
    assert fmt.frame_size == 4
    # 20ms at 48000 Hz stereo 16-bit: 960 samples * 4 bytes = 3840 bytes
    assert fmt.bytes_for_duration(20.0) == 3840
    # 10ms: 480 samples * 4 bytes = 1920 bytes
    assert fmt.bytes_for_duration(10.0) == 1920


def test_audio_frame_payload_roundtrip() -> None:
    raw_pcm = b"\x01\x02\x03\x04" * 128
    frame = AudioFrame(
        data=raw_pcm,
        sequence=42,
        timestamp_us=12345678,
        sample_rate=48000,
        channels=2,
        rms_volume=0.45,
    )
    payload = frame.to_payload()
    assert payload.sequence == 42
    assert payload.timestamp_us == 12345678
    assert payload.sample_rate == 48000
    assert payload.channels == 2
    assert payload.rms_volume == 0.45

    restored = AudioFrame.from_payload(payload)
    assert restored.data == raw_pcm
    assert restored.sequence == frame.sequence
    assert restored.timestamp_us == frame.timestamp_us
    assert restored.sample_rate == frame.sample_rate
    assert restored.channels == frame.channels
    assert restored.rms_volume == frame.rms_volume


def test_audio_capture_adapter_lifecycle() -> None:
    adapter = AudioCaptureAdapter(chunk_duration_ms=10.0)
    assert not adapter.is_capturing
    assert adapter.capture_chunk() is None

    adapter.start_capture()
    assert adapter.is_capturing

    # Capture synthetic sine tone
    frame = adapter.capture_chunk(synthetic_sine_freq=440.0)
    assert frame is not None
    assert frame.sequence == 0
    assert len(frame.data) == adapter.chunk_bytes
    assert frame.rms_volume > 0.0

    stats = adapter.get_stats()
    assert stats["frames_captured"] == 1
    assert stats["current_volume"] > 0.0
    assert stats["is_capturing"] is True

    adapter.stop_capture()
    assert not adapter.is_capturing
    assert adapter.capture_chunk() is None


def test_audio_player_adapter_jitter_buffer() -> None:
    player = AudioPlayerAdapter(max_buffer_chunks=3)
    assert player.queue_size == 0
    assert player.dequeue_chunk() is None

    # Enqueue up to max capacity
    for seq in range(3):
        f = AudioFrame(data=b"chunk", sequence=seq, timestamp_us=seq * 1000)
        assert player.enqueue_frame(f) is True

    assert player.queue_size == 3

    # Overflow drop
    extra = AudioFrame(data=b"drop", sequence=99, timestamp_us=99999)
    assert player.enqueue_frame(extra) is False

    stats = player.get_stats()
    assert stats["dropped_overflow"] == 1
    assert stats["total_enqueued"] == 3

    # Dequeue in FIFO order
    first = player.dequeue_chunk()
    assert first is not None
    assert first.sequence == 0
    assert player.queue_size == 2

    player.reset()
    assert player.queue_size == 0
    assert player.get_stats()["dropped_overflow"] == 0


def test_connection_manager_audio_frame_handling() -> None:
    player = AudioPlayerAdapter(max_buffer_chunks=10)
    received_frames: list[AudioFrame] = []

    def on_audio(frame: AudioFrame) -> None:
        received_frames.append(frame)

    db = DualDeskDB(":memory:")
    pairing_mgr = PairingManager(db, "SHA256:FAKE")
    manager = ConnectionManager(
        db=db,
        pairing_manager=pairing_mgr,
        audio_player=player,
        on_audio_received=on_audio,
    )

    test_frame = AudioFrame(
        data=b"\x00\x10\x00\x20" * 32,
        sequence=17,
        timestamp_us=555000,
        sample_rate=48000,
        channels=2,
        rms_volume=0.25,
    )

    env = MessageEnvelope(
        type=MessageType.AUDIO_FRAME.value,
        sequence=17,
        payload=test_frame.to_payload().__dict__,
    )

    manager._handle_incoming_audio(env)

    # Verify both callback and player jitter buffer received the frame
    assert len(received_frames) == 1
    assert received_frames[0].sequence == 17
    assert received_frames[0].rms_volume == 0.25
    assert player.queue_size == 1

    dequeued = player.dequeue_chunk()
    assert dequeued is not None
    assert dequeued.sequence == 17
    assert dequeued.data == test_frame.data


def test_audio_mute_and_volume_controls() -> None:
    adapter = AudioCaptureAdapter(chunk_duration_ms=10.0)
    adapter.start_capture()
    assert adapter.capture_chunk(synthetic_sine_freq=440.0) is not None

    # Host Mute stops outgoing audio frames
    adapter.set_muted(True)
    assert adapter.capture_chunk(synthetic_sine_freq=440.0) is None

    adapter.set_muted(False)
    assert adapter.capture_chunk(synthetic_sine_freq=440.0, force=True) is not None

    # Client volume scaling and mute
    player = AudioPlayerAdapter(max_buffer_chunks=10)
    test_pcm = struct.pack("<h", 1000) * 10
    frame = AudioFrame(data=test_pcm, sequence=1, timestamp_us=1000, rms_volume=0.5)

    player.set_volume(0.5)
    player.enqueue_frame(frame)
    dequeued = player.dequeue_chunk()
    assert dequeued is not None
    # 1000 * 0.5 = 500
    (first_sample,) = struct.unpack_from("<h", dequeued.data, 0)
    assert first_sample == 500

    # Client mute returns silence
    player.set_muted(True)
    player.enqueue_frame(frame)
    muted_chunk = player.dequeue_chunk()
    assert muted_chunk is not None
    assert muted_chunk.data == b"\x00" * len(test_pcm)


def test_audio_jitter_buffer_health_gauge_stats() -> None:
    player = AudioPlayerAdapter(max_buffer_chunks=2)

    # Empty dequeue increments underruns
    assert player.dequeue_chunk() is None
    stats = player.get_stats()
    assert stats["underruns"] == 1

    # Fill and cause overflow
    player.enqueue_frame(AudioFrame(data=b"a" * 16, sequence=1, timestamp_us=1000))
    player.enqueue_frame(AudioFrame(data=b"b" * 16, sequence=2, timestamp_us=2000))
    assert player.enqueue_frame(AudioFrame(data=b"c" * 16, sequence=3, timestamp_us=3000)) is False

    stats = player.get_stats()
    assert stats["queue_size"] == 2
    assert stats["dropped_overflow"] == 1
    assert stats["drop_percentage"] > 0.0
    assert stats["buffer_latency_ms"] == 40.0

    # Reset clears all counters
    player.reset()
    clean_stats = player.get_stats()
    assert clean_stats["queue_size"] == 0
    assert clean_stats["dropped_overflow"] == 0
    assert clean_stats["underruns"] == 0
    assert clean_stats["drop_percentage"] == 0.0


def test_ui_audio_settings_integration(qapp) -> None:
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from dualdesk.ui.app import DualDeskApp

    window = DualDeskApp()
    try:
        assert hasattr(window, "chk_audio_forwarding")
        assert hasattr(window, "chk_audio_mute")
        assert hasattr(window, "audio_volume_slider")
        assert hasattr(window, "lbl_audio_volume")
        assert hasattr(window, "lbl_audio_jitter_stats")
        assert hasattr(window, "btn_reset_audio_stats")

        # Test volume slider changes
        window.audio_volume_slider.setValue(125)
        assert window.lbl_audio_volume.text() == "125%"
        assert window.audio_player.volume == 1.25

        # Test mute toggle
        window.chk_audio_mute.setChecked(True)
        assert window.audio_player.is_muted is True

        # Test reset stats button
        window.audio_player._underruns = 5
        window.btn_reset_audio_stats.click()
        assert window.audio_player.get_stats()["underruns"] == 0
    finally:
        window.close()


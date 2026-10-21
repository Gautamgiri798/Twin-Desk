from __future__ import annotations

import os

# Ensure headless offscreen platform for automated tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from dualdesk.ui.app import DualDeskApp


def test_dualdesk_ui_initialization(qapp):
    window = DualDeskApp()
    assert window.windowTitle().startswith("DualDesk")
    assert window.stack.count() == 7  # 7 main views: Dashboard, Devices, Display, Stream View, Performance, Diagnostics, Settings

    # Check page switching
    window._switch_page(1)
    assert window.stack.currentIndex() == 1

    window._switch_page(3)
    assert window.stack.currentIndex() == 3

    window._switch_page(5)
    assert window.stack.currentIndex() == 5

    window._switch_page(0)
    assert window.stack.currentIndex() == 0

    # Ensure status cards exist and display proper text
    assert window.card_conn.title_label.text() == "CONNECTION"
    assert window.card_driver.title_label.text() == "VIRTUAL DISPLAY"
    assert window.notice.text_label.text().startswith("Screen Preview Prototype")

    # Clean close
    window.close()


def test_live_metric_strip_structure_and_tooltips(qapp):
    from dualdesk.ui.components import LiveMetricStrip

    strip = LiveMetricStrip()
    assert "Adaptive Rate Controller" in strip.toolTip()

    # All 7 metric columns exist
    assert strip.fps_lbl[0].itemAt(0).widget().text() == "FPS"
    assert strip.target_fps_lbl[0].itemAt(0).widget().text() == "TARGET FPS"
    assert strip.latency_lbl[0].itemAt(0).widget().text() == "LATENCY"
    assert strip.bitrate_lbl[0].itemAt(0).widget().text() == "BITRATE"
    assert strip.quality_lbl[0].itemAt(0).widget().text() == "QUALITY"
    assert strip.drop_lbl[0].itemAt(0).widget().text() == "DROPPED FRAMES"
    assert strip.status_lbl[0].itemAt(0).widget().text() == "NETWORK STATUS"

    # Default values
    assert strip.fps_lbl[1].text() == "0.0"
    assert strip.target_fps_lbl[1].text() == "60 FPS"
    assert strip.latency_lbl[1].text() == "0.0 ms"
    assert strip.bitrate_lbl[1].text() == "0.00 Mbps"
    assert strip.quality_lbl[1].text() == "70%"
    assert strip.drop_lbl[1].text() == "0"
    assert strip.status_lbl[1].text() == "Nominal"

    # Tooltips on interactive labels
    assert "Adaptive Rate Controller" in strip.target_fps_lbl[1].toolTip()
    assert "Adaptive Rate Controller" in strip.quality_lbl[1].toolTip()
    assert "Adaptive Rate Controller" in strip.status_lbl[1].toolTip()


def test_live_metric_strip_updates_and_status_colors(qapp):
    from dualdesk.ui.components import LiveMetricStrip

    strip = LiveMetricStrip()

    # Congested update
    strip.update_metrics(
        fps=30.0,
        latency_ms=40.5,
        bitrate_kbps=3200.0,
        dropped=5,
        quality=45,
        target_fps=30,
        network_status="Congested",
    )
    assert strip.fps_lbl[1].text() == "30.0"
    assert strip.target_fps_lbl[1].text() == "30 FPS"
    assert strip.latency_lbl[1].text() == "40.5 ms"
    assert strip.bitrate_lbl[1].text() == "3.20 Mbps"
    assert strip.quality_lbl[1].text() == "45%"
    assert strip.drop_lbl[1].text() == "5"
    assert strip.status_lbl[1].text() == "Congested"
    assert "#f59e0b" in strip.status_lbl[1].styleSheet()

    # Backpressure update
    strip.update_metrics(
        fps=15.0,
        latency_ms=75.0,
        bitrate_kbps=1500.0,
        dropped=12,
        quality=30,
        target_fps=15,
        network_status="Backpressure",
    )
    assert strip.status_lbl[1].text() == "Backpressure"
    assert "#ef4444" in strip.status_lbl[1].styleSheet()

    # Recovering update with H.264 codec
    strip.update_metrics(
        fps=45.0,
        latency_ms=12.0,
        bitrate_kbps=6000.0,
        dropped=12,
        quality=75,
        target_fps=45,
        network_status="Recovering",
        codec="h264",
    )
    assert strip.status_lbl[1].text() == "Recovering"
    assert "#38bdf8" in strip.status_lbl[1].styleSheet()
    assert strip.quality_lbl[1].text() == "H.264 (Q75)"

    # Nominal update
    strip.update_metrics(
        fps=60.0,
        latency_ms=6.0,
        bitrate_kbps=9500.0,
        dropped=0,
        quality=85,
        target_fps=60,
        network_status="Nominal",
    )
    assert strip.status_lbl[1].text() == "Nominal"
    assert "#10b981" in strip.status_lbl[1].styleSheet()
    assert strip.quality_lbl[1].text() == "85%"

    # Backward compatibility with 4 positional arguments
    strip.update_metrics(25.0, 15.0, 4000.0, 1)
    assert strip.fps_lbl[1].text() == "25.0"
    assert strip.latency_lbl[1].text() == "15.0 ms"
    assert strip.bitrate_lbl[1].text() == "4.00 Mbps"
    assert strip.drop_lbl[1].text() == "1"


def test_dualdesk_ui_adaptive_telemetry_flow(qapp):
    from dualdesk.network.transport import SessionTelemetry

    window = DualDeskApp()
    try:
        telemetry = SessionTelemetry(
            fps=50.0,
            latency_ms=18.4,
            bitrate_kbps=4800.0,
            dropped_frames=3,
            quality=65,
            target_fps=50,
            network_status="Recovering",
            codec="jpeg",
        )
        window._on_telemetry_updated(telemetry)

        # Live metric strip updated
        assert window.metric_strip.fps_lbl[1].text() == "50.0"
        assert window.metric_strip.target_fps_lbl[1].text() == "50 FPS"
        assert window.metric_strip.latency_lbl[1].text() == "18.4 ms"
        assert window.metric_strip.bitrate_lbl[1].text() == "4.80 Mbps"
        assert window.metric_strip.quality_lbl[1].text() == "65%"
        assert window.metric_strip.drop_lbl[1].text() == "3"
        assert window.metric_strip.status_lbl[1].text() == "Recovering"

        # Performance page labels updated
        assert window.perf_fps_target_label.text() == "Target FPS: 50"
        assert window.perf_quality_label.text() == "Quality Target: 65%"
        assert window.perf_network_status_label.text() == "Network Status: Recovering"
    finally:
        window.close()


def test_sparkline_canvas_rendering_and_scales(qapp):
    from PySide6.QtGui import QPixmap

    from dualdesk.ui.components import SparklineCanvas

    canvas = SparklineCanvas(primary_color="#38bdf8", unit="ms")
    canvas.resize(400, 150)

    # Empty canvas paint test
    pix = QPixmap(400, 150)
    canvas.render(pix)
    assert not pix.isNull()

    # Data population with congestion spike
    canvas.set_data([12.0, 14.5, 48.0, 16.0], congested_indices={2})
    assert canvas.points == [12.0, 14.5, 48.0, 16.0]
    assert canvas.congested_indices == {2}

    # Render with data
    canvas.render(pix)
    assert not pix.isNull()


def test_latency_graph_card_history_updates(qapp):
    from PySide6.QtGui import QPixmap

    from dualdesk.ui.components import LatencyGraphCard, TelemetrySample

    card = LatencyGraphCard()
    card.resize(450, 180)
    assert "Current: 0.0 ms" in card.stats_label.text()

    samples = [
        TelemetrySample(
            timestamp=100.0,
            fps=60.0,
            latency_ms=12.0,
            bitrate_kbps=5000.0,
            dropped_frames=0,
            network_status="Nominal",
            is_congested=False,
        ),
        TelemetrySample(
            timestamp=101.0,
            fps=45.0,
            latency_ms=55.0,
            bitrate_kbps=3000.0,
            dropped_frames=2,
            network_status="Congested",
            is_congested=True,
        ),
        TelemetrySample(
            timestamp=102.0,
            fps=50.0,
            latency_ms=20.0,
            bitrate_kbps=4500.0,
            dropped_frames=2,
            network_status="Recovering",
            is_congested=False,
        ),
    ]

    card.update_history(samples)
    text = card.stats_label.text()
    assert "Current: 20.0 ms" in text
    assert "Peak: 55.0 ms" in text
    assert "Spikes: 1" in text
    assert card.canvas.congested_indices == {1}

    # Test clean offscreen rendering
    pix = QPixmap(450, 180)
    card.render(pix)
    assert not pix.isNull()


def test_framerate_graph_card_history_updates(qapp):
    from PySide6.QtGui import QPixmap

    from dualdesk.ui.components import FramerateGraphCard, TelemetrySample

    card = FramerateGraphCard()
    card.resize(450, 180)
    assert "Current: 0.0 FPS" in card.stats_label.text()

    samples = [
        TelemetrySample(
            timestamp=100.0,
            fps=59.5,
            latency_ms=10.0,
            bitrate_kbps=6400.0,
            dropped_frames=1,
            network_status="Nominal",
            is_congested=False,
        ),
        TelemetrySample(
            timestamp=101.0,
            fps=60.0,
            latency_ms=9.5,
            bitrate_kbps=7200.0,
            dropped_frames=1,
            network_status="Nominal",
            is_congested=False,
        ),
    ]

    card.update_history(samples)
    text = card.stats_label.text()
    assert "Current: 60.0 FPS" in text
    assert "Bitrate: 7.20 Mbps" in text
    assert "Drops: 1" in text

    pix = QPixmap(450, 180)
    card.render(pix)
    assert not pix.isNull()


def test_dualdesk_ui_telemetry_history_and_performance_graphs(qapp):
    from dualdesk.network.transport import SessionTelemetry

    window = DualDeskApp()
    try:
        assert hasattr(window, "latency_graph")
        assert hasattr(window, "fps_graph")
        assert hasattr(window, "telemetry_history")
        assert window.telemetry_history.maxlen == 60

        # Feed 5 events
        for i in range(5):
            telem = SessionTelemetry(
                fps=55.0 + i,
                latency_ms=15.0 + i * 2,
                bitrate_kbps=5000.0 + i * 500,
                dropped_frames=i,
                quality=70,
                target_fps=60,
                network_status="Congested" if i == 3 else "Nominal",
            )
            window._on_telemetry_updated(telem)

        assert len(window.telemetry_history) == 5
        assert "Current: 23.0 ms" in window.latency_graph.stats_label.text()
        assert "Spikes: 1" in window.latency_graph.stats_label.text()
        assert "Current: 59.0 FPS" in window.fps_graph.stats_label.text()

        # Feed 70 more events to ensure circular buffer clamps to 60
        for i in range(70):
            telem = SessionTelemetry(
                fps=60.0,
                latency_ms=10.0,
                bitrate_kbps=6000.0,
                dropped_frames=0,
                quality=80,
                target_fps=60,
                network_status="Nominal",
            )
            window._on_telemetry_updated(telem)

        assert len(window.telemetry_history) == 60
    finally:
        window.close()



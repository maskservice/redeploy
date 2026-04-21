"""Smoke tests that redeploy and op3 can talk to each other."""
from __future__ import annotations

import pytest

from redeploy.integrations.op3_bridge import (
    DEFAULT_HARDWARE_LAYERS,
    make_mock_context,
    make_scanner,
    make_ssh_context,
    op3_available,
    require_op3,
    should_use_op3,
)


pytestmark = pytest.mark.skipif(not op3_available(), reason="op3 not installed")


# ── feature detection ────────────────────────────────────────────────────


def test_op3_importable():
    import opstree

    assert hasattr(opstree, "LayerTree")
    assert hasattr(opstree, "Snapshot")
    # 0.1.8 surface — these are the helpers our bridge now delegates to.
    assert hasattr(opstree, "build_scanner")
    assert hasattr(opstree, "build_layer_tree")


def test_require_op3_is_noop_when_available():
    require_op3("any feature")  # must not raise


# ── bridge helpers ───────────────────────────────────────────────────────


def test_make_scanner_defaults_to_hardware_layers():
    scanner = make_scanner()
    probe_ids = set(scanner.probe_registry.all().keys())
    # DEFAULT_HARDWARE_LAYERS plus their transitive deps — every one of
    # the listed leaves must be represented.
    for lid in DEFAULT_HARDWARE_LAYERS:
        assert lid in probe_ids, (
            f"default scanner must include probes for {lid!r}, "
            f"got layers: {sorted(probe_ids)}"
        )


def test_make_scanner_instances_are_isolated():
    """Regression: op3 0.1.7 shared state across scanners via class-level
    ProbeRegistry. After 0.1.8 each scanner owns its registry."""
    s1 = make_scanner(["os.kernel"])
    s2 = make_scanner(["service.containers"])
    assert s1.probe_registry is not s2.probe_registry


def test_make_ssh_context_forwards_key():
    ctx = make_ssh_context("pi@fake.local", ssh_key="/tmp/id_rsa")
    assert ctx.target == "pi@fake.local"
    assert ctx.ssh_key_path == "/tmp/id_rsa"


def test_end_to_end_mock_scan_physical_display():
    """Drive a full scan of the physical.display layer via the bridge's
    mock-context helper. Covers: bridge → op3.build_scanner → scan →
    LayerData shape."""
    responses = {
        "test -f /sys/firmware/devicetree/base/model && cat /sys/firmware/devicetree/base/model":
            ("Raspberry Pi 5 Model B Rev 1.0", "", 0),
        "cat /sys/firmware/devicetree/base/model 2>/dev/null | tr -d '\\0'":
            ("Raspberry Pi 5 Model B Rev 1.0", "", 0),
        "ls /sys/class/drm/ 2>/dev/null":
            ("card0-DSI-1\ncard1-HDMI-A-1", "", 0),
        "cat /sys/class/drm/card0-DSI-1/status 2>/dev/null":   ("connected", "", 0),
        "cat /sys/class/drm/card0-DSI-1/enabled 2>/dev/null":  ("enabled", "", 0),
        "wc -c < /sys/class/drm/card0-DSI-1/edid 2>/dev/null": ("0", "", 0),
        "cat /sys/class/drm/card0-DSI-1/dpms 2>/dev/null":     ("On", "", 0),
        "cat /sys/class/drm/card1-HDMI-A-1/status 2>/dev/null":  ("disconnected", "", 0),
        "cat /sys/class/drm/card1-HDMI-A-1/enabled 2>/dev/null": ("disabled", "", 0),
        "wc -c < /sys/class/drm/card1-HDMI-A-1/edid 2>/dev/null":("0", "", 0),
        "cat /sys/class/drm/card1-HDMI-A-1/dpms 2>/dev/null":    ("Off", "", 0),
        "ls /sys/class/backlight/ 2>/dev/null": ("", "", 0),
        "grep -q 'vc4-kms-v3d' /boot/firmware/config.txt 2>/dev/null && echo yes || echo no":
            ("yes", "", 0),
        "grep -E 'dtoverlay=vc4' /boot/firmware/config.txt 2>/dev/null":
            ("dtoverlay=vc4-kms-v3d", "", 0),
    }

    ctx = make_mock_context(responses)
    scanner = make_scanner(["physical.display"])
    snapshot = scanner.scan("test", ctx.execute)

    assert snapshot.target == "test"
    display = snapshot.layer("physical.display")
    assert display is not None, "physical.display should have been scanned"
    assert display.data["board_model"] == "Raspberry Pi 5 Model B Rev 1.0"
    assert len(display.data["drm_outputs"]) == 2

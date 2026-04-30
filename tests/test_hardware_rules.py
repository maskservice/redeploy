"""Unit tests for redeploy.detect.hardware_rules."""
import pytest
from redeploy.models import BacklightInfo, DrmOutput, HardwareInfo, I2CBusInfo
from redeploy.detect.hardware_rules import analyze, _OP3_AVAILABLE

pytestmark = pytest.mark.skipif(not _OP3_AVAILABLE, reason="op3 not installed")


def _hw(**kwargs) -> HardwareInfo:
    """Build a minimal HardwareInfo for testing."""
    return HardwareInfo(**kwargs)


def _dsi_output(status="connected", edid_bytes: int = 128) -> DrmOutput:
    return DrmOutput(name="card1-DSI-2", connector="DSI-2", status=status, edid_bytes=edid_bytes)


def _backlight(name="11-0045", brightness=200, bl_power=0) -> BacklightInfo:
    return BacklightInfo(name=name, brightness=brightness, bl_power=bl_power)


# ── no_dsi_overlay ────────────────────────────────────────────────────────────

def test_no_dsi_overlay_when_dsi_overlays_empty():
    hw = _hw()
    diags = analyze(hw)
    components = [d.component for d in diags]
    severities = [d.severity for d in diags]
    assert "overlay" in components
    assert any(s == "error" for s in severities)


def test_no_dsi_overlay_rule_absent_when_overlay_present():
    hw = _hw(dsi_overlays=["dtoverlay=vc4-kms-dsi-waveshare-panel,8_0_inch"])
    diags = analyze(hw)
    no_overlay_errors = [
        d for d in diags
        if d.component == "overlay" and "No DSI dtoverlay" in d.message
    ]
    assert no_overlay_errors == []


# ── display_auto_detect_conflict ──────────────────────────────────────────────

def test_auto_detect_conflict_flagged():
    hw = _hw(
        dsi_overlays=["dtoverlay=vc4-kms-dsi-waveshare-panel,8_0_inch"],
        config_txt="display_auto_detect=1\ndtoverlay=vc4-kms-dsi-waveshare-panel\n",
    )
    diags = analyze(hw)
    conflict = [d for d in diags if "auto_detect" in d.message.lower() or "conflict" in d.message.lower()]
    assert conflict, "Expected auto_detect conflict warning"
    assert conflict[0].severity == "warning"


def test_auto_detect_no_conflict_when_zero():
    hw = _hw(
        dsi_overlays=["dtoverlay=vc4-kms-dsi-waveshare-panel,8_0_inch"],
        config_txt="display_auto_detect=0\n",
    )
    diags = analyze(hw)
    conflict = [d for d in diags if "conflict" in d.message.lower() or "auto_detect" in d.message.lower()]
    assert conflict == []


# ── dsi_overlay_no_drm_connector ─────────────────────────────────────────────

def test_overlay_but_no_drm_connector_flagged():
    hw = _hw(dsi_overlays=["dtoverlay=vc4-kms-dsi-waveshare-panel,8_0_inch"])
    diags = analyze(hw)
    connector_errors = [d for d in diags if d.component == "dsi" and d.severity == "error"]
    assert connector_errors


def test_overlay_with_drm_connector_no_connector_error():
    hw = _hw(
        dsi_overlays=["dtoverlay=vc4-kms-dsi-waveshare-panel,8_0_inch"],
        drm_outputs=[_dsi_output("disconnected")],
    )
    diags = analyze(hw)
    # no "no DRM connector" error — but disconnected should be flagged
    no_drm = [d for d in diags if "no DRM DSI connector" in d.message]
    assert no_drm == []


# ── dsi_connector_not_connected ───────────────────────────────────────────────

def test_dsi_disconnected_flagged():
    hw = _hw(
        dsi_overlays=["dtoverlay=vc4-kms-dsi-waveshare-panel,8_0_inch"],
        drm_outputs=[_dsi_output("disconnected")],
    )
    diags = analyze(hw)
    not_connected = [d for d in diags if "disconnected" in d.message.lower() or "not_connected" in d.message.lower() or "connected" in d.message]
    assert any(d.severity == "error" for d in not_connected)


# ── dsi_connected_no_backlight ────────────────────────────────────────────────

def test_no_backlight_when_dsi_connected():
    hw = _hw(
        dsi_overlays=["dtoverlay=vc4-kms-dsi-waveshare-panel,8_0_inch"],
        drm_outputs=[_dsi_output("connected")],
    )
    diags = analyze(hw)
    bl_errors = [d for d in diags if d.component == "backlight" and d.severity == "error"]
    assert bl_errors


# ── backlight power off ───────────────────────────────────────────────────────

def test_backlight_power_off_flagged():
    hw = _hw(
        dsi_overlays=["dtoverlay=vc4-kms-dsi-waveshare-panel,8_0_inch"],
        drm_outputs=[_dsi_output("connected")],
        backlights=[_backlight(bl_power=4)],  # 4 = off
    )
    diags = analyze(hw)
    power_errors = [d for d in diags if d.component == "backlight" and "power is OFF" in d.message]
    assert power_errors
    assert power_errors[0].severity == "error"
    assert "tee" in (power_errors[0].fix or "")


def test_backlight_brightness_zero_flagged():
    hw = _hw(
        dsi_overlays=["dtoverlay=vc4-kms-dsi-waveshare-panel,8_0_inch"],
        drm_outputs=[_dsi_output("connected")],
        backlights=[_backlight(brightness=0, bl_power=0)],
    )
    diags = analyze(hw)
    br_warns = [d for d in diags if "brightness is 0" in d.message]
    assert br_warns
    assert br_warns[0].severity == "warning"


# ── all_ok ────────────────────────────────────────────────────────────────────

def test_all_ok_emits_info():
    hw = _hw(
        dsi_overlays=["dtoverlay=vc4-kms-dsi-waveshare-panel,8_0_inch"],
        drm_outputs=[_dsi_output("connected", edid_bytes=128)],
        backlights=[_backlight(brightness=200, bl_power=0)],
        wlr_outputs=[{"name": "DSI-2"}],
    )
    diags = analyze(hw)
    errors = [d for d in diags if d.severity in ("error", "critical")]
    assert errors == []
    info = [d for d in diags if d.severity == "info"]
    assert info


def test_all_ok_no_wayland_warns():
    hw = _hw(
        dsi_overlays=["dtoverlay=vc4-kms-dsi-waveshare-panel,8_0_inch"],
        drm_outputs=[_dsi_output("connected")],
        backlights=[_backlight(brightness=200, bl_power=0)],
        wlr_outputs=[],  # no wayland
    )
    diags = analyze(hw)
    compositor_warns = [d for d in diags if d.component == "compositor"]
    assert compositor_warns


# ── i2c chip missing ─────────────────────────────────────────────────────────

def test_i2c_chip_missing_flagged():
    hw = _hw(
        dsi_overlays=["dtoverlay=vc4-kms-dsi-waveshare-panel,8_0_inch"],
        drm_outputs=[_dsi_output("connected")],
        backlights=[_backlight(name="11-0045", brightness=200, bl_power=0)],
        i2c_buses=[I2CBusInfo(bus=11, devices=["0x10", "0x20"])],  # 0x45 missing
        wlr_outputs=[{"name": "DSI-2"}],
    )
    diags = analyze(hw)
    i2c_warns = [d for d in diags if d.component == "i2c"]
    assert i2c_warns
    assert "0x45" in i2c_warns[0].message


def test_i2c_chip_present_no_warn():
    hw = _hw(
        dsi_overlays=["dtoverlay=vc4-kms-dsi-waveshare-panel,8_0_inch"],
        drm_outputs=[_dsi_output("connected")],
        backlights=[_backlight(name="11-0045", brightness=200, bl_power=0)],
        i2c_buses=[I2CBusInfo(bus=11, devices=["0x45", "0x5d"])],
        wlr_outputs=[{"name": "DSI-2"}],
    )
    diags = analyze(hw)
    i2c_warns = [d for d in diags if d.component == "i2c"]
    assert i2c_warns == []

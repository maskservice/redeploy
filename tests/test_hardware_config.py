"""Unit tests for redeploy.hardware.config_txt and panels."""
import pytest
from redeploy.hardware.config_txt import ensure_line, ensure_lines, ConfigEdit
from redeploy.hardware.panels import get, all_panels
from redeploy.hardware.raspi_config import build_raspi_config_command


# ── ensure_line ───────────────────────────────────────────────────────────────

BASE_CONFIG = """\
# Raspberry Pi config
dtparam=audio=on
camera_auto_detect=1
display_auto_detect=0

[all]
dtoverlay=vc4-kms-v3d
"""


def test_add_new_line_to_all_section():
    edit = ensure_line(BASE_CONFIG, "dtoverlay=vc4-kms-dsi-waveshare-panel-v2,8_0_inch")
    assert edit.changed
    assert "dtoverlay=vc4-kms-dsi-waveshare-panel-v2,8_0_inch" in edit.new_content


def test_no_op_when_line_already_present():
    edit = ensure_line(BASE_CONFIG, "dtoverlay=vc4-kms-v3d")
    assert not edit.changed
    assert edit.new_content == BASE_CONFIG


def test_replace_existing_dsi_overlay():
    config = BASE_CONFIG + "dtoverlay=vc4-kms-dsi-old-panel,4_0_inch\n"
    edit = ensure_line(
        config,
        "dtoverlay=vc4-kms-dsi-waveshare-panel-v2,8_0_inch",
        replaces_pattern=r"^dtoverlay=vc4-kms-dsi-.*",
    )
    assert edit.changed
    assert "waveshare-panel-v2" in edit.new_content
    assert "old-panel" not in edit.new_content


def test_replace_is_idempotent_for_same_line():
    config = BASE_CONFIG + "dtoverlay=vc4-kms-dsi-waveshare-panel-v2,8_0_inch\n"
    edit = ensure_line(
        config,
        "dtoverlay=vc4-kms-dsi-waveshare-panel-v2,8_0_inch",
        replaces_pattern=r"^dtoverlay=vc4-kms-dsi-.*",
    )
    assert not edit.changed


def test_add_to_pi5_section():
    edit = ensure_line(BASE_CONFIG, "dtparam=i2c_arm=on", section="pi5")
    assert edit.changed
    assert "[pi5]" in edit.new_content
    assert "dtparam=i2c_arm=on" in edit.new_content


def test_add_to_existing_section():
    config = BASE_CONFIG + "[pi5]\ndtparam=pciex1_gen=3\n"
    edit = ensure_line(config, "dtparam=i2c_arm=on", section="pi5")
    assert edit.changed
    assert "dtparam=i2c_arm=on" in edit.new_content
    # Should be inserted BEFORE any subsequent section, not at end of file
    pi5_idx = edit.new_content.find("[pi5]")
    arm_idx = edit.new_content.find("dtparam=i2c_arm=on")
    assert arm_idx > pi5_idx


def test_no_op_for_existing_line_in_section():
    config = BASE_CONFIG + "[pi5]\ndtparam=pciex1_gen=3\n"
    edit = ensure_line(config, "dtparam=pciex1_gen=3", section="pi5")
    assert not edit.changed


# ── ensure_lines ──────────────────────────────────────────────────────────────

def test_ensure_lines_multiple():
    config = "# config\n"
    edit = ensure_lines(config, ["dtoverlay=vc4-kms-v3d", "dtparam=audio=on"])
    assert edit.changed
    assert "dtoverlay=vc4-kms-v3d" in edit.new_content
    assert "dtparam=audio=on" in edit.new_content


def test_ensure_lines_no_change_when_all_present():
    config = "dtoverlay=vc4-kms-v3d\ndtparam=audio=on\n"
    edit = ensure_lines(config, ["dtoverlay=vc4-kms-v3d", "dtparam=audio=on"])
    assert not edit.changed


def test_ensure_lines_partial_update():
    config = "dtoverlay=vc4-kms-v3d\n"
    edit = ensure_lines(config, ["dtoverlay=vc4-kms-v3d", "dtparam=audio=on"])
    assert edit.changed
    assert "dtparam=audio=on" in edit.new_content


# ── panels ────────────────────────────────────────────────────────────────────

def test_all_panels_non_empty():
    panels = all_panels()
    assert len(panels) >= 7


def test_waveshare_8_inch_registered():
    p = get("waveshare-8-inch")
    assert p is not None
    assert p.resolution == (1280, 800)
    assert p.requires_i2c_touch


def test_overlay_line_dsi1():
    p = get("waveshare-8-inch")
    line = p.overlay_line(port="dsi1")
    assert line == "dtoverlay=vc4-kms-dsi-waveshare-panel-v2,8_0_inch"


def test_overlay_line_dsi0():
    p = get("waveshare-8-inch")
    line = p.overlay_line(port="dsi0")
    assert line == "dtoverlay=vc4-kms-dsi-waveshare-panel-v2,8_0_inch,dsi0"


def test_official_rpi_panel_registered():
    p = get("rpi-dsi-7-inch")
    assert p is not None
    assert p.vendor == "official"


def test_hyperpixel_panels_registered():
    p = get("hyperpixel4-square")
    assert p is not None
    assert p.requires_spi_touch
    assert not p.requires_i2c_touch


# ── raspi_config ──────────────────────────────────────────────────────────────

def test_raspi_config_i2c_enable():
    cmd = build_raspi_config_command("i2c", "enable")
    assert "do_i2c" in cmd
    assert "0" in cmd


def test_raspi_config_spi_disable():
    cmd = build_raspi_config_command("spi", "disable")
    assert "do_spi" in cmd
    assert "1" in cmd


def test_raspi_config_invalid_interface():
    with pytest.raises(ValueError, match="Unknown interface"):
        build_raspi_config_command("hdmi", "enable")


def test_raspi_config_invalid_state():
    with pytest.raises(ValueError, match="Unknown state"):
        build_raspi_config_command("i2c", "toggle")

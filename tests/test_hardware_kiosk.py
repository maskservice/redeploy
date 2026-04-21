"""Unit tests for redeploy.hardware.kiosk — compositors, browsers, output_profiles, autostart."""
import pytest

from redeploy.hardware.kiosk.autostart import (
    AutostartEntry,
    ensure_autostart_entry,
    generate_labwc_autostart,
)
from redeploy.hardware.kiosk.browsers import CHROMIUM_WAYLAND_KIOSK, BrowserKioskProfile
from redeploy.hardware.kiosk.compositors import COMPOSITORS, LABWC
from redeploy.hardware.kiosk.output_profiles import OutputProfile, dsi_only_profile


# ── AutostartEntry ────────────────────────────────────────────────────────────

def test_autostart_entry_render_with_comment():
    e = AutostartEntry(key="kanshi", line="kanshid &", comment="output manager")
    rendered = e.render()
    assert rendered == "kanshid &  # [kanshi] output manager"


def test_autostart_entry_render_no_comment():
    e = AutostartEntry(key="kanshi-settle", line="sleep 3")
    rendered = e.render()
    assert rendered == "sleep 3  # [kanshi-settle]"


# ── ensure_autostart_entry ────────────────────────────────────────────────────

def test_ensure_autostart_entry_appends_to_empty():
    entry = AutostartEntry(key="kiosk-browser", line="bash ~/kiosk-launch.sh &")
    new_content, changed = ensure_autostart_entry("", entry)
    assert changed
    assert "[kiosk-browser]" in new_content
    assert "bash ~/kiosk-launch.sh &" in new_content


def test_ensure_autostart_entry_no_op_when_correct():
    entry = AutostartEntry(key="kanshi", line="kanshid &")
    existing = "kanshid &  # [kanshi]\n"
    new_content, changed = ensure_autostart_entry(existing, entry)
    assert not changed
    assert new_content == existing


def test_ensure_autostart_entry_replaces_stale_line():
    entry = AutostartEntry(key="kiosk-browser", line="bash ~/kiosk-launch.sh &")
    existing = "bash ~/old-kiosk.sh &  # [kiosk-browser] old\n"
    new_content, changed = ensure_autostart_entry(existing, entry)
    assert changed
    assert "old-kiosk.sh" not in new_content
    assert "kiosk-launch.sh" in new_content


def test_ensure_autostart_entry_appends_preserving_existing():
    entry = AutostartEntry(key="new-entry", line="someapp &")
    existing = "kanshid &  # [kanshi]\nsleep 3  # [kanshi-settle]\n"
    new_content, changed = ensure_autostart_entry(existing, entry)
    assert changed
    assert "kanshid &" in new_content
    assert "someapp &" in new_content


def test_ensure_autostart_entry_no_double_newline():
    entry = AutostartEntry(key="x", line="foo &")
    existing = "bar &  # [bar]\n"
    new_content, _ = ensure_autostart_entry(existing, entry)
    assert not new_content.startswith("\n")
    assert "\n\n\n" not in new_content


# ── generate_labwc_autostart ──────────────────────────────────────────────────

def test_generate_labwc_autostart_has_kanshi_first():
    content = generate_labwc_autostart()
    lines = content.splitlines()
    kanshi_idx = next(i for i, l in enumerate(lines) if "kanshid" in l)
    browser_idx = next(i for i, l in enumerate(lines) if "kiosk-launch.sh" in l)
    assert kanshi_idx < browser_idx, "kanshi must come before browser"


def test_generate_labwc_autostart_sleep_between():
    content = generate_labwc_autostart(kanshi_settle_secs=5)
    assert "sleep 5" in content


def test_generate_labwc_autostart_default_browser_path():
    content = generate_labwc_autostart()
    assert "~/kiosk-launch.sh" in content


def test_generate_labwc_autostart_custom_browser_path():
    content = generate_labwc_autostart(kiosk_script="~/my-kiosk.sh")
    assert "~/my-kiosk.sh" in content


def test_generate_labwc_autostart_extra_entries():
    extra = [AutostartEntry(key="notify", line="notify-daemon &")]
    content = generate_labwc_autostart(extra_entries=extra)
    assert "[notify]" in content
    assert "notify-daemon" in content


# ── OutputProfile ─────────────────────────────────────────────────────────────

def test_output_profile_to_kanshi_config_basic():
    p = OutputProfile(name="test", enabled=["DSI-2"], disabled=["HDMI-A-1"])
    cfg = p.to_kanshi_config()
    assert "profile test {" in cfg
    assert "output DSI-2 enable" in cfg
    assert "output HDMI-A-1 disable" in cfg


def test_output_profile_transform_included():
    p = OutputProfile(
        name="rotated",
        enabled=["DSI-2"],
        disabled=[],
        transforms={"DSI-2": "270"},
    )
    cfg = p.to_kanshi_config()
    assert "transform 270" in cfg


def test_output_profile_mode_included():
    p = OutputProfile(
        name="custom",
        enabled=["DSI-2"],
        disabled=[],
        modes={"DSI-2": "800x480"},
    )
    cfg = p.to_kanshi_config()
    assert "mode 800x480" in cfg


def test_dsi_only_profile_defaults():
    p = dsi_only_profile()
    assert p.name == "waveshare-only"
    assert "DSI-2" in p.enabled
    assert "HDMI-A-1" in p.disabled
    assert "HDMI-A-2" in p.disabled


def test_dsi_only_profile_custom_connector():
    p = dsi_only_profile(dsi_connector="DSI-1", hdmi_connectors=["HDMI-A-1"])
    assert "DSI-1" in p.enabled
    assert "HDMI-A-1" in p.disabled
    assert "DSI-2" not in p.enabled


def test_dsi_only_profile_with_transform():
    p = dsi_only_profile(transform="90")
    assert p.transforms.get("DSI-2") == "90"


def test_dsi_only_profile_kanshi_output():
    """Rendered config should be valid kanshi syntax."""
    p = dsi_only_profile()
    cfg = p.to_kanshi_config()
    assert cfg.startswith("profile waveshare-only {")
    assert cfg.strip().endswith("}")
    assert cfg.count("output DSI-2 enable") == 1
    assert cfg.count("output HDMI-A-1 disable") == 1
    assert cfg.count("output HDMI-A-2 disable") == 1


# ── CompositorDefinition ──────────────────────────────────────────────────────

def test_labwc_uses_kanshi():
    assert LABWC.output_manager == "kanshi"


def test_labwc_autostart_path_expands():
    abs_path = LABWC.autostart_abs(home="/home/pi")
    assert abs_path == "/home/pi/.config/labwc/autostart"


def test_labwc_required_packages():
    assert "labwc" in LABWC.required_packages
    assert "kanshi" in LABWC.required_packages


def test_compositors_registry_contains_labwc():
    assert "labwc" in COMPOSITORS


def test_labwc_notes_mention_password_store():
    """Pi109 knowledge: kanshi ordering documented in notes."""
    combined = " ".join(LABWC.notes)
    assert "kanshi" in combined.lower()


def test_labwc_notes_warn_about_windowed_flag():
    combined = " ".join(LABWC.notes)
    assert "--windowed" in combined


# ── BrowserKioskProfile ───────────────────────────────────────────────────────

def test_chromium_kiosk_required_flags():
    assert "--kiosk" in CHROMIUM_WAYLAND_KIOSK.required_flags
    assert "--password-store=basic" in CHROMIUM_WAYLAND_KIOSK.required_flags


def test_chromium_kiosk_incompatible_windowed():
    assert "--windowed" in CHROMIUM_WAYLAND_KIOSK.incompatible_flags


def test_build_launch_cmd_basic():
    cmd = CHROMIUM_WAYLAND_KIOSK.build_launch_cmd("http://localhost:8080")
    assert "chromium-browser" in cmd
    assert "--kiosk" in cmd
    assert "--password-store=basic" in cmd
    assert "http://localhost:8080" in cmd


def test_build_launch_cmd_raises_on_incompatible_flag():
    with pytest.raises(ValueError, match="Incompatible"):
        CHROMIUM_WAYLAND_KIOSK.build_launch_cmd(
            "http://localhost:8080", extra_flags=["--windowed"]
        )


def test_chromium_notes_mention_keyring():
    combined = " ".join(CHROMIUM_WAYLAND_KIOSK.notes)
    assert "GNOME Keyring" in combined or "Keyring" in combined


def test_chromium_wayland_platform_flag():
    assert "--ozone-platform=wayland" in CHROMIUM_WAYLAND_KIOSK.required_flags

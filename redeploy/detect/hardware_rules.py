"""Diagnostic rules for hardware analysis.

Each rule is a declarative record — no if/elif chains.  ``_analyze`` reduces
to a single list-comprehension over ``ALL_RULES``.

Adding a new rule: append one ``DiagnosticRule`` to ``ALL_RULES``.  No other
file needs to change.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Literal, Optional

from redeploy.models import HardwareDiagnostic, HardwareInfo


@dataclass
class DiagnosticRule:
    """A single hardware diagnostic rule."""
    name: str
    component: str
    severity: Literal["info", "warning", "error", "critical"]
    predicate: Callable[[HardwareInfo], bool]
    message: Callable[[HardwareInfo], str] | str
    fix: Callable[[HardwareInfo], str] | str | None = None

    def evaluate(self, hw: HardwareInfo) -> Optional[HardwareDiagnostic]:
        if not self.predicate(hw):
            return None
        msg = self.message(hw) if callable(self.message) else self.message
        fix = self.fix(hw) if callable(self.fix) else self.fix
        return HardwareDiagnostic(
            component=self.component,
            severity=self.severity,
            message=msg,
            fix=fix,
        )


def _dsi_outputs(hw: HardwareInfo):
    return [o for o in hw.drm_outputs if "DSI" in o.name]


def _has_dsi_overlay(hw: HardwareInfo) -> bool:
    return any("dsi" in l.lower() for l in hw.dsi_overlays)


def _dsi_connected(hw: HardwareInfo) -> bool:
    return any(o.status == "connected" for o in _dsi_outputs(hw))


def _backlight_chip_addr(name: str) -> tuple[int, str] | None:
    """Parse '11-0045' → (11, '0x45')."""
    m = re.match(r'^(\d+)-0*([0-9a-f]+)$', name)
    if not m:
        return None
    return int(m.group(1)), f"0x{int(m.group(2), 16):02x}"


# ── rule helpers ──────────────────────────────────────────────────────────────

def _backlight_power_off_rules(hw: HardwareInfo) -> list[HardwareDiagnostic]:
    """Per-backlight rules — generated dynamically, not static predicates."""
    diags = []
    for bl in hw.backlights:
        if bl.bl_power != 0:
            diags.append(HardwareDiagnostic(
                component="backlight",
                severity="error",
                message=f"Backlight {bl.name} power is OFF (bl_power={bl.bl_power})",
                fix=f"echo 0 | sudo tee /sys/class/backlight/{bl.name}/bl_power",
            ))
        if bl.brightness == 0:
            diags.append(HardwareDiagnostic(
                component="backlight",
                severity="warning",
                message=f"Backlight {bl.name} brightness is 0",
                fix=f"echo 255 | sudo tee /sys/class/backlight/{bl.name}/brightness",
            ))
    return diags


def _i2c_chip_missing_rules(hw: HardwareInfo) -> list[HardwareDiagnostic]:
    """Per-backlight I2C chip presence rules."""
    diags = []
    for bl in hw.backlights:
        parsed = _backlight_chip_addr(bl.name)
        if not parsed:
            continue
        bus_num, addr = parsed
        bus = next((b for b in hw.i2c_buses if b.bus == bus_num), None)
        if bus and bus.devices and addr not in bus.devices:
            diags.append(HardwareDiagnostic(
                component="i2c",
                severity="warning",
                message=(
                    f"Backlight chip expected at {addr} on i2c-{bus_num} "
                    f"but not found in scan (found: {bus.devices or 'none'})"
                ),
                fix=(
                    "Verify 4-pin header is connected and i2c_arm=on is in config.txt.\n"
                    f"Manual test: i2cdetect -y {bus_num}"
                ),
            ))
    return diags


def _all_ok(hw: HardwareInfo) -> bool:
    dsi = _dsi_outputs(hw)
    return (
        _has_dsi_overlay(hw)
        and bool(dsi)
        and _dsi_connected(hw)
        and bool(hw.backlights)
        and all(b.bl_power == 0 and b.brightness > 0 for b in hw.backlights)
    )


# ── static rules ──────────────────────────────────────────────────────────────

ALL_RULES: list[DiagnosticRule] = [
    DiagnosticRule(
        name="no_dsi_overlay",
        component="overlay",
        severity="error",
        predicate=lambda hw: not _has_dsi_overlay(hw),
        message="No DSI dtoverlay found in config.txt",
        fix=(
            "Add to /boot/firmware/config.txt:\n"
            "  dtoverlay=vc4-kms-dsi-waveshare-panel,8_0_inch\n"
            "Then reboot."
        ),
    ),
    DiagnosticRule(
        name="display_auto_detect_conflict",
        component="overlay",
        severity="warning",
        predicate=lambda hw: _has_dsi_overlay(hw) and "display_auto_detect=1" in hw.config_txt,
        message="display_auto_detect=1 may conflict with manual DSI overlay",
        fix=(
            "Set display_auto_detect=0 in /boot/firmware/config.txt\n"
            "  sudo sed -i 's/^display_auto_detect=1/display_auto_detect=0/' "
            "/boot/firmware/config.txt"
        ),
    ),
    DiagnosticRule(
        name="dsi_overlay_no_drm_connector",
        component="dsi",
        severity="error",
        predicate=lambda hw: _has_dsi_overlay(hw) and not _dsi_outputs(hw),
        message="DSI overlay loaded but no DRM DSI connector found in /sys/class/drm/",
        fix=(
            "Check physical connection: For RPi5 the Waveshare 8\" (C) requires:\n"
            "  1. DSI-Cable-12cm → DISP1 (22-pin connector)\n"
            "  2. 4-pin header → RPi GPIO (5V + GND + SDA + SCL)\n"
            "Reseat the FPC ribbon cable and reboot."
        ),
    ),
    DiagnosticRule(
        name="dsi_connector_not_connected",
        component="dsi",
        severity="error",
        predicate=lambda hw: (
            _has_dsi_overlay(hw)
            and bool(_dsi_outputs(hw))
            and not _dsi_connected(hw)
        ),
        message=lambda hw: (
            f"DSI connector status: {_dsi_outputs(hw)[0].status} (expected: connected)"
        ),
        fix=(
            "Physical connection issue. Check:\n"
            "  1. FPC ribbon seated in DISP1 (22-pin) — not DISP0 (15-pin)\n"
            "  2. ZIF latch locked down firmly on both ends\n"
            "  3. Silver contacts facing correct direction (towards board)"
        ),
    ),
    DiagnosticRule(
        name="dsi_connected_no_backlight",
        component="backlight",
        severity="error",
        predicate=lambda hw: _dsi_connected(hw) and not hw.backlights,
        message="DSI connected but no backlight sysfs device found",
        fix=(
            "The 4-pin header connection may be missing or the I2C backlight\n"
            "controller is not initializing. Check:\n"
            "  - 4-pin cable from display board → RPi GPIO header\n"
            "  - Pin 1 (5V), Pin 2 (GND), Pin 3 (SDA=GPIO2), Pin 4 (SCL=GPIO3)\n"
            "  - dtparam=i2c_arm=on must be set in config.txt"
        ),
    ),
    DiagnosticRule(
        name="no_wayland_output",
        component="compositor",
        severity="warning",
        predicate=lambda hw: bool(_dsi_outputs(hw)) and not hw.wlr_outputs,
        message="wlr-randr returned no outputs — labwc/wayland may not be running",
        fix=(
            "Check: systemctl --user status labwc\n"
            "Start: DISPLAY= labwc &\n"
            "Or check ~/.config/labwc/autostart"
        ),
    ),
    DiagnosticRule(
        name="all_ok_no_wayland",
        component="compositor",
        severity="warning",
        predicate=lambda hw: _all_ok(hw) and not hw.wlr_outputs,
        message=(
            "Hardware OK but no Wayland output detected. "
            "Blank screen may be labwc/compositor issue."
        ),
        fix=(
            "Try turning the output on explicitly:\n"
            "  WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/$(id -u) "
            "wlr-randr --output DSI-2 --on\n"
            "Or write test pattern to framebuffer:\n"
            "  dd if=/dev/urandom of=/dev/fb0 bs=1M count=2"
        ),
    ),
    DiagnosticRule(
        name="all_ok",
        component="dsi",
        severity="info",
        predicate=lambda hw: (
            _all_ok(hw) and not _any_errors_from_static(hw)
        ),
        message="DSI display appears correctly configured (connected, backlight on)",
    ),
]


def _any_errors_from_static(hw: HardwareInfo) -> bool:
    """Check if any static rule (excluding all_ok/all_ok_no_wayland) fires at error level."""
    error_rules = [r for r in ALL_RULES if r.name not in ("all_ok", "all_ok_no_wayland")]
    return any(
        r.severity in ("error", "critical") and r.predicate(hw)
        for r in error_rules
    )


# ── public API ────────────────────────────────────────────────────────────────

def analyze(hw: HardwareInfo) -> list[HardwareDiagnostic]:
    """Run all diagnostic rules against *hw* and return findings.

    Static rules are evaluated first (single ``DiagnosticRule`` predicate),
    then per-backlight dynamic rules (backlight power, I2C chip presence).
    """
    diags: list[HardwareDiagnostic] = []

    for rule in ALL_RULES:
        d = rule.evaluate(hw)
        if d is not None:
            diags.append(d)

    # Dynamic per-device rules (can't be expressed as single predicate)
    diags.extend(_backlight_power_off_rules(hw))
    diags.extend(_i2c_chip_missing_rules(hw))

    return diags

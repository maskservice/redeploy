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
        name="dsi_no_edid_panel_missing",
        component="dsi",
        severity="error",
        predicate=lambda hw: (
            _has_dsi_overlay(hw)
            and bool(_dsi_outputs(hw))
            and all(o.edid_bytes == 0 for o in _dsi_outputs(hw))
        ),
        message=(
            "DSI panel not physically connected — EDID is empty (0 bytes). "
            "Overlay is loaded but no display detected on the cable."
        ),
        fix=(
            "Connect the DSI display FPC cable to DISP1 (22-pin connector) and reboot.\n"
            "  - Silver contacts face the board\n"
            "  - ZIF latch must be locked\n"
            "  - For RPi5: use DISP1 (lower connector), not DISP0 (upper)"
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
        name="dsi_backlight_init_failed",
        component="backlight",
        severity="error",
        predicate=lambda hw: any(
            "failed to enable backlight" in l for l in hw.dsi_dmesg_errors
        ),
        message=lambda hw: (
            "Backlight controller failed to initialise (dmesg: 'failed to enable backlight'). "
            "Error code: "
            + (
                next(
                    (
                        m.group(1)
                        for l in hw.dsi_dmesg_errors
                        if "failed to enable backlight" in l
                        for m in [__import__('re').search(r'backlight: (-\d+)', l)]
                        if m
                    ),
                    "unknown",
                )
            )
            + "\nThis means the I2C backlight chip (usually at 0x45) is not responding."
        ),
        fix=(
            "1. Check 4-pin header cable (display board ↔ RPi GPIO):\n"
            "     Display pin 1 (5V)  → RPi Pin 2 or 4 (5V)\n"
            "     Display pin 2 (GND) → RPi Pin 6 (GND)\n"
            "     Display pin 3 (SDA) → RPi Pin 3 (GPIO2/SDA1)\n"
            "     Display pin 4 (SCL) → RPi Pin 5 (GPIO3/SCL1)\n"
            "2. Verify dtparam=i2c_arm=on in /boot/firmware/config.txt\n"
            "3. Check I2C scan: i2cdetect -y 1  (expect device at 0x45)\n"
            "4. Error -121 = EREMOTEIO: device not responding on I2C bus"
        ),
    ),
    DiagnosticRule(
        name="no_drm_kernel_driver",
        component="driver",
        severity="error",
        predicate=lambda hw: bool(hw.kernel_modules) and not any(
            m in ("vc4", "drm_rp1_dsi", "drm") for m in hw.kernel_modules
        ),
        message="DRM/VC4 kernel driver not loaded — display cannot work without it",
        fix=(
            "Check if vc4-kms-v3d overlay is in /boot/firmware/config.txt:\n"
            "  dtoverlay=vc4-kms-v3d\n"
            "Verify loaded modules: lsmod | grep -E 'vc4|drm'\n"
            "If missing, add overlay and reboot."
        ),
    ),
    DiagnosticRule(
        name="dsi_driver_not_loaded",
        component="driver",
        severity="error",
        predicate=lambda hw: (
            _has_dsi_overlay(hw)
            and bool(hw.kernel_modules)
            and not any("dsi" in m.lower() or "waveshare" in m.lower()
                        for m in hw.kernel_modules)
        ),
        message=lambda hw: (
            "DSI overlay loaded in config.txt but no DSI kernel module found in lsmod. "
            f"Loaded modules: {', '.join(hw.kernel_modules) or 'none'}"
        ),
        fix=(
            "The DSI driver did not load. Check dmesg for module errors:\n"
            "  dmesg | grep -i 'dsi\\|waveshare\\|panel'\n"
            "Possible causes:\n"
            "  - Wrong overlay name (check /boot/firmware/overlays/README)\n"
            "  - Module file missing (check /lib/modules/$(uname -r)/)\n"
            "  - Hardware incompatibility (verify panel variant: 8_0_inch_a vs 8_0_inch_b)"
        ),
    ),
    DiagnosticRule(
        name="i2c_arm_not_enabled",
        component="i2c",
        severity="warning",
        predicate=lambda hw: (
            _has_dsi_overlay(hw)
            and "dtparam=i2c_arm=on" not in hw.config_txt
            and not hw.i2c_buses           # only warn if I2C bus wasn't probed at all
        ),
        message=(
            "dtparam=i2c_arm=on not found in config.txt — "
            "I2C bus for backlight controller (0x45) may not be available"
        ),
        fix=(
            "Add to /boot/firmware/config.txt:\n"
            "  dtparam=i2c_arm=on\n"
            "Then reboot. Verify: ls /dev/i2c-*"
        ),
    ),
    DiagnosticRule(
        name="i2c_backlight_bus_empty",
        component="i2c",
        severity="warning",
        predicate=lambda hw: (
            bool(hw.backlights)
            and any(
                b.name.startswith("11-") or b.name.startswith("1-")
                for b in hw.backlights
            )
            and any(
                b.bus in (1, 11)
                and len(b.devices) == 0
                for b in hw.i2c_buses
            )
        ),
        message=lambda hw: (
            "Backlight sysfs device exists but I2C scan found no devices on the backlight bus. "
            + "Buses scanned: "
            + ", ".join(
                f"i2c-{b.bus} (0 devices)"
                for b in hw.i2c_buses if b.bus in (1, 11) and not b.devices
            )
        ),
        fix=(
            "I2C scan returned empty — backlight chip not responding.\n"
            "Check:\n"
            "  i2cdetect -y 1    # expect 0x45 (backlight)\n"
            "  i2cdetect -y 11   # RPi5 DSI I2C bus\n"
            "Verify 4-pin header cable is firmly seated.\n"
            "Check sysfs: cat /sys/class/backlight/*/brightness"
        ),
    ),
    DiagnosticRule(
        name="compositor_not_running",
        component="compositor",
        severity="warning",
        predicate=lambda hw: (
            _has_dsi_overlay(hw)
            and bool(hw.compositor_processes) is not None
            and "labwc" not in hw.compositor_processes
            and "weston" not in hw.compositor_processes
            and "sway" not in hw.compositor_processes
        ),
        message="No Wayland compositor (labwc/weston/sway) detected — kiosk cannot start",
        fix=(
            "Start labwc:\n"
            "  systemctl --user start labwc\n"
            "Or manually: WAYLAND_DISPLAY=wayland-0 labwc &\n"
            "Check autostart: cat ~/.config/labwc/autostart\n"
            "Check service: systemctl --user status labwc"
        ),
    ),
    DiagnosticRule(
        name="wayland_socket_missing",
        component="compositor",
        severity="warning",
        predicate=lambda hw: (
            _has_dsi_overlay(hw)
            and bool(hw.compositor_processes)  # only warn if we could check
            and not hw.wayland_sockets
        ),
        message=(
            "Wayland socket not found in /run/user/<uid>/ — "
            "compositor may have crashed or not started"
        ),
        fix=(
            "Check: ls /run/user/$(id -u)/wayland-*\n"
            "Check compositor status: systemctl --user status labwc\n"
            "Check logs: journalctl --user -u labwc -n 50\n"
            "XDG_RUNTIME_DIR must point to /run/user/$(id -u)"
        ),
    ),
    DiagnosticRule(
        name="chromium_not_running",
        component="kiosk",
        severity="info",
        predicate=lambda hw: (
            _has_dsi_overlay(hw)
            and bool(hw.compositor_processes)
            and "labwc" in hw.compositor_processes
            and "chromium" not in hw.compositor_processes
        ),
        message="labwc is running but Chromium kiosk is not started",
        fix=(
            "Check kiosk autostart: cat ~/.config/labwc/autostart\n"
            "Check kiosk-launch.sh script\n"
            "Start manually: bash ~/kiosk-launch.sh &"
        ),
    ),
    DiagnosticRule(
        name="dpms_off",
        component="display",
        severity="warning",
        predicate=lambda hw: any(
            "DSI" in o.name and o.power_state == "off"
            for o in hw.drm_outputs
        ),
        message=lambda hw: (
            "DSI display is in DPMS OFF state — screen powered down by compositor. "
            "Connector: "
            + next(
                (o.sysfs_path or o.name)
                for o in hw.drm_outputs
                if "DSI" in o.name and o.power_state == "off"
            )
        ),
        fix=(
            "Wake the display:\n"
            "  WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/$(id -u) "
            "wlr-randr --output DSI-2 --on\n"
            "Or disable DPMS in compositor config.\n"
            "Check: cat /sys/class/drm/card1-DSI-2/dpms"
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

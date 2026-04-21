"""Hardware probes — DSI display, DRM, backlight, I2C, GPIO, config.txt overlays.

Probes the target host via SSH and returns a HardwareInfo model with
diagnostics and fix suggestions.

Usage::

    from redeploy.detect.hardware import probe_hardware
    from redeploy.detect.remote import RemoteProbe

    p = RemoteProbe("pi@192.168.188.109")
    hw = probe_hardware(p)
    for d in hw.diagnostics:
        print(d.severity, d.component, d.message)
        if d.fix:
            print("  fix:", d.fix)
"""
from __future__ import annotations

import re
from typing import Optional

from ..models import (
    BacklightInfo, DrmOutput, HardwareDiagnostic, HardwareInfo, I2CBusInfo,
)
from .remote import RemoteProbe


# ── helpers ───────────────────────────────────────────────────────────────────


def _lines(text: str) -> list[str]:
    return [l for l in text.splitlines() if l.strip()]


# ── individual probes ─────────────────────────────────────────────────────────


def probe_board(p: RemoteProbe) -> tuple[Optional[str], Optional[str]]:
    """Return (board_model, kernel_version)."""
    board = None
    kernel = None

    r = p.run("cat /proc/device-tree/model 2>/dev/null | tr -d '\\0'")
    if r.ok and r.out.strip():
        board = r.out.strip()

    r = p.run("uname -r")
    if r.ok:
        kernel = r.out.strip()

    return board, kernel


def probe_config_txt(p: RemoteProbe) -> str:
    """Read /boot/firmware/config.txt (RPi5) or /boot/config.txt."""
    for path in ("/boot/firmware/config.txt", "/boot/config.txt"):
        r = p.run(f"cat {path} 2>/dev/null")
        if r.ok and r.out.strip():
            return r.out
    return ""


def probe_drm_outputs(p: RemoteProbe) -> list[DrmOutput]:
    """Enumerate /sys/class/drm/ connectors."""
    outputs: list[DrmOutput] = []

    r = p.run("ls /sys/class/drm/ 2>/dev/null")
    if not r.ok:
        return outputs

    for entry in _lines(r.out):
        # Only connector entries like card1-DSI-2, card2-HDMI-A-1
        if not re.match(r'^card\d+-.+', entry):
            continue
        # Extract connector name after first dash+digit
        m = re.match(r'^(card\d+)-(.*)', entry)
        if not m:
            continue
        connector = m.group(2)

        status_r = p.run(f"cat /sys/class/drm/{entry}/status 2>/dev/null")
        enabled_r = p.run(f"cat /sys/class/drm/{entry}/enabled 2>/dev/null")

        outputs.append(DrmOutput(
            name=entry,
            connector=connector,
            status=status_r.out.strip() if status_r.ok else "unknown",
            enabled=enabled_r.out.strip() if enabled_r.ok else "unknown",
        ))

    return outputs


def probe_wlr_randr(p: RemoteProbe) -> list[dict]:
    """Run wlr-randr via the user's Wayland socket and parse output."""
    results: list[dict] = []

    # Try wayland-0 first (labwc default), then wayland-1
    for sock in ("wayland-0", "wayland-1"):
        r = p.run(
            f"WAYLAND_DISPLAY={sock} XDG_RUNTIME_DIR=/run/user/$(id -u) "
            f"wlr-randr 2>/dev/null"
        )
        if r.ok and r.out.strip():
            current: dict = {}
            for line in r.out.splitlines():
                # New output block: "DSI-2 ..."
                if re.match(r'^[A-Z]', line) and '"' in line:
                    if current:
                        results.append(current)
                    name_m = re.match(r'^(\S+)\s+"([^"]*)"', line)
                    current = {
                        "output": name_m.group(1) if name_m else line.split()[0],
                        "enabled": None,
                        "mode": None,
                        "transform": None,
                        "scale": None,
                    }
                elif "Enabled:" in line:
                    current["enabled"] = "yes" in line
                elif "px," in line and ("preferred" in line or "current" in line):
                    m = re.search(r'(\d+x\d+)\s+px,\s+([\d.]+)\s+Hz', line)
                    if m:
                        current["mode"] = f"{m.group(1)}@{float(m.group(2)):.0f}"
                elif "Transform:" in line:
                    current["transform"] = line.split(":", 1)[1].strip()
                elif "Scale:" in line:
                    current["scale"] = line.split(":", 1)[1].strip()
            if current:
                results.append(current)
            break

    return results


def probe_backlights(p: RemoteProbe) -> list[BacklightInfo]:
    """Read all /sys/class/backlight/* devices."""
    backlights: list[BacklightInfo] = []

    r = p.run("ls /sys/class/backlight/ 2>/dev/null")
    if not r.ok or not r.out.strip():
        return backlights

    for name in _lines(r.out):
        def _read(attr: str) -> str:
            res = p.run(f"cat /sys/class/backlight/{name}/{attr} 2>/dev/null")
            return res.out.strip() if res.ok else ""

        brightness = int(_read("brightness") or "0")
        max_brightness = int(_read("max_brightness") or "255")
        bl_power = int(_read("bl_power") or "0")
        display_name = _read("display_name") or None

        backlights.append(BacklightInfo(
            name=name,
            brightness=brightness,
            max_brightness=max_brightness,
            bl_power=bl_power,
            display_name=display_name,
        ))

    return backlights


def probe_framebuffers(p: RemoteProbe) -> list[str]:
    r = p.run("ls /dev/fb* 2>/dev/null")
    if not r.ok:
        return []
    return _lines(r.out)


def probe_i2c_buses(p: RemoteProbe) -> list[I2CBusInfo]:
    """List I2C buses. Scan if i2cdetect is available."""
    buses: list[I2CBusInfo] = []

    r = p.run("ls /dev/i2c-* 2>/dev/null")
    if not r.ok or not r.out.strip():
        return buses

    has_i2cdetect = p.run("which i2cdetect 2>/dev/null").ok

    for entry in _lines(r.out):
        m = re.search(r'i2c-(\d+)', entry)
        if not m:
            continue
        bus_num = int(m.group(1))
        devices: list[str] = []

        if has_i2cdetect:
            scan = p.run(f"i2cdetect -y {bus_num} 2>/dev/null")
            if scan.ok:
                for line in scan.out.splitlines():
                    # e.g. "40: -- -- -- -- -- 45 -- --"
                    parts = line.split()
                    if not parts or not parts[0].endswith(":"):
                        continue
                    row_base = int(parts[0].rstrip(":"), 16)
                    for i, val in enumerate(parts[1:]):
                        if val not in ("--", "UU"):
                            addr = row_base + i
                            devices.append(f"0x{addr:02x}")

        buses.append(I2CBusInfo(bus=bus_num, devices=devices))

    return buses


def probe_dsi_dmesg(p: RemoteProbe) -> list[str]:
    """Collect relevant DSI/panel/backlight lines from dmesg."""
    r = p.run(
        "dmesg 2>/dev/null | grep -iE 'dsi|panel|backlight|waveshare|drm.*rp1' "
        "| grep -v 'cycle\\|bluetooth\\|brcm\\|Broad' | tail -30"
    )
    if not r.ok:
        return []
    return _lines(r.out)


# ── diagnostics analyzer ──────────────────────────────────────────────────────


def _analyze(hw: HardwareInfo) -> list[HardwareDiagnostic]:
    diag: list[HardwareDiagnostic] = []

    dsi_outputs = [o for o in hw.drm_outputs if "DSI" in o.name]
    has_waveshare_overlay = any(
        "waveshare" in l.lower() or "dsi-waveshare" in l.lower()
        for l in hw.dsi_overlays
    )
    has_dsi_overlay = any(
        "dsi" in l.lower() for l in hw.dsi_overlays
    )

    # 1. No DSI overlay configured
    if not has_dsi_overlay:
        diag.append(HardwareDiagnostic(
            component="overlay",
            severity="error",
            message="No DSI dtoverlay found in config.txt",
            fix=(
                "Add to /boot/firmware/config.txt:\n"
                "  dtoverlay=vc4-kms-dsi-waveshare-panel,8_0_inch\n"
                "Then reboot."
            ),
        ))

    # 2. display_auto_detect=1 while using manual DSI overlay
    if has_dsi_overlay and "display_auto_detect=1" in hw.config_txt:
        diag.append(HardwareDiagnostic(
            component="overlay",
            severity="warning",
            message="display_auto_detect=1 may conflict with manual DSI overlay",
            fix=(
                "Set display_auto_detect=0 in /boot/firmware/config.txt\n"
                "  sudo sed -i 's/^display_auto_detect=1/display_auto_detect=0/' "
                "/boot/firmware/config.txt"
            ),
        ))

    # 3. DSI output not connected
    if has_dsi_overlay and not dsi_outputs:
        diag.append(HardwareDiagnostic(
            component="dsi",
            severity="error",
            message="DSI overlay loaded but no DRM DSI connector found in /sys/class/drm/",
            fix=(
                "Check physical connection: For RPi5 the Waveshare 8\" (C) requires:\n"
                "  1. DSI-Cable-12cm → DISP1 (22-pin connector)\n"
                "  2. 4-pin header → RPi GPIO (5V + GND + SDA + SCL)\n"
                "Reseat the FPC ribbon cable and reboot."
            ),
        ))

    elif has_dsi_overlay and dsi_outputs:
        not_connected = [o for o in dsi_outputs if o.status != "connected"]
        if not_connected:
            diag.append(HardwareDiagnostic(
                component="dsi",
                severity="error",
                message=f"DSI connector status: {not_connected[0].status} (expected: connected)",
                fix=(
                    "Physical connection issue. Check:\n"
                    "  1. FPC ribbon seated in DISP1 (22-pin) — not DISP0 (15-pin)\n"
                    "  2. ZIF latch locked down firmly on both ends\n"
                    "  3. Silver contacts facing correct direction (towards board)"
                ),
            ))

    # 4. Backlight off or zero brightness
    for bl in hw.backlights:
        if bl.bl_power != 0:
            diag.append(HardwareDiagnostic(
                component="backlight",
                severity="error",
                message=f"Backlight {bl.name} power is OFF (bl_power={bl.bl_power})",
                fix=f"echo 0 | sudo tee /sys/class/backlight/{bl.name}/bl_power",
            ))
        if bl.brightness == 0:
            diag.append(HardwareDiagnostic(
                component="backlight",
                severity="warning",
                message=f"Backlight {bl.name} brightness is 0",
                fix=f"echo 255 | sudo tee /sys/class/backlight/{bl.name}/brightness",
            ))

    # 5. No backlight device found despite DSI connected
    if dsi_outputs and any(o.status == "connected" for o in dsi_outputs) and not hw.backlights:
        diag.append(HardwareDiagnostic(
            component="backlight",
            severity="error",
            message="DSI connected but no backlight sysfs device found",
            fix=(
                "The 4-pin header connection may be missing or the I2C backlight\n"
                "controller is not initializing. Check:\n"
                "  - 4-pin cable from display board → RPi GPIO header\n"
                "  - Pin 1 (5V), Pin 2 (GND), Pin 3 (SDA=GPIO2), Pin 4 (SCL=GPIO3)\n"
                "  - dtparam=i2c_arm=on must be set in config.txt"
            ),
        ))

    # 6. I2C backlight chip (0x45) not scanning
    for bl in hw.backlights:
        # name is like "11-0045" = bus 11, addr 0x45
        m = re.match(r'^(\d+)-0*([0-9a-f]+)$', bl.name)
        if not m:
            continue
        bus_num = int(m.group(1))
        addr = f"0x{int(m.group(2), 16):02x}"
        bus = next((b for b in hw.i2c_buses if b.bus == bus_num), None)
        if bus and bus.devices and addr not in bus.devices:
            diag.append(HardwareDiagnostic(
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

    # 7. Wayland/labwc not running
    if dsi_outputs and not hw.wlr_outputs:
        diag.append(HardwareDiagnostic(
            component="compositor",
            severity="warning",
            message="wlr-randr returned no outputs — labwc/wayland may not be running",
            fix=(
                "Check: systemctl --user status labwc\n"
                "Start: DISPLAY= labwc &\n"
                "Or check ~/.config/labwc/autostart"
            ),
        ))

    # 8. DSI detected, everything seems OK
    all_ok = (
        has_dsi_overlay
        and dsi_outputs
        and any(o.status == "connected" for o in dsi_outputs)
        and hw.backlights
        and all(b.bl_power == 0 and b.brightness > 0 for b in hw.backlights)
    )
    if all_ok and not any(d.severity in ("error", "critical") for d in diag):
        diag.append(HardwareDiagnostic(
            component="dsi",
            severity="info",
            message="DSI display appears correctly configured (connected, backlight on)",
        ))
        if not hw.wlr_outputs:
            diag.append(HardwareDiagnostic(
                component="compositor",
                severity="warning",
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
            ))

    return diag


# ── main entry point ──────────────────────────────────────────────────────────


def probe_hardware(p: RemoteProbe) -> HardwareInfo:
    """Probe hardware state of the remote host and return HardwareInfo with diagnostics."""
    board, kernel = probe_board(p)
    config_txt = probe_config_txt(p)

    # Parse active DSI overlays from config.txt
    dsi_overlays = [
        line.strip() for line in config_txt.splitlines()
        if re.match(r'\s*dtoverlay=.*dsi', line, re.IGNORECASE)
        and not line.strip().startswith("#")
    ]

    drm_outputs = probe_drm_outputs(p)
    wlr_outputs = probe_wlr_randr(p)
    backlights = probe_backlights(p)
    framebuffers = probe_framebuffers(p)
    i2c_buses = probe_i2c_buses(p)
    dsi_dmesg = probe_dsi_dmesg(p)

    # Enrich DrmOutputs with wlr-randr data
    for wo in wlr_outputs:
        out_name = wo.get("output", "")
        for drm in drm_outputs:
            if drm.connector == out_name:
                if wo.get("mode"):
                    drm.modes = [wo["mode"]]
                if wo.get("transform"):
                    drm.transform = wo["transform"]
                if wo.get("scale"):
                    drm.scale = wo["scale"]
                if wo.get("enabled") is not None:
                    drm.enabled = "enabled" if wo["enabled"] else "disabled"

    hw = HardwareInfo(
        board=board,
        kernel=kernel,
        config_txt=config_txt,
        dsi_overlays=dsi_overlays,
        drm_outputs=drm_outputs,
        wlr_outputs=wlr_outputs,
        backlights=backlights,
        framebuffers=framebuffers,
        i2c_buses=i2c_buses,
        dsi_dmesg=dsi_dmesg,
    )

    hw.diagnostics = _analyze(hw)
    return hw

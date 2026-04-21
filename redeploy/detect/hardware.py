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
from .hardware_rules import analyze as _analyze_rules
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


def probe_config_txt(p: RemoteProbe) -> tuple[str, str]:
    """Read /boot/firmware/config.txt (RPi5) or /boot/config.txt.

    Returns (content, path) — path is needed for idempotent edits later.
    """
    for path in ("/boot/firmware/config.txt", "/boot/config.txt"):
        r = p.run(f"cat {path} 2>/dev/null")
        if r.ok and r.out.strip():
            return r.out, path
    return "", "/boot/firmware/config.txt"


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
    """Delegate to rules engine in hardware_rules.py."""
    return _analyze_rules(hw)


# ── main entry point ──────────────────────────────────────────────────────────


def probe_hardware(p: RemoteProbe) -> HardwareInfo:
    """Probe hardware state of the remote host and return HardwareInfo with diagnostics."""
    board, kernel = probe_board(p)
    config_txt, config_txt_path = probe_config_txt(p)

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
        config_txt_path=config_txt_path,
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

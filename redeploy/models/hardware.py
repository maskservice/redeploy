"""Hardware models — output of hardware probe."""
from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import BaseModel, Field


class DrmOutput(BaseModel):
    """One DRM connector (e.g. card1-DSI-2, card2-HDMI-A-1)."""
    name: str                           # e.g. "card1-DSI-2"
    connector: str                      # e.g. "DSI-2", "HDMI-A-1"
    status: str = "unknown"             # connected / disconnected
    enabled: str = "unknown"            # enabled / disabled
    modes: list[str] = Field(default_factory=list)    # e.g. ["1280x800@60"]
    transform: str = "normal"
    position: str = "0,0"
    scale: str = "1.0"
    edid_bytes: int = 0                 # EDID size in bytes; 0 = no physical panel
    power_state: Optional[str] = None  # DPMS: "on", "off", "suspend"
    sysfs_path: str = ""               # e.g. /sys/class/drm/card1-DSI-2


class BacklightInfo(BaseModel):
    """Sysfs backlight device."""
    name: str                           # e.g. "11-0045"
    brightness: int = 0
    max_brightness: int = 255
    bl_power: int = 0                   # 0=on, 4=off
    display_name: Optional[str] = None  # e.g. "DSI-2"
    sysfs_path: str = ""               # e.g. /sys/class/backlight/11-0045


class I2CBusInfo(BaseModel):
    bus: int
    devices: list[str] = Field(default_factory=list)  # hex addresses found
    sysfs_path: str = ""               # e.g. /dev/i2c-11


class HardwareDiagnostic(BaseModel):
    """Problem found during hardware probe."""
    component: str                      # "dsi", "backlight", "i2c", "gpio", "overlay"
    severity: str = "warning"           # info / warning / error / critical
    message: str
    fix: Optional[str] = None          # suggested fix command or action


class HardwareInfo(BaseModel):
    """Hardware state produced by hardware probe."""
    board: Optional[str] = None         # e.g. "Raspberry Pi 5 Model B Rev 1.0"
    kernel: Optional[str] = None        # uname -r
    config_txt: str = ""                # full /boot/firmware/config.txt
    config_txt_path: str = "/boot/firmware/config.txt"

    # Display
    drm_outputs: list[DrmOutput] = Field(default_factory=list)
    backlights: list[BacklightInfo] = Field(default_factory=list)
    framebuffers: list[str] = Field(default_factory=list)   # /dev/fb* names
    wlr_outputs: list[dict] = Field(default_factory=list)   # raw wlr-randr output

    # DSI specific
    dsi_overlays: list[str] = Field(default_factory=list)   # active dtoverlay lines
    dsi_dmesg: list[str] = Field(default_factory=list)      # relevant dmesg lines
    dsi_dmesg_errors: list[str] = Field(default_factory=list)

    # I2C
    i2c_buses: list[I2CBusInfo] = Field(default_factory=list)

    # Kernel modules
    kernel_modules: list[str] = Field(default_factory=list)  # lsmod filtered

    # Wayland/compositor runtime state
    wayland_sockets: list[str] = Field(default_factory=list)  # e.g. ["wayland-0"]
    compositor_processes: dict[str, list[int]] = Field(default_factory=dict)

    # Diagnostics
    diagnostics: list[HardwareDiagnostic] = Field(default_factory=list)

    @property
    def has_dsi(self) -> bool:
        return any("DSI" in o.name for o in self.drm_outputs)

    @property
    def kms_enabled(self) -> bool:
        """True if vc4-kms-v3d overlay is present in config.txt."""
        return any(
            re.match(r'\s*dtoverlay=vc4-kms-v3d', line)
            for line in self.config_txt.splitlines()
            if not line.strip().startswith("#")
        )

    @property
    def dsi_connected(self) -> bool:
        """DRM reports connected — always True on RPi5 when DSI overlay is loaded."""
        return any("DSI" in o.name and o.status == "connected" for o in self.drm_outputs)

    @property
    def dsi_physically_connected(self) -> bool:
        """True only when a physical panel is present (EDID > 0 bytes)."""
        return any("DSI" in o.name and o.edid_bytes > 0 for o in self.drm_outputs)

    @property
    def dsi_enabled(self) -> bool:
        return any("DSI" in o.name and o.enabled == "enabled" for o in self.drm_outputs)

    @property
    def backlight_on(self) -> bool:
        return any(b.bl_power == 0 and b.brightness > 0 for b in self.backlights)

    @property
    def errors(self) -> list[HardwareDiagnostic]:
        return [d for d in self.diagnostics if d.severity in ("error", "critical")]

    @property
    def warnings(self) -> list[HardwareDiagnostic]:
        return [d for d in self.diagnostics if d.severity == "warning"]

"""Compositor definitions for kiosk deployments.

Encodes compositor-specific knowledge: where autostart lives, which output
manager is used, what environment variables are required.

Pi109 lesson: labwc uses kanshi for output management. The compositor must be
started BEFORE kanshi, which must settle BEFORE Chromium starts.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CompositorDefinition:
    """Static definition of a Wayland compositor for kiosk use."""

    id: str
    """Short identifier, e.g. 'labwc'."""

    autostart_path: str
    """Path to the autostart file (relative to $HOME or absolute)."""

    output_manager: str
    """Tool used to manage outputs: 'kanshi', 'wlr-randr', 'none'."""

    required_packages: list[str] = field(default_factory=list)
    """Packages that must be present on the target device."""

    required_env: list[str] = field(default_factory=list)
    """Environment variables a kiosk launcher script must export."""

    notes: list[str] = field(default_factory=list)
    """Human-readable caveats encoded from real debugging sessions."""

    def autostart_abs(self, home: str = "/home/pi") -> str:
        path = self.autostart_path
        if path.startswith("~"):
            path = home + path[1:]
        return path


LABWC = CompositorDefinition(
    id="labwc",
    autostart_path="~/.config/labwc/autostart",
    output_manager="kanshi",
    required_packages=["labwc", "kanshi", "wlr-randr"],
    required_env=["WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "XDG_SESSION_TYPE"],
    notes=[
        # Pi109 session knowledge:
        "kanshi must be started BEFORE Chromium (it disables HDMI-A-2)",
        "sleep 3 between kanshid and browser start allows kanshi to apply profile",
        "labwc autostart order: kanshid & → sleep 3 → bash ~/kiosk-launch.sh &",
        "--windowed flag conflicts with --kiosk under labwc; remove it",
        "XDG_SESSION_TYPE=wayland must be set or Chromium falls back to X11",
    ],
)

WESTON = CompositorDefinition(
    id="weston",
    autostart_path="~/.config/weston.ini",
    output_manager="weston",
    required_packages=["weston"],
    required_env=["WAYLAND_DISPLAY", "XDG_RUNTIME_DIR"],
    notes=[],
)

SWAY = CompositorDefinition(
    id="sway",
    autostart_path="~/.config/sway/config",
    output_manager="sway",
    required_packages=["sway", "swaybar"],
    required_env=["WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "XDG_SESSION_TYPE"],
    notes=[],
)

#: registry: compositor id → definition
COMPOSITORS: dict[str, CompositorDefinition] = {
    c.id: c for c in [LABWC, WESTON, SWAY]
}

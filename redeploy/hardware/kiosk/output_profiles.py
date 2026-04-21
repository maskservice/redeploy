"""Kanshi output profile generation for kiosk deployments.

Encodes the pi109 lesson: HDMI outputs must be explicitly disabled in the
kanshi profile so the DSI panel is the only active output BEFORE Chromium is
launched. If HDMI-A-2 is enabled, Chromium may open on it instead of DSI-2.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OutputProfile:
    """A kanshi output profile definition."""

    name: str
    """Profile name used in kanshi config, e.g. 'waveshare-only'."""

    enabled: list[str] = field(default_factory=list)
    """Connector names to enable, e.g. ['DSI-2']."""

    disabled: list[str] = field(default_factory=list)
    """Connector names to explicitly disable, e.g. ['HDMI-A-2']."""

    transforms: dict[str, str] = field(default_factory=dict)
    """Optional per-output transform, e.g. {'DSI-2': '90'}."""

    modes: dict[str, str] = field(default_factory=dict)
    """Optional per-output mode override, e.g. {'DSI-2': '800x480'}."""

    def to_kanshi_config(self) -> str:
        """Render the kanshi profile block as a string."""
        lines = [f"profile {self.name} {{"]
        for conn in self.enabled:
            parts = [f"    output {conn} enable"]
            if conn in self.modes:
                parts.append(f"mode {self.modes[conn]}")
            if conn in self.transforms:
                parts.append(f"transform {self.transforms[conn]}")
            lines.append(" ".join(parts))
        for conn in self.disabled:
            lines.append(f"    output {conn} disable")
        lines.append("}")
        return "\n".join(lines)


def dsi_only_profile(
    dsi_connector: str = "DSI-2",
    hdmi_connectors: list[str] | None = None,
    profile_name: str = "waveshare-only",
    transform: str | None = None,
) -> OutputProfile:
    """Factory: DSI panel enabled, all HDMI outputs disabled.

    Pi109 knowledge: RPi 5 exposes HDMI-A-1 and HDMI-A-2. Both must be
    disabled in kanshi so Chromium opens on DSI-2.
    """
    if hdmi_connectors is None:
        hdmi_connectors = ["HDMI-A-1", "HDMI-A-2"]
    transforms = {}
    if transform:
        transforms[dsi_connector] = transform
    return OutputProfile(
        name=profile_name,
        enabled=[dsi_connector],
        disabled=hdmi_connectors,
        transforms=transforms,
    )

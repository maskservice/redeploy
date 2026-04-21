"""Kiosk display configuration helpers — encoding pi109 session knowledge."""

from .autostart import AutostartEntry, ensure_autostart_entry, generate_labwc_autostart
from .browsers import BrowserKioskProfile, CHROMIUM_WAYLAND_KIOSK
from .compositors import CompositorDefinition, LABWC
from .output_profiles import OutputProfile, dsi_only_profile

__all__ = [
    "AutostartEntry",
    "ensure_autostart_entry",
    "generate_labwc_autostart",
    "BrowserKioskProfile",
    "CHROMIUM_WAYLAND_KIOSK",
    "CompositorDefinition",
    "LABWC",
    "OutputProfile",
    "dsi_only_profile",
]

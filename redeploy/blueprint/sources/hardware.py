"""Build ``HardwareRequirements`` from a DeviceMap hardware snapshot."""
from __future__ import annotations

from typing import Optional

from ...models import HardwareRequirements


def build_hw_requirements(hw) -> HardwareRequirements:
    """Derive hardware requirements from a probed *hw* object."""
    if hw is None:
        return HardwareRequirements()

    display_type = None
    display_res = None
    features: list[str] = []

    # DRM / DSI
    for output in getattr(hw, "drm_outputs", []):
        if "DSI" in (output.connector or ""):
            display_type = "DSI"
            if output.modes:
                display_res = output.modes[0]

    if getattr(hw, "backlights", []):
        features.append("backlight")
    if getattr(hw, "i2c_buses", []):
        features.append("i2c")

    # Infer arch from board name
    board = getattr(hw, "board", "") or ""
    arch = "linux/arm64" if any(x in board.lower() for x in ("rpi", "raspberry", "aarch64", "pi")) else ""

    # Overlays → wayland / kiosk hints
    for overlay in getattr(hw, "dsi_overlays", []):
        if "dsi" in overlay.lower():
            features.append("wayland")

    return HardwareRequirements(
        arch=arch,
        display_type=display_type,
        display_resolution=display_res,
        i2c_required=bool(getattr(hw, "i2c_buses", [])),
        features=features,
    )

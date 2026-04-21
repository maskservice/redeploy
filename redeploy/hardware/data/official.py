"""Official Raspberry Pi display panel definitions."""
from __future__ import annotations

from redeploy.hardware.panels import PanelDefinition, register

register(PanelDefinition(
    id="rpi-dsi-7-inch",
    name='Official Raspberry Pi 7" DSI 800×480',
    vendor="official",
    overlay="vc4-kms-dsi-rpi-touchscreen",
    overlay_params=(),
    resolution=(800, 480),
    requires_i2c_touch=True,
    notes=[
        "Oryginalny ekran RPi — sterownik vc4-kms-dsi-rpi-touchscreen",
        "Podłączenie zasilania przez 4-pin JST na module ekranu",
    ],
))

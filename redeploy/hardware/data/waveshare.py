"""Waveshare panel definitions."""
from __future__ import annotations

from redeploy.hardware.panels import PanelDefinition, register

register(PanelDefinition(
    id="waveshare-8-inch",
    name='Waveshare 8" DSI 1280×800 IPS',
    vendor="waveshare",
    overlay="vc4-kms-dsi-waveshare-panel-v2",
    overlay_params=("8_0_inch",),
    resolution=(1280, 800),
    requires_i2c_touch=True,
    notes=[
        "Port DSI1 domyślny; dla DSI0 dodaj ',dsi0' w overlay",
        "Jeśli dotyk nie reaguje, sprawdź raspi-config → I2C → enable",
    ],
))

register(PanelDefinition(
    id="waveshare-8-inch-a",
    name='Waveshare 8" DSI (wariant A)',
    vendor="waveshare",
    overlay="vc4-kms-dsi-waveshare-panel-v2",
    overlay_params=("8_0_inch_a",),
    resolution=(1280, 800),
    requires_i2c_touch=True,
))

register(PanelDefinition(
    id="waveshare-8_8-inch",
    name='Waveshare 8.8" DSI 480×1920',
    vendor="waveshare",
    overlay="vc4-kms-dsi-waveshare-panel-v2",
    overlay_params=("8_8_inch",),
    resolution=(480, 1920),
    requires_i2c_touch=True,
))

register(PanelDefinition(
    id="waveshare-7-inch-c",
    name='Waveshare 7" DSI (wariant C)',
    vendor="waveshare",
    overlay="vc4-kms-dsi-waveshare-panel-v2",
    overlay_params=("7_0_inch_c",),
    resolution=(1024, 600),
    requires_i2c_touch=True,
))

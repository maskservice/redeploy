"""HyperPixel panel definitions."""
from __future__ import annotations

from redeploy.hardware.panels import PanelDefinition, register

register(PanelDefinition(
    id="hyperpixel4-square",
    name="HyperPixel 4.0 Square 720×720",
    vendor="hyperpixel",
    overlay="vc4-kms-dpi-hyperpixel4sq",
    overlay_params=(),
    resolution=(720, 720),
    requires_spi_touch=True,
    notes=[
        "Dotyk przez SPI — raspi-config → SPI → enable",
        "Nie wymaga I2C",
    ],
))

register(PanelDefinition(
    id="hyperpixel4",
    name="HyperPixel 4.0 800×480",
    vendor="hyperpixel",
    overlay="vc4-kms-dpi-hyperpixel4",
    overlay_params=(),
    resolution=(800, 480),
    requires_spi_touch=True,
    notes=[
        "Dotyk przez SPI — raspi-config → SPI → enable",
    ],
))

register(PanelDefinition(
    id="hyperpixel2r",
    name="HyperPixel 2.1 Round 480×480",
    vendor="hyperpixel",
    overlay="vc4-kms-dpi-hyperpixel2r",
    overlay_params=(),
    resolution=(480, 480),
    requires_spi_touch=True,
))

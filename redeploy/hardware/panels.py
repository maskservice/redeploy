"""Panel definitions and registry for Raspberry Pi display panels."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

_REGISTRY: dict[str, "PanelDefinition"] = {}


@dataclass(frozen=True)
class PanelDefinition:
    """Definition of a Raspberry Pi display panel."""
    id: str  # "waveshare-8-inch"
    name: str  # human-readable
    vendor: Literal["waveshare", "official", "hyperpixel", "generic"]
    overlay: str  # "vc4-kms-dsi-waveshare-panel-v2"
    overlay_params: tuple[str, ...] = ()  # ("8_0_inch",) → appended after ","
    resolution: tuple[int, int] | None = None
    requires_kms: bool = True
    requires_i2c_touch: bool = False
    requires_spi_touch: bool = False
    supported_ports: tuple[str, ...] = ("dsi1", "dsi0")
    notes: list[str] = field(default_factory=list)

    def overlay_line(self, port: str = "dsi1") -> str:
        """Generate the dtoverlay line for this panel."""
        parts = [self.overlay, *self.overlay_params]
        if port == "dsi0":
            parts.append("dsi0")
        return f"dtoverlay={','.join(parts)}"


def register(panel: PanelDefinition) -> None:
    """Register a panel in the registry."""
    _REGISTRY[panel.id] = panel


def get(panel_id: str) -> PanelDefinition | None:
    """Get a panel by ID."""
    return _REGISTRY.get(panel_id)


def all_panels() -> list[PanelDefinition]:
    """Get all registered panels sorted by vendor and ID."""
    return sorted(_REGISTRY.values(), key=lambda p: (p.vendor, p.id))


def infer_from_hardware(hw) -> PanelDefinition | None:
    """Heuristic panel detection from HardwareInfo."""
    # TODO: Implement based on I2C bus scan, EDID, DSI connector detection
    return None

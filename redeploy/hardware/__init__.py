"""Hardware configuration support for Raspberry Pi."""
from __future__ import annotations

from .panels import PanelDefinition, get, all_panels, infer_from_hardware, register
from . import data as _data  # noqa: F401 — populates panel registry

__all__ = ["PanelDefinition", "get", "all_panels", "infer_from_hardware", "register"]


"""detect — Probe infrastructure and produce InfraState."""
from .detector import Detector
from .hardware import probe_hardware

__all__ = ["Detector", "probe_hardware"]

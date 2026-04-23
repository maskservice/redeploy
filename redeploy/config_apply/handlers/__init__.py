"""Hardware/infrastructure config-apply handlers.

Each handler receives a ``(console, probe, value)`` triple and performs
the remote mutation + local reporting.
"""
from __future__ import annotations

from .display import apply_display_transform

__all__ = ["apply_display_transform"]

"""Shared config-apply layer for ``--apply-config`` across CLI commands.

Unifies the duplicated load-host-connect-apply logic found in
``hardware``, ``device-map``, and ``blueprint`` commands.
"""
from __future__ import annotations

from .applier import apply_config_dict, apply_config_file
from .loader import load_config_file

__all__ = [
    "apply_config_dict",
    "apply_config_file",
    "load_config_file",
]

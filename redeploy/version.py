"""Deprecated: use redeploy.version package instead.

This file is a backward-compatibility shim. All functions have been moved
to the redeploy.version package (redeploy/version/__init__.py).

Import from the package:
    from redeploy.version import read_local_version, check_version, ...
"""
from __future__ import annotations

from redeploy.version import (
    check_version,
    check_version_http,
    read_local_version,
    read_remote_version,
)

__all__ = [
    "read_local_version",
    "read_remote_version",
    "check_version",
    "check_version_http",
]

"""redeploy version management — declarative version manifest system.

This module implements Part III of the redeploy refactoring plan:
systematic version management through .redeploy/version.yaml manifests.

Example:
    >>> from redeploy.version import VersionManifest, bump_version
    >>> manifest = VersionManifest.load(Path(".redeploy/version.yaml"))
    >>> bump_version(manifest, "patch")  # Atomically bumps all sources
"""
from __future__ import annotations

from .manifest import VersionManifest, SourceConfig, GitConfig, ChangelogConfig
from .transaction import VersionBumpTransaction
from .bump import bump_version, verify_sources
from .sources import get_adapter

__all__ = [
    "VersionManifest",
    "SourceConfig",
    "GitConfig",
    "ChangelogConfig",
    "VersionBumpTransaction",
    "bump_version",
    "verify_sources",
    "get_adapter",
]

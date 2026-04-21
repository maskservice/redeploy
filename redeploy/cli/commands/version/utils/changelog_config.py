"""Resolve changelog config for a package release."""
from __future__ import annotations

from typing import Any


def resolve_package_release_changelog_config(
    manifest_model: Any,
    package_name: str | None,
    *,
    allow_root_fallback: bool,
) -> Any:
    """Return the changelog config for *package_name* with optional root fallback."""
    if not package_name:
        return manifest_model.changelog

    package_manifest = manifest_model.get_package(package_name)
    if package_manifest is None:
        raise ValueError(f"Package '{package_name}' not found in manifest")

    if package_manifest.changelog is not None:
        return package_manifest.changelog

    if allow_root_fallback:
        return manifest_model.changelog

    return None

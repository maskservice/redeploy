"""Version drift detection - compare manifest vs spec vs live.

Closes the deploy loop: manifest → migration.yaml → live host.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .manifest import VersionManifest


@dataclass
class VersionDiff:
    """Version comparison result."""

    source: str  # "manifest", "spec", "live", "image"
    version: Optional[str]
    expected: Optional[str]
    match: bool
    error: Optional[str] = None


def diff_manifest_vs_spec(
    manifest: VersionManifest,
    spec_version: Optional[str],
) -> VersionDiff:
    """Compare manifest version vs migration.yaml target.version.

    Handles '@manifest' reference in spec.
    """
    manifest_version = manifest.version

    if spec_version is None or not str(spec_version).strip():
        return VersionDiff(
            source="spec",
            version=None,
            expected=manifest_version,
            match=False,
            error="target.version not set in spec",
        )

    spec_version = str(spec_version).strip()

    # Handle @manifest reference
    if spec_version == "@manifest":
        return VersionDiff(
            source="spec (@manifest)",
            version=manifest_version,
            expected=manifest_version,
            match=True,
        )

    # Direct version comparison
    match = manifest_version == spec_version
    return VersionDiff(
        source="spec",
        version=spec_version,
        expected=manifest_version,
        match=match,
    )


def diff_manifest_vs_live(
    manifest: VersionManifest,
    live_version: Optional[str],
) -> VersionDiff:
    """Compare manifest version vs live deployed version."""
    manifest_version = manifest.version

    if live_version is None:
        return VersionDiff(
            source="live",
            version=None,
            expected=manifest_version,
            match=False,
            error="Could not detect live version",
        )

    match = manifest_version == live_version
    return VersionDiff(
        source="live",
        version=live_version,
        expected=manifest_version,
        match=match,
    )


def format_diff_report(diffs: list[VersionDiff], manifest_version: str) -> str:
    """Format diff results as human-readable report."""
    lines = [
        f"Manifest version: {manifest_version}",
        "",
        "Version comparison:",
    ]

    for d in diffs:
        status = "✓" if d.match else "✗"
        actual = d.version or "(unknown)"
        if d.error:
            lines.append(f"  {status} {d.source}: {d.error}")
        else:
            lines.append(f"  {status} {d.source}: {actual} (expected {d.expected})")

    # Summary
    mismatches = [d for d in diffs if not d.match]
    if mismatches:
        lines.extend([
            "",
            f"⚠ {len(mismatches)} version drift(s) detected",
        ])
    else:
        lines.extend([
            "",
            "✓ All versions in sync",
        ])

    return "\n".join(lines)

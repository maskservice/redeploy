"""Atomic version bump transaction with prepare/commit/rollback.

Implements two-phase commit for multi-source version updates:
1. prepare() - stage all changes to tempfiles (validation)
2. commit() - atomic rename of all staged files
3. rollback() - cleanup on failure
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .manifest import SourceConfig, VersionManifest
from .sources import get_adapter


@dataclass
class StagingResult:
    """Result of staging one source."""

    source: SourceConfig
    ok: bool
    temp_path: Optional[Path] = None
    error: Optional[Exception] = None
    old_version: str = ""


class VersionBumpTransaction:
    """Atomic transaction for bumping version across multiple sources.

    Usage:
        tx = VersionBumpTransaction(manifest, "1.0.21")
        results = tx.prepare()  # Stage to tempfiles
        if all(r.ok for r in results):
            tx.commit()  # Atomic apply
        else:
            tx.rollback()  # Cleanup
    """

    def __init__(self, manifest: VersionManifest, new_version: str):
        self.manifest = manifest
        self.new_version = new_version
        self._staged: list[tuple[Path, Path, SourceConfig]] = []  # (temp, final, source)
        self._results: list[StagingResult] = []

    def prepare(self) -> list[StagingResult]:
        """Stage all changes to tempfiles without touching targets.

        Returns list of results. If any fails, caller should rollback().
        """
        self._results = []
        self._staged = []

        for source in self.manifest.sources:
            result = self._stage_one(source)
            self._results.append(result)
            if result.ok and result.temp_path:
                self._staged.append((result.temp_path, source.path, source))

        return self._results

    def _stage_one(self, source: SourceConfig) -> StagingResult:
        """Stage single source to temp file."""
        adapter = get_adapter(source.format)

        # Read current version for reporting
        old_version = ""
        try:
            old_version = adapter.read(source.path, source)
        except Exception:
            if not source.optional:
                pass  # Will fail in stage anyway

        try:
            temp = adapter.stage(source.path, source, self.new_version)
            return StagingResult(
                source=source,
                ok=True,
                temp_path=temp,
                old_version=old_version,
            )
        except Exception as e:
            return StagingResult(
                source=source,
                ok=False,
                error=e,
                old_version=old_version,
            )

    def commit(self) -> None:
        """Atomically apply all staged changes.

        Raises if any rename fails. Partial renames leave system inconsistent,
        but individual renames are atomic (os.replace).
        """
        if not self._staged:
            raise ValueError("No staged changes to commit. Call prepare() first.")

        # Create parent directories if needed
        for temp, final, _ in self._staged:
            final.parent.mkdir(parents=True, exist_ok=True)

        # Atomic rename loop
        renamed = []
        try:
            for temp, final, _ in self._staged:
                temp.replace(final)  # Atomic on POSIX
                renamed.append(final)
        except Exception:
            # Best-effort cleanup: we can't rollback renamed files
            # but we can cleanup remaining temps
            for temp, _, _ in self._staged[len(renamed):]:
                temp.unlink(missing_ok=True)
            raise

        # Cleanup any remaining temps (shouldn't happen)
        for temp, _, _ in self._staged:
            if temp.exists():
                temp.unlink(missing_ok=True)

    def rollback(self) -> None:
        """Cleanup staged tempfiles without applying changes."""
        for temp, _, _ in self._staged:
            if temp.exists():
                temp.unlink(missing_ok=True)
        self._staged = []

    def get_summary(self) -> dict:
        """Get summary of transaction for reporting."""
        return {
            "new_version": self.new_version,
            "total": len(self._results),
            "success": sum(1 for r in self._results if r.ok),
            "failed": sum(1 for r in self._results if not r.ok),
            "sources": [
                {
                    "path": str(r.source.path),
                    "format": r.source.format,
                    "old": r.old_version,
                    "new": self.new_version if r.ok else None,
                    "ok": r.ok,
                    "error": str(r.error) if r.error else None,
                }
                for r in self._results
            ],
        }

"""Public API for version bump operations."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .git_integration import GitIntegrationError
from .git_transaction import GitTransactionResult, GitVersionBumpTransaction
from .manifest import VersionManifest
from .sources import get_adapter
from .transaction import VersionBumpTransaction


def bump_version(
    manifest: VersionManifest,
    bump_type: str,  # "patch", "minor", "major", "prerelease"
    new_version: Optional[str] = None,  # explicit version (overrides bump_type)
) -> dict:
    """Bump version across all sources atomically.

    Args:
        manifest: Loaded version manifest
        bump_type: "patch", "minor", "major", or "prerelease"
        new_version: Optional explicit version (bypasses bump calculation)

    Returns:
        Summary dict with transaction results

    Raises:
        ValueError: If bump_type invalid or transaction fails
    """
    # Calculate new version if not explicit
    if new_version is None:
        new_version = _calculate_bump(manifest.version, bump_type)

    # Create and execute transaction
    tx = VersionBumpTransaction(manifest, new_version)
    results = tx.prepare()

    # Check for failures
    failures = [r for r in results if not r.ok]
    if failures:
        tx.rollback()
        errors = "\n".join(f"  - {r.source.path}: {r.error}" for r in failures)
        raise ValueError(f"Failed to stage {len(failures)} source(s):\n{errors}")

    # All staged successfully - commit
    tx.commit()

    # Update manifest in-memory
    manifest.version = new_version

    return tx.get_summary()


def verify_sources(manifest: VersionManifest) -> dict:
    """Verify all sources are in sync with manifest.version.

    Returns dict with verification results.
    """
    results = []
    all_match = True

    for source in manifest.sources:
        adapter = get_adapter(source.format)
        try:
            actual = adapter.read(source.path, source)
            match = actual == manifest.version
            if not match:
                all_match = False
            results.append({
                "path": str(source.path),
                "format": source.format,
                "expected": manifest.version,
                "actual": actual,
                "match": match,
                "ok": True,
            })
        except Exception as e:
            all_match = False
            results.append({
                "path": str(source.path),
                "format": source.format,
                "expected": manifest.version,
                "actual": None,
                "match": False,
                "ok": False,
                "error": str(e),
            })

    return {
        "version": manifest.version,
        "all_match": all_match,
        "sources": results,
    }


def bump_version_with_git(
    manifest: VersionManifest,
    bump_type: str,
    repo_path: Path = Path("."),
    new_version: Optional[str] = None,
    manifest_path: Optional[Path] = None,
    commit: bool = False,
    tag: bool = False,
    push: bool = False,
    sign: bool = False,
    allow_dirty: bool = False,
) -> GitTransactionResult:
    """Bump version with optional git integration.

    Args:
        manifest: Loaded version manifest
        bump_type: "patch", "minor", "major", or "prerelease"
        repo_path: Path to git repository
        new_version: Optional explicit version (bypasses bump calculation)
        commit: Create git commit
        tag: Create git tag
        push: Push to origin (implies commit+tag)
        sign: Sign tag with GPG
        allow_dirty: Allow bump with dirty working directory

    Returns:
        GitTransactionResult with details of what was done

    Raises:
        GitIntegrationError: If git operations fail
        ValueError: If bump or transaction fails
    """
    # Calculate new version if not explicit
    if new_version is None:
        new_version = _calculate_bump(manifest.version, bump_type)

    # Create extended transaction
    tx = GitVersionBumpTransaction(
        manifest,
        new_version,
        repo_path,
        manifest_path=manifest_path,
        allow_dirty=allow_dirty,
    )

    # Prepare (stage files, check git clean)
    results = tx.prepare()

    # Check for failures
    failures = [r for r in results if not r.ok]
    if failures:
        tx.rollback()
        errors = "\n".join(f"  - {r.source.path}: {r.error}" for r in failures)
        raise ValueError(f"Failed to stage {len(failures)} source(s):\n{errors}")

    # All staged successfully - commit file changes
    tx.commit()

    # Update manifest in-memory and on disk
    manifest.version = new_version
    manifest.save(manifest_path or (repo_path / ".redeploy" / "version.yaml"))

    # Git operations
    if commit or tag or push:
        git_result = tx.commit_and_tag(
            create_commit=commit or push,
            create_tag=tag or push,
            sign_tag=sign,
        )

        if push:
            tx.push()
            git_result.pushed = True

        return git_result

    # No git operations - return simple result
    return GitTransactionResult(
        version=new_version,
        files_updated=len(tx._touched_files),
    )


def bump_package(
    manifest: VersionManifest,
    package_name: str,
    bump_type: str,
    new_version: Optional[str] = None,
) -> dict:
    """Bump version of a single package in a monorepo manifest.

    Args:
        manifest:      Loaded version manifest (policy=independent)
        package_name:  Key in manifest.packages
        bump_type:     "patch", "minor", "major", or "prerelease"
        new_version:   Explicit version (bypasses bump calculation)

    Returns:
        Summary dict with ``package``, ``old``, ``new_version``, transaction results.

    Raises:
        KeyError:   If package_name not found in manifest.packages
        ValueError: If transaction fails
    """
    pkg = manifest.get_package(package_name)
    if pkg is None:
        available = manifest.list_packages()
        raise KeyError(
            f"Package '{package_name}' not found. "
            f"Available: {available or '(none)'}"
        )

    if new_version is None:
        new_version = _calculate_bump(pkg.version, bump_type)

    # Create a temporary mini-manifest for this package's sources
    mini = VersionManifest(
        version=pkg.version,
        sources=pkg.sources,
        git=pkg.git or manifest.git,
    )

    tx = VersionBumpTransaction(mini, new_version)
    results = tx.prepare()

    failures = [r for r in results if not r.ok]
    if failures:
        tx.rollback()
        errors = "\n".join(f"  - {r.source.path}: {r.error}" for r in failures)
        raise ValueError(f"Failed to stage {len(failures)} source(s) for '{package_name}':\n{errors}")

    tx.commit()
    pkg.version = new_version

    return {
        "package": package_name,
        "old": mini.version,
        "new_version": new_version,
        **tx.get_summary(),
    }


def bump_all_packages(
    manifest: VersionManifest,
    bump_type: str,
) -> list[dict]:
    """Bump all packages in a monorepo manifest independently.

    Returns list of bump summaries per package.
    """
    if not manifest.is_monorepo():
        raise ValueError("Manifest has no packages defined (not a monorepo)")

    results = []
    for name in manifest.list_packages():
        results.append(bump_package(manifest, name, bump_type))
    return results


def _calculate_bump(current: str, bump_type: str) -> str:
    """Calculate new version from current + bump type."""
    # Basic semver parsing
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$", current)
    if not match:
        raise ValueError(f"Cannot bump non-semver version: {current}")

    major, minor, patch, prerelease = match.groups()
    major, minor, patch = int(major), int(minor), int(patch)

    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    elif bump_type == "prerelease":
        if prerelease:
            # Increment prerelease number
            base = re.match(r"^(.*?)(\d+)$", prerelease)
            if base:
                prefix, num = base.groups()
                return f"{major}.{minor}.{patch}-{prefix}{int(num) + 1}"
            return f"{major}.{minor}.{patch}-{prerelease}.1"
        return f"{major}.{minor}.{patch}-rc.1"
    else:
        raise ValueError(f"Unknown bump type: {bump_type}")

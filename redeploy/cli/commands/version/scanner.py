"""Version scan helpers for auto-detecting version sources."""
from __future__ import annotations

import click
from pathlib import Path
from rich.console import Console

from ....version.manifest import PackageConfig, SourceConfig
from ....version.sources import get_adapter


def _version_scan_specs():
    """Get version scan specs."""
    return [
        ("VERSION", "plain", None),
        ("pyproject.toml", "toml", "project.version"),
        ("package.json", "json", "version"),
    ]


def _regex_version_scan_specs():
    """Get regex version scan specs."""
    return [
        ("__init__.py", r'__version__\s*=\s*["\']([^"\']+)["\']'),
        ("src/__init__.py", r'__version__\s*=\s*["\']([^"\']+)["\']'),
        ("version.ts", r'(?:export\s+)?(?:const|let|var)\s+VERSION\s*=\s*["\']([^"\']+)["\']'),
        ("src/version.ts", r'(?:export\s+)?(?:const|let|var)\s+VERSION\s*=\s*["\']([^"\']+)["\']'),
        ("version.h", r'#define\s+[A-Z0-9_]*VERSION\s+"([^"]+)"'),
        ("src/version.h", r'#define\s+[A-Z0-9_]*VERSION\s+"([^"]+)"'),
        ("include/version.h", r'#define\s+[A-Z0-9_]*VERSION\s+"([^"]+)"'),
    ]


def _is_scannable_version_path(path: Path) -> bool:
    """Check if path is scannable."""
    ignored = {".git", ".venv", ".redeploy", "node_modules", "__pycache__", "dist", "build"}
    return not any(part in ignored for part in path.parts)


def _normalize_scan_exclusions(excluded_paths) -> set[str]:
    """Normalize scan exclusions."""
    return {
        str(Path(path)).replace("\\", "/")
        for path in excluded_paths
        if str(path).strip()
    }


def _detect_version_sources_in_dir(directory: Path, workspace_root: Path, *, excluded_paths: set[str] | None = None):
    """Detect version sources in a directory."""
    excluded_paths = excluded_paths or set()
    sources = []
    for filename, format_name, key in _version_scan_specs():
        candidate = directory / filename
        if not candidate.exists() or not candidate.is_file():
            continue

        relative_path = candidate.relative_to(workspace_root)
        if not _is_scannable_version_path(relative_path):
            continue
        if relative_path.as_posix() in excluded_paths:
            continue

        source_kwargs = {"path": relative_path, "format": format_name}
        if key is not None:
            source_kwargs["key"] = key
        sources.append(SourceConfig(**source_kwargs))

    for relative_filename, pattern in _regex_version_scan_specs():
        candidate = directory / relative_filename
        if not candidate.exists() or not candidate.is_file():
            continue

        relative_path = candidate.relative_to(workspace_root)
        if not _is_scannable_version_path(relative_path):
            continue
        if relative_path.as_posix() in excluded_paths:
            continue

        sources.append(SourceConfig(path=relative_path, format="regex", pattern=pattern))

    return sources


def _detect_source_version(sources, *, default: str):
    """Detect version from sources."""
    detected = _read_detected_source_versions(sources)
    return detected[0][1] if detected else default


def _read_detected_source_versions(sources):
    """Read detected source versions."""
    detected = []
    for source in sources:
        try:
            detected.append((source, get_adapter(source.format).read(source.path, source)))
        except Exception:
            continue
    return detected


def _report_version_scan_conflict(console, label: str, sources, chosen_version: str):
    """Report version scan conflict."""
    detected = _read_detected_source_versions(sources)
    unique_versions = {version for _, version in detected}
    if len(unique_versions) <= 1:
        return

    details = ", ".join(f"{source.path}={version}" for source, version in detected)
    console.print(
        f"[yellow]⚠ Version conflict in {label}: {details}; using {chosen_version}[/yellow]"
    )


def _print_version_scan_review(console, root_sources, packages):
    """Print version scan review."""
    console.print("[bold]Scan review[/bold]")

    if root_sources:
        _print_version_scan_group(console, "root", root_sources, default_version="0.0.0")

    if packages:
        for package_name, package in packages.items():
            _print_version_scan_group(console, package_name, package.sources, default_version=package.version)

    if not root_sources and not packages:
        console.print("  No version sources detected")


def _classify_version_scan_source_confidence(source, *, actual: str) -> str:
    """Classify version scan source confidence."""
    if actual == "(unreadable)":
        return "unreadable"
    if source.format == "regex":
        return "heuristic"
    return "certain"


def _format_version_scan_source_status(confidence: str, *, conflict: bool) -> str:
    """Format version scan source status."""
    parts = [f"confidence={confidence}"]
    if conflict:
        parts.append("conflict=yes")
    return " ".join(parts)


def _default_keep_scanned_source(confidence: str, *, conflict: bool) -> bool:
    """Default keep scanned source."""
    return confidence == "certain" and not conflict


def _summarize_version_scan_group(sources, *, default_version: str):
    """Summarize version scan group."""
    detected = _read_detected_source_versions(sources)
    detected_map = {str(source.path): version for source, version in detected}
    unique_versions = {version for _, version in detected}
    chosen_version = detected[0][1] if detected else default_version
    has_conflict = len(unique_versions) > 1
    reviewed_sources = []

    for source in sources:
        actual = detected_map.get(str(source.path), "(unreadable)")
        confidence = _classify_version_scan_source_confidence(source, actual=actual)
        is_conflict = has_conflict and actual not in {"(unreadable)", chosen_version}
        reviewed_sources.append((source, actual, confidence, is_conflict))

    return chosen_version, has_conflict, reviewed_sources


def _print_version_scan_group(console, label: str, sources, *, default_version: str):
    """Print version scan group."""
    chosen_version, has_conflict, reviewed_sources = _summarize_version_scan_group(
        sources, default_version=default_version
    )
    suffix = " (conflict)" if has_conflict else ""

    console.print(f"  {label}: chosen version {chosen_version}{suffix}")
    for source, actual, confidence, is_conflict in reviewed_sources:
        status = _format_version_scan_source_status(confidence, conflict=is_conflict)
        console.print(f"    - {source.path} ({source.format}) current: {actual} {status}")


def _iter_version_scan_groups(root_sources, packages):
    """Iterate version scan groups."""
    if root_sources:
        yield "root", root_sources, "0.0.0"

    if packages:
        for package_name, package in packages.items():
            yield package_name, package.sources, package.version


def _review_detected_sources_interactively(console, root_sources, packages) -> set[str]:
    """Review detected sources interactively."""
    rejected = set()
    console.print("[bold]Interactive scan review[/bold]")

    for label, sources, default_version in _iter_version_scan_groups(root_sources, packages):
        chosen_version, has_conflict, reviewed_sources = _summarize_version_scan_group(
            sources, default_version=default_version
        )
        suffix = " (conflict)" if has_conflict else ""

        console.print(f"\n[bold]{label}[/bold]: chosen version {chosen_version}{suffix}")
        for source, actual, confidence, is_conflict in reviewed_sources:
            status = _format_version_scan_source_status(confidence, conflict=is_conflict)
            keep = click.confirm(
                f"Keep {source.path} ({source.format}) current={actual} {status}?",
                default=_default_keep_scanned_source(confidence, conflict=is_conflict),
            )
            if not keep:
                rejected.add(source.path.as_posix())

    return rejected


def _derive_scanned_package_name(package_dir: Path, workspace_root: Path, used_names: set[str]) -> str:
    """Derive scanned package name."""
    relative_dir = package_dir.relative_to(workspace_root)
    if len(relative_dir.parts) > 1 and relative_dir.parts[0] in {"packages", "apps", "services", "modules"}:
        candidate = relative_dir.parts[-1]
    else:
        candidate = relative_dir.as_posix()

    if candidate in used_names:
        candidate = relative_dir.as_posix().replace("/", "-")

    return candidate


def _scan_package_version_manifests(workspace_root: Path, *, excluded_paths: set[str] | None = None):
    """Scan package version manifests."""
    excluded_paths = excluded_paths or set()
    package_dirs = []
    for candidate in sorted(workspace_root.rglob("*")):
        if not candidate.is_dir() or candidate == workspace_root:
            continue

        relative_path = candidate.relative_to(workspace_root)
        if not _is_scannable_version_path(relative_path):
            continue
        if candidate.name in {"src", "include"}:
            continue

        if _detect_version_sources_in_dir(candidate, workspace_root, excluded_paths=excluded_paths):
            package_dirs.append(candidate)

    packages = {}
    used_names = set()
    for package_dir in package_dirs:
        sources = _detect_version_sources_in_dir(package_dir, workspace_root, excluded_paths=excluded_paths)
        if not sources:
            continue

        package_name = _derive_scanned_package_name(package_dir, workspace_root, used_names)
        used_names.add(package_name)
        packages[package_name] = PackageConfig(
            version=_detect_source_version(sources, default="0.1.0"),
            sources=sources,
        )

    return packages or None

"""Helper functions for version CLI commands."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console


def _resolve_monorepo_targets(manifest_model, package_name, all_packages, console):
    """Resolve monorepo targets from package_name and all_packages flags."""
    if package_name and all_packages:
        console.print("[red]✗ Use either --package NAME or --all-packages, not both.[/red]")
        import sys
        sys.exit(1)

    if not (package_name or all_packages):
        return None

    if not manifest_model.is_monorepo():
        console.print(
            "[red]✗ Manifest has no packages defined. Add 'packages:' section for monorepo support.[/red]"
        )
        import sys
        sys.exit(1)

    if package_name:
        pkg = manifest_model.get_package(package_name)
        if pkg is None:
            console.print(f"[red]✗ Package '{package_name}' not found in manifest[/red]")
            console.print(f"  Available: {manifest_model.list_packages()}")
            import sys
            sys.exit(1)
        return [package_name]

    return manifest_model.list_packages()


def _build_package_version_manifest(manifest_model, package_name: str, *, allow_root_changelog_fallback: bool):
    """Build a VersionManifest for a specific package."""
    from ....version.manifest import VersionManifest

    package_manifest = manifest_model.get_package(package_name)
    if package_manifest is None:
        raise ValueError(f"Package '{package_name}' not found in manifest")

    return VersionManifest(
        version=package_manifest.version,
        scheme=manifest_model.scheme,
        policy="synced",
        sources=package_manifest.sources,
        git=_resolve_package_release_git_config(manifest_model, package_name),
        changelog=_resolve_package_release_changelog_config(
            manifest_model, package_name, allow_root_fallback=allow_root_changelog_fallback
        ),
        commits=manifest_model.commits,
    )


def _resolve_package_release_git_config(manifest_model, package_name: str | None):
    """Resolve git config for package release."""
    if not package_name:
        return manifest_model.git

    package_manifest = manifest_model.get_package(package_name)
    if package_manifest is None:
        raise ValueError(f"Package '{package_name}' not found in manifest")

    git_config = package_manifest.git if package_manifest.git else manifest_model.git

    try:
        tag_format = package_manifest.tag_format.format(
            package=package_name,
            version="{version}",
        )
    except KeyError as exc:
        raise ValueError(
            f"Invalid tag_format for package '{package_name}': missing placeholder '{exc.args[0]}'"
        ) from exc

    return git_config.model_copy(update={"tag_format": tag_format})


def _resolve_package_release_changelog_config(manifest_model, package_name: str | None, *, allow_root_fallback: bool):
    """Resolve changelog config for package release."""
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


def _print_verify_result(console, result, expected_version: str, *, label: str | None = None) -> bool:
    """Print verify result and return True if drift detected."""
    prefix = f"{label}: " if label else ""

    if result["all_match"]:
        console.print(
            f"[green]✓ {prefix}All {len(result['sources'])} sources in sync at {expected_version}[/green]"
        )
        return False

    console.print(f"[red]✗ {prefix}Version drift detected[/red]")
    for source in result["sources"]:
        if not source["match"]:
            actual = source.get("actual") or "ERROR"
            console.print(
                f"  [red]✗[/red] {source['path']}: expected {expected_version}, found {actual}"
            )
    return True


def _print_source_drift_status(console, result, expected_version: str) -> bool:
    """Print source drift status."""
    if not result["all_match"]:
        mismatch_count = len([s for s in result["sources"] if not s["match"]])
        console.print(f"[yellow]⚠ Source drift detected in {mismatch_count} file(s)[/yellow]")
        for source in result["sources"]:
            if not source["match"]:
                actual = source.get("actual") or "ERROR"
                console.print(f"  [red]✗[/red] {source['path']}: {actual} ≠ {expected_version}")
        return True

    console.print(
        f"[green]✓ All {len(result['sources'])} sources in sync at {expected_version}[/green]"
    )
    return False


def _load_spec_version_diff(manifest_model, spec):
    """Load version diff from spec file."""
    import yaml

    from ....version.diff import VersionDiff, diff_manifest_vs_spec

    if not spec:
        return None

    spec_path = Path(spec)
    if not spec_path.exists():
        return VersionDiff(
            source="spec",
            version=None,
            expected=manifest_model.version,
            match=False,
            error=f"Spec not found: {spec_path}",
        )

    try:
        spec_data = yaml.safe_load(spec_path.read_text()) or {}
        if not isinstance(spec_data, dict):
            raise ValueError("spec root must be a mapping")

        target_data = spec_data.get("target") or {}
        if not isinstance(target_data, dict):
            raise ValueError("spec target must be a mapping")

        return diff_manifest_vs_spec(manifest_model, target_data.get("version"))
    except Exception as e:
        return VersionDiff(
            source="spec",
            version=None,
            expected=manifest_model.version,
            match=False,
            error=f"Could not read spec: {e}",
        )


def _load_live_version_diff(manifest_model, live, app):
    """Load version diff from live host."""
    from ....ssh import SshClient
    from ....version import read_remote_version
    from ....version.diff import VersionDiff, diff_manifest_vs_live

    if not live:
        return None

    try:
        remote = SshClient(live)
        live_version = read_remote_version(remote, "~/c2004", app)
        return diff_manifest_vs_live(manifest_model, live_version)
    except Exception as e:
        return VersionDiff(
            source="live",
            version=None,
            expected=manifest_model.version,
            match=False,
            error=f"Could not check live version: {e}",
        )


def _run_version_diff_for_manifest(
    console, manifest_model, spec, live, app, *, label: str | None = None
) -> bool:
    """Run version diff for a manifest."""
    from ....version import verify_sources
    from ....version.diff import format_diff_report

    if label:
        console.print(f"[bold]{label}[/bold]")

    result = verify_sources(manifest_model)
    has_source_drift = _print_source_drift_status(console, result, manifest_model.version)

    diffs = []
    spec_diff = _load_spec_version_diff(manifest_model, spec)
    if spec_diff is not None:
        diffs.append(spec_diff)

    live_diff = _load_live_version_diff(manifest_model, live, app)
    if live_diff is not None:
        diffs.append(live_diff)

    if diffs:
        console.print()
        console.print(format_diff_report(diffs, manifest_model.version))

    return (not has_source_drift) and all(diff.match for diff in diffs)


def _bump_single(
    m,
    bump_type,
    dry_run,
    analyze,
    commit,
    tag,
    push,
    sign,
    allow_dirty,
    changelog,
    *,
    repo_path,
    console,
    package_name: str = None,
    manifest_path: Path | None = None,
    new_version: str | None = None,
    allow_default_changelog: bool = True,
):
    """Bump version for a single manifest (or package)."""
    from ....version.bump import _calculate_bump, bump_version, bump_version_with_git
    from ....version.commits import analyze_commits, format_analysis_report
    from ....version.git_integration import GitIntegrationError
    from .release import _format_release_tag, _update_release_changelog

    old = m.version
    prefix = f"[{package_name}] " if package_name else ""

    # Auto-analyze if requested
    if analyze:
        last_tag = m.git.tag_format.format(version=old)
        analysis = analyze_commits(last_tag, repo_path, m.commits)

        console.print(f"{prefix}[bold]Analyzing commits...[/bold]")
        console.print(format_analysis_report(analysis))

        if analysis.bump_type:
            bump_type = analysis.bump_type
            console.print(f"\n{prefix}Using detected bump type: [bold]{bump_type}[/bold]")
        else:
            console.print(
                f"\n{prefix}[yellow]No bump-worthy commits found. Use explicit type to force bump.[/yellow]"
            )
            return None

    if not bump_type:
        console.print("[red]✗ Bump type required (patch/minor/major) or use --analyze[/red]")
        import sys
        sys.exit(1)

    target_version = new_version or _calculate_bump(old, bump_type)

    # Dry run
    if dry_run:
        console.print(f"[DRY RUN] Would change version: {old} → {target_version}")
        console.print(f"  Sources: {len(m.sources)}")
        if commit or tag or push:
            console.print(f"  Git: commit={commit}, tag={tag}, push={push}, sign={sign}")
        if changelog:
            changelog_path = m.changelog.path if m.changelog else Path("CHANGELOG.md")
            console.print(f"  Changelog: update {changelog_path}")
        for s in m.sources:
            console.print(f"    - {s.path} ({s.format})")
        return

    # Real bump
    try:
        # Handle changelog update
        if changelog:
            _update_release_changelog(
                m,
                repo_path,
                target_version,
                console,
                previous_tag=_format_release_tag(m.git, old),
                label=package_name,
                allow_default=allow_default_changelog,
            )

        if commit or tag or push:
            result = bump_version_with_git(
                m,
                bump_type,
                repo_path=repo_path,
                new_version=target_version,
                manifest_path=manifest_path,
                commit=commit or push,
                tag=tag or push,
                push=push,
                sign=sign,
                allow_dirty=allow_dirty,
            )
            console.print(f"[green]✓ Changed version: {old} → {result.version}[/green]")
            console.print(f"  Updated {result.files_updated} files")
            if result.commit_hash:
                console.print(f"  Commit: {result.commit_hash[:8]}")
            if result.tag_name:
                console.print(f"  Tag: {result.tag_name}")
            if result.pushed:
                console.print("  Pushed to origin")
            return result
        else:
            result = bump_version(m, bump_type, new_version=target_version)
            if manifest_path is not None:
                m.save(manifest_path)
            console.print(f"[green]✓ Changed version: {old} → {result['new_version']}[/green]")
            console.print(f"  Updated {result['success']}/{result['total']} sources")
            return result

    except GitIntegrationError as e:
        console.print(f"[red]✗ Git error: {e}[/red]")
        import sys
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Bump failed: {e}[/red]")
        import traceback

        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        import sys
        sys.exit(1)

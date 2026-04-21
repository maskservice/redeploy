"""CLI commands for version management."""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .helpers import (
    _bump_single,
    _build_package_version_manifest,
    _load_spec_version_diff,
    _load_live_version_diff,
    _print_verify_result,
    _print_source_drift_status,
    _resolve_monorepo_targets,
    _run_version_diff_for_manifest,
)
from .monorepo import _set_monorepo_version
from .scanner import (
    _detect_source_version,
    _detect_version_sources_in_dir,
    _normalize_scan_exclusions,
    _print_version_scan_review,
    _report_version_scan_conflict,
    _review_detected_sources_interactively,
    _scan_package_version_manifests,
)


@click.group(name="version")
def version_cmd():
    """Declarative version management: bump, verify, diff.

    Reads .redeploy/version.yaml manifest and manages version
    across all declared sources atomically.
    """
    pass


# ── current ──────────────────────────────────────────────────────────────────


@version_cmd.command(name="current")
@click.option(
    "--manifest", "-m", default=".redeploy/version.yaml",
    help="Path to version manifest"
)
@click.option(
    "--package", "package_name", "-p",
    help="Show version for a specific package (for monorepo)"
)
@click.option(
    "--all-packages", is_flag=True, help="Show versions for all packages (for monorepo)"
)
def version_current(manifest, package_name, all_packages):
    """Show current version from manifest."""
    from ....version import VersionManifest

    console = Console()
    path = Path(manifest)

    if not path.exists():
        console.print(f"[red]✗ Manifest not found: {path}[/red]")
        console.print("  Run: redeploy version init")
        sys.exit(1)

    try:
        m = VersionManifest.load(path)
        targets = _resolve_monorepo_targets(m, package_name, all_packages, console)

        if targets:
            if package_name:
                console.print(f"[bold]{m.get_package(package_name).version}[/bold]")
                return

            console.print("[bold]Package current versions[/bold]")
            table = Table(show_header=True, box=None)
            table.add_column("Package", style="bold")
            table.add_column("Version")

            for pkg_name in targets:
                table.add_row(pkg_name, m.get_package(pkg_name).version)

            console.print(table)
            return

        console.print(f"[bold]{m.version}[/bold]")
    except Exception as e:
        console.print(f"[red]✗ Error loading manifest: {e}[/red]")
        sys.exit(1)


# ── list ─────────────────────────────────────────────────────────────────────


@version_cmd.command(name="list")
@click.option(
    "--manifest", "-m", default=".redeploy/version.yaml",
    help="Path to version manifest"
)
@click.option(
    "--package", "package_name", "-p",
    help="List sources for a specific package (for monorepo)"
)
@click.option(
    "--all-packages", is_flag=True, help="List sources for all packages (for monorepo)"
)
def version_list(manifest, package_name, all_packages):
    """List all version sources and their values."""
    from ....version import VersionManifest, verify_sources

    console = Console()
    path = Path(manifest)

    if not path.exists():
        console.print(f"[red]✗ Manifest not found: {path}[/red]")
        sys.exit(1)

    m = VersionManifest.load(path)
    targets = _resolve_monorepo_targets(m, package_name, all_packages, console)

    if targets:
        any_drift = False
        console.print("[bold]Package version sources[/bold]")
        t = Table(show_header=True, box=None)
        t.add_column("Package", style="bold")
        t.add_column("Manifest")
        t.add_column("Source")
        t.add_column("Format")
        t.add_column("Current")
        t.add_column("Status")

        for pkg_name in targets:
            pkg_manifest = _build_package_version_manifest(
                m, pkg_name, allow_root_changelog_fallback=True
            )
            result = verify_sources(pkg_manifest)
            if not result["all_match"]:
                any_drift = True

            for source in result["sources"]:
                status = "[green]✓" if source["match"] else "[red]✗ drift"
                actual = source["actual"] or "[dim]—[/dim]"
                t.add_row(
                    pkg_name,
                    result["version"],
                    str(source["path"]),
                    source["format"],
                    actual,
                    status,
                )

        console.print(t)
        if any_drift:
            console.print("\n[yellow]⚠ Some sources are out of sync[/yellow]")
            sys.exit(1)
        return

    result = verify_sources(m)

    console.print(f"[bold]Version sources[/bold] (manifest: {m.version})")
    t = Table(show_header=True, box=None)
    t.add_column("Source", style="bold")
    t.add_column("Format")
    t.add_column("Current")
    t.add_column("Status")

    for s in result["sources"]:
        status = "[green]✓" if s["match"] else "[red]✗ drift"
        actual = s["actual"] or "[dim]—[/dim]"
        t.add_row(str(s["path"]), s["format"], actual, status)

    console.print(t)
    if not result["all_match"]:
        console.print("\n[yellow]⚠ Some sources are out of sync[/yellow]")
        sys.exit(1)


# ── verify ───────────────────────────────────────────────────────────────────


@version_cmd.command(name="verify")
@click.option(
    "--manifest", "-m", default=".redeploy/version.yaml",
    help="Path to version manifest"
)
@click.option(
    "--package", "package_name", "-p",
    help="Verify sources for a specific package (for monorepo)"
)
@click.option(
    "--all-packages", is_flag=True, help="Verify sources for all packages (for monorepo)"
)
def version_verify(manifest, package_name, all_packages):
    """Verify all sources match manifest version."""
    from ....version import VersionManifest, verify_sources

    console = Console()
    path = Path(manifest)

    if not path.exists():
        console.print(f"[red]✗ Manifest not found: {path}[/red]")
        sys.exit(1)

    m = VersionManifest.load(path)
    targets = _resolve_monorepo_targets(m, package_name, all_packages, console)

    if targets:
        any_drift = False
        for pkg_name in targets:
            pkg_manifest = _build_package_version_manifest(
                m, pkg_name, allow_root_changelog_fallback=True
            )
            result = verify_sources(pkg_manifest)
            any_drift = _print_verify_result(
                console, result, pkg_manifest.version, label=pkg_name
            ) or any_drift

        if any_drift:
            sys.exit(1)
        return

    result = verify_sources(m)
    if _print_verify_result(console, result, m.version):
        sys.exit(1)


# ── bump ──────────────────────────────────────────────────────────────────────


@version_cmd.command(name="bump")
@click.argument(
    "type", type=click.Choice(["patch", "minor", "major", "prerelease"]), required=False
)
@click.option(
    "--manifest", "-m", default=".redeploy/version.yaml",
    help="Path to version manifest"
)
@click.option("--package", "-p", help="Bump specific package (for monorepo)")
@click.option("--all-packages", is_flag=True, help="Bump all packages (for monorepo)")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying")
@click.option("--analyze", is_flag=True, help="Auto-detect bump type from conventional commits")
@click.option("--commit", is_flag=True, help="Create git commit with changes")
@click.option("--tag", is_flag=True, help="Create git tag for new version")
@click.option("--push", is_flag=True, help="Push commit and tags to origin")
@click.option("--sign", is_flag=True, help="Sign tag with GPG")
@click.option("--allow-dirty", is_flag=True, help="Allow bump with dirty working directory")
@click.option("--changelog", is_flag=True, help="Update CHANGELOG.md")
def version_bump(
    type, manifest, package, all_packages, dry_run, analyze,
    commit, tag, push, sign, allow_dirty, changelog
):
    """Bump version across all sources atomically.

    Examples:
        redeploy version bump patch
        redeploy version bump patch --commit --tag --push
        redeploy version bump --analyze --commit --tag  # Auto-detect from commits
    """
    from ....version import VersionManifest

    console = Console()
    path = Path(manifest)

    if not path.exists():
        console.print(f"[red]✗ Manifest not found: {path}[/red]")
        console.print("  Run: redeploy version init")
        sys.exit(1)

    m = VersionManifest.load(path)

    # Handle monorepo packages
    if package:
        pkg = m.get_package(package)
        if pkg is None:
            console.print(f"[red]✗ Package '{package}' not found in manifest[/red]")
            console.print(f"  Available: {m.list_packages()}")
            sys.exit(1)

        pkg_manifest = _build_package_version_manifest(
            m, package, allow_root_changelog_fallback=True
        )

        result = _bump_single(
            pkg_manifest, type, dry_run, analyze, commit, tag, push, sign,
            allow_dirty, changelog,
            repo_path=path.parent.parent,
            console=console,
            package_name=package,
            allow_default_changelog=True,
        )

        # Update package version in main manifest
        if not dry_run and result:
            pkg.version = result.version if hasattr(result, "version") else result["new_version"]
            m.save(path)

        return

    if all_packages and m.is_monorepo():
        for pkg_name in m.list_packages():
            console.print(f"\n[bold]Bumping package: {pkg_name}[/bold]")
            pkg = m.get_package(pkg_name)
            pkg_manifest = _build_package_version_manifest(
                m, pkg_name, allow_root_changelog_fallback=False
            )

            _bump_single(
                pkg_manifest, type, dry_run, analyze, commit, tag, push, sign,
                allow_dirty, changelog,
                repo_path=path.parent.parent,
                console=console,
                package_name=pkg_name,
                allow_default_changelog=False,
            )

            if not dry_run:
                pkg.version = pkg_manifest.version

        if not dry_run:
            m.save(path)
        return

    # Standard single-repo bump
    old = m.version
    _bump_single(
        m, type, dry_run, analyze, commit, tag, push, sign, allow_dirty, changelog,
        repo_path=path.parent.parent,
        console=console,
        manifest_path=path,
    )

    if not dry_run:
        m.save(path)


# ── set ──────────────────────────────────────────────────────────────────────


@version_cmd.command(name="set")
@click.argument("version")
@click.option(
    "--manifest", "manifest_path_str", default=".redeploy/version.yaml",
    help="Path to version manifest"
)
@click.option("--package", "package_name", "-p", help="Set version for a specific package")
@click.option("--all-packages", is_flag=True, help="Set version for all packages")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying")
@click.option("--commit", is_flag=True, help="Create git commit with changes")
@click.option("--tag", is_flag=True, help="Create git tag for new version")
@click.option("--push", is_flag=True, help="Push commit and tags to origin")
@click.option("--sign", is_flag=True, help="Sign tag with GPG")
@click.option("--allow-dirty", is_flag=True, help="Allow version change with dirty working directory")
@click.option("--changelog", is_flag=True, help="Update CHANGELOG.md")
def version_set(
    version, manifest_path_str, package_name, all_packages, dry_run,
    commit, tag, push, sign, allow_dirty, changelog
):
    """Set an explicit version across all manifest sources."""
    from ....version import VersionManifest
    from ....version.git_integration import GitIntegrationError

    console = Console()
    manifest_path = Path(manifest_path_str)

    if not manifest_path.exists():
        console.print(f"[red]✗ Manifest not found: {manifest_path}[/red]")
        console.print("  Run: redeploy version init")
        sys.exit(1)

    manifest_model = VersionManifest.load(manifest_path)
    targets = _resolve_monorepo_targets(manifest_model, package_name, all_packages, console)

    if targets:
        try:
            _set_monorepo_version(
                manifest_model, version, targets, manifest_path, dry_run,
                commit, tag, push, sign, allow_dirty, changelog, console,
                package_name=package_name,
            )
            return
        except GitIntegrationError as e:
            console.print(f"[red]✗ Git error: {e}[/red]")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]✗ Version set failed: {e}[/red]")
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")
            sys.exit(1)

    _bump_single(
        manifest_model,
        "patch",
        dry_run,
        False,
        commit,
        tag,
        push,
        sign,
        allow_dirty,
        changelog,
        repo_path=manifest_path.parent.parent,
        console=console,
        manifest_path=manifest_path,
        new_version=version,
    )

    if not dry_run:
        manifest_model.save(manifest_path)


# ── init ─────────────────────────────────────────────────────────────────────


@version_cmd.command(name="init")
@click.option("--scan", is_flag=True, help="Auto-detect version sources")
@click.option("--review", is_flag=True, help="Review detected sources without writing manifest")
@click.option(
    "--interactive", is_flag=True,
    help="Interactively accept or reject detected sources before writing manifest"
)
@click.option(
    "--exclude", "excluded_paths", multiple=True,
    help="Exclude a detected source path from scan results (repeatable)"
)
@click.option("--force", is_flag=True, help="Overwrite existing manifest")
def version_init(scan, review, interactive, excluded_paths, force):
    """Initialize .redeploy/version.yaml manifest."""
    from ....version.manifest import VersionManifest, SourceConfig, GitConfig

    console = Console()
    manifest_path = Path(".redeploy/version.yaml")

    if manifest_path.exists() and not force:
        console.print(f"[yellow]⚠ Manifest already exists: {manifest_path}[/yellow]")
        console.print("  Use --force to overwrite or edit existing file")
        sys.exit(1)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    root = Path.cwd()
    root_sources = []
    packages = None
    excluded = _normalize_scan_exclusions(excluded_paths)

    if (review or interactive or excluded) and not scan:
        console.print("[red]✗ --review, --interactive and --exclude require --scan[/red]")
        sys.exit(1)

    if scan:
        root_sources = _detect_version_sources_in_dir(root, root, excluded_paths=excluded)
        packages = _scan_package_version_manifests(root, excluded_paths=excluded)

        if interactive:
            excluded.update(
                _review_detected_sources_interactively(console, root_sources, packages)
            )
            root_sources = _detect_version_sources_in_dir(root, root, excluded_paths=excluded)
            packages = _scan_package_version_manifests(root, excluded_paths=excluded)

            if not root_sources and not packages:
                console.print("[yellow]⚠ No sources selected - manifest not written[/yellow]")
                return

            _print_version_scan_review(console, root_sources, packages)
            if not click.confirm("Write manifest to .redeploy/version.yaml?", default=True):
                console.print("[yellow]Review complete - manifest not written[/yellow]")
                return

        if review and not interactive:
            _print_version_scan_review(console, root_sources, packages)
            console.print("[yellow]Review only - manifest not written[/yellow]")
            return

    if packages:
        current = _detect_source_version(root_sources, default="0.0.0") if root_sources else "0.0.0"
        m = VersionManifest(
            version=current,
            scheme="semver",
            policy="independent",
            sources=root_sources,
            git=GitConfig(),
            packages=packages,
        )
    else:
        sources = root_sources
        if not sources:
            sources = [SourceConfig(path=Path("VERSION"), format="plain")]

        current = _detect_source_version(sources, default="0.1.0")
        m = VersionManifest(
            version=current,
            scheme="semver",
            policy="synced",
            sources=sources,
            git=GitConfig(),
        )

    m.save(manifest_path)
    console.print(f"[green]✓ Created {manifest_path}[/green]")
    console.print(f"  Current version: {current}")
    console.print(f"  Policy: {m.policy}")

    if m.sources:
        console.print(f"  Sources: {len(m.sources)}")
        for source in m.sources:
            console.print(f"    - {source.path} ({source.format})")

    if m.is_monorepo():
        console.print(f"  Packages: {len(m.packages or {})}")
        for package_name in m.list_packages():
            package = m.get_package(package_name)
            console.print(
                f"    - {package_name}: {package.version} ({len(package.sources)} sources)"
            )

    if scan:
        if m.sources:
            _report_version_scan_conflict(console, "root", m.sources, m.version)
        if m.is_monorepo():
            for package_name in m.list_packages():
                package = m.get_package(package_name)
                _report_version_scan_conflict(console, package_name, package.sources, package.version)


# ── diff ──────────────────────────────────────────────────────────────────────


@version_cmd.command(name="diff")
@click.option(
    "--manifest", "-m", default=".redeploy/version.yaml",
    help="Path to version manifest"
)
@click.option(
    "--package", "package_name", "-p",
    help="Compare a specific package (for monorepo)"
)
@click.option(
    "--all-packages", is_flag=True,
    help="Compare all packages (for monorepo, source drift only)"
)
@click.option("--spec", help="Path to migration.yaml to compare")
@click.option("--live", help="SSH host to check live version (user@host)")
@click.option("--app", default="c2004", help="Application name for live check")
def version_diff(manifest, package_name, all_packages, spec, live, app):
    """Compare manifest version vs spec vs live.

    Examples:
        redeploy version diff                    # sources only
        redeploy version diff --spec migration.yaml   # vs migration.yaml
        redeploy version diff --live root@vps.example.com  # vs live
    """
    from ....version import VersionManifest

    console = Console()
    path = Path(manifest)

    if not path.exists():
        console.print(f"[red]✗ Manifest not found: {path}[/red]")
        sys.exit(1)

    m = VersionManifest.load(path)
    targets = _resolve_monorepo_targets(m, package_name, all_packages, console)

    if targets and not package_name and (spec or live):
        console.print(
            "[red]✗ --spec/--live require --package for monorepo manifests; --all-packages checks source drift only.[/red]"
        )
        sys.exit(1)

    if targets:
        all_match = True
        for index, pkg_name in enumerate(targets):
            if index:
                console.print()
            pkg_manifest = _build_package_version_manifest(
                m, pkg_name, allow_root_changelog_fallback=True
            )
            if not _run_version_diff_for_manifest(
                console, pkg_manifest, spec, live, app, label=pkg_name
            ):
                all_match = False
    else:
        all_match = _run_version_diff_for_manifest(console, m, spec, live, app)

    if all_match:
        console.print(f"\n[green]✓ No version drift detected[/green]")
    else:
        console.print(f"\n[yellow]⚠ Version drift detected - review before deploying[/yellow]")
        sys.exit(1)

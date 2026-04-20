"""version command group — Declarative version management."""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table


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
    from ...version import VersionManifest

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
    from ...version import VersionManifest, verify_sources

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
    from ...version import VersionManifest, verify_sources

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
    from ...version import VersionManifest

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
    from ...version import VersionManifest
    from ...version.git_integration import GitIntegrationError

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
    from ...version.manifest import VersionManifest, SourceConfig, GitConfig

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
    from ...version import VersionManifest

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


# ── Helper functions ────────────────────────────────────────────────────────


def _resolve_monorepo_targets(manifest_model, package_name, all_packages, console):
    """Resolve monorepo targets from package_name and all_packages flags."""
    if package_name and all_packages:
        console.print("[red]✗ Use either --package NAME or --all-packages, not both.[/red]")
        sys.exit(1)

    if not (package_name or all_packages):
        return None

    if not manifest_model.is_monorepo():
        console.print(
            "[red]✗ Manifest has no packages defined. Add 'packages:' section for monorepo support.[/red]"
        )
        sys.exit(1)

    if package_name:
        pkg = manifest_model.get_package(package_name)
        if pkg is None:
            console.print(f"[red]✗ Package '{package_name}' not found in manifest[/red]")
            console.print(f"  Available: {manifest_model.list_packages()}")
            sys.exit(1)
        return [package_name]

    return manifest_model.list_packages()


def _build_package_version_manifest(manifest_model, package_name: str, *, allow_root_changelog_fallback: bool):
    """Build a VersionManifest for a specific package."""
    from ...version.manifest import VersionManifest

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

    from ...version.diff import VersionDiff, diff_manifest_vs_spec

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
    from ...ssh import SshClient
    from ...version import read_remote_version
    from ...version.diff import VersionDiff, diff_manifest_vs_live

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
    from ...version import verify_sources
    from ...version.diff import format_diff_report

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
    from ...version.bump import _calculate_bump, bump_version, bump_version_with_git
    from ...version.commits import analyze_commits, format_analysis_report
    from ...version.git_integration import GitIntegrationError

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
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Bump failed: {e}[/red]")
        import traceback

        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)


def _format_release_tag(git_config, version: str) -> str:
    """Format release tag from git config."""
    return git_config.tag_format.format(version=version)


def _update_release_changelog(
    manifest_model,
    repo_path,
    version,
    console,
    *,
    previous_tag: str,
    label: str | None = None,
    changelog_config=None,
    allow_default: bool = True,
):
    """Update release changelog."""
    from ...version.changelog import ChangelogManager, get_commits_since_tag

    config = changelog_config or manifest_model.changelog
    if config is None and allow_default:
        changelog_path = Path("CHANGELOG.md")
    elif config is None:
        label_text = f" for {label}" if label else ""
        console.print(
            f"[yellow]⚠ Skipping changelog{label_text}: no package changelog configured[/yellow]"
        )
        return None
    else:
        changelog_path = config.path

    changelog_mgr = ChangelogManager(repo_path / changelog_path)
    commits = get_commits_since_tag(repo_path, previous_tag)
    new_content = changelog_mgr.prepare_release(version, commit_messages=commits)
    changelog_mgr.write(new_content)
    label_text = f" for {label}" if label else ""
    console.print(f"[green]✓ Updated {changelog_path}{label_text}[/green]")
    return changelog_path


def _set_monorepo_version(
    manifest_model,
    version,
    targets,
    manifest_path,
    dry_run,
    commit,
    tag,
    push,
    sign,
    allow_dirty,
    changelog,
    console,
    *,
    package_name,
):
    """Set version for monorepo packages."""
    from ...version.bump import bump_package
    from ...version.git_integration import GitIntegration

    repo_path = manifest_path.parent.parent

    if dry_run:
        _print_monorepo_set_dry_run(manifest_model, targets, version, console)
        return

    git = _create_version_set_git(
        manifest_model, repo_path, package_name, commit, tag, push, allow_dirty
    )
    taggers = (
        _create_version_set_taggers(manifest_model, repo_path, targets)
        if (tag or push)
        else []
    )

    touched_files = []
    if changelog:
        touched_files.extend(
            _update_monorepo_release_changelogs(
                manifest_model, repo_path, version, targets, console, package_name=package_name
            )
        )

    for pkg_name in targets:
        pkg = manifest_model.get_package(pkg_name)
        result = bump_package(manifest_model, pkg_name, "patch", new_version=version)
        touched_files.extend(source.path for source in pkg.sources)
        console.print(
            f"[green]✓[/green] {pkg_name}: {result['old']} → {result['new_version']}  "
            f"({result['success']}/{result['total']} sources)"
        )

    manifest_model.save(manifest_path)
    touched_files.append(manifest_path)

    if git:
        _finalize_monorepo_version_set(
            git, version, touched_files, commit, tag, push, sign, console, len(targets), taggers=taggers
        )


def _print_monorepo_set_dry_run(manifest_model, targets, version, console):
    """Print dry run for monorepo version set."""
    for pkg_name in targets:
        pkg = manifest_model.get_package(pkg_name)
        console.print(f"[DRY RUN] Would set {pkg_name}: {pkg.version} → {version}")
        console.print(f"  Sources: {len(pkg.sources)}")
        for source in pkg.sources:
            console.print(f"    - {source.path} ({source.format})")


def _create_version_set_git(
    manifest_model, repo_path, package_name, commit, tag, push, allow_dirty
):
    """Create git integration for version set."""
    from ...version.git_integration import GitIntegration

    if not (commit or tag or push):
        return None

    git_config = _resolve_package_release_git_config(manifest_model, package_name)
    git = GitIntegration(git_config, repo_path)

    if git_config.require_clean and not allow_dirty:
        git.require_clean()

    return git


def _create_version_set_taggers(manifest_model, repo_path, targets):
    """Create taggers for monorepo version set."""
    from ...version.git_integration import GitIntegration

    return [
        GitIntegration(_resolve_package_release_git_config(manifest_model, pkg_name), repo_path)
        for pkg_name in targets
    ]


def _create_release_tags(taggers, version, sign):
    """Create release tags."""
    tag_names = []
    seen = set()

    for git in taggers:
        tag_name = _format_release_tag(git.config, version)
        if tag_name in seen:
            continue
        git.tag(version, sign=sign)
        seen.add(tag_name)
        tag_names.append(tag_name)

    return tag_names


def _finalize_monorepo_version_set(
    git, version, touched_files, commit, tag, push, sign, console, package_count, *, taggers
):
    """Finalize monorepo version set."""
    unique_files = []
    for file_path in touched_files:
        if file_path not in unique_files:
            unique_files.append(file_path)

    commit_hash = None
    tag_names = []
    if commit or push:
        commit_hash = git.commit(version, unique_files)
    if tag or push:
        tag_names = _create_release_tags(taggers, version, sign)
    if push:
        git.push(follow_tags=True)

    console.print(f"[green]✓ Set version to {version} for {package_count} package(s)[/green]")
    if commit_hash:
        console.print(f"  Commit: {commit_hash[:8]}")
    for tag_name in tag_names:
        console.print(f"  Tag: {tag_name}")
    if push:
        console.print("  Pushed to origin")


def _update_monorepo_release_changelogs(
    manifest_model, repo_path, version, targets, console, *, package_name
):
    """Update changelogs for monorepo packages."""
    touched_files = []

    if package_name:
        package_manifest = manifest_model.get_package(package_name)
        touched = _update_release_changelog(
            manifest_model,
            repo_path,
            version,
            console,
            previous_tag=_format_release_tag(
                _resolve_package_release_git_config(manifest_model, package_name),
                package_manifest.version,
            ),
            label=package_name,
            changelog_config=_resolve_package_release_changelog_config(
                manifest_model, package_name, allow_root_fallback=True
            ),
            allow_default=True,
        )
        if touched is not None:
            touched_files.append(touched)
        return touched_files

    for pkg_name in targets:
        package_manifest = manifest_model.get_package(pkg_name)
        touched = _update_release_changelog(
            manifest_model,
            repo_path,
            version,
            console,
            previous_tag=_format_release_tag(
                _resolve_package_release_git_config(manifest_model, pkg_name),
                package_manifest.version,
            ),
            label=pkg_name,
            changelog_config=_resolve_package_release_changelog_config(
                manifest_model, pkg_name, allow_root_fallback=False
            ),
            allow_default=False,
        )
        if touched is not None:
            touched_files.append(touched)

    return touched_files


# ── Version scan helpers ────────────────────────────────────────────────────


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
    from ...version.manifest import SourceConfig

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
    from ...version.sources import get_adapter

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
    from ...version.manifest import PackageConfig

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

"""Monorepo-specific helper functions for version CLI."""
from __future__ import annotations

from pathlib import Path
from rich.console import Console

from .release import (
    _create_release_tags,
    _format_release_tag,
    _resolve_package_release_changelog_config,
    _resolve_package_release_git_config,
    _update_monorepo_release_changelogs,
)


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
    from ....version.bump import bump_package
    from ....version.git_integration import GitIntegration

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
    from ....version.git_integration import GitIntegration

    if not (commit or tag or push):
        return None

    git_config = _resolve_package_release_git_config(manifest_model, package_name)
    git = GitIntegration(git_config, repo_path)

    if git_config.require_clean and not allow_dirty:
        git.require_clean()

    return git


def _create_version_set_taggers(manifest_model, repo_path, targets):
    """Create taggers for monorepo version set."""
    from ....version.git_integration import GitIntegration

    return [
        GitIntegration(_resolve_package_release_git_config(manifest_model, pkg_name), repo_path)
        for pkg_name in targets
    ]


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

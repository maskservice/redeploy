"""Release-related helper functions for version CLI."""
from __future__ import annotations

from pathlib import Path
from rich.console import Console


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
    from ....version.changelog import ChangelogManager, get_commits_since_tag

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

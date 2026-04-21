"""Shared version-command utilities."""
from .git_config import resolve_package_release_git_config
from .changelog_config import resolve_package_release_changelog_config

__all__ = [
    "resolve_package_release_git_config",
    "resolve_package_release_changelog_config",
]

"""Changelog management for keep-a-changelog format.

Supports auto-generating changelog entries from conventional commits.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .commits import ConventionalCommit, parse_conventional


class ChangelogManager:
    """Manage CHANGELOG.md in keep-a-changelog format."""

    def __init__(self, path: Path):
        self.path = path

    def exists(self) -> bool:
        """Check if changelog file exists."""
        return self.path.exists()

    def read(self) -> str:
        """Read changelog content."""
        if not self.exists():
            return self._default_template()
        return self.path.read_text(encoding="utf-8")

    def _default_template(self) -> str:
        """Default changelog template."""
        return "# Changelog\n\nAll notable changes to this project will be documented in this file.\n\n## [Unreleased]\n\n"

    def get_unreleased_section(self) -> str:
        """Extract current unreleased section content."""
        content = self.read()
        # Match ## [Unreleased] up to next ## or EOF
        match = re.search(
            r"## \[Unreleased\]\s*\n(.*?)(?=\n## \[|\Z)",
            content,
            re.DOTALL | re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()
        return ""

    def prepare_release(
        self,
        version: str,
        date: Optional[str] = None,
        commit_messages: Optional[list[str]] = None,
    ) -> str:
        """Prepare changelog for release.

        Replaces ## [Unreleased] with ## [version] - date
        and adds new empty ## [Unreleased] section.

        Args:
            version: Version string for release
            date: Release date (defaults to today)
            commit_messages: Optional commit messages to auto-categorize

        Returns:
            Updated changelog content
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        content = self.read()

        # Build release section content
        release_content = self._format_release_content(
            self.get_unreleased_section(),
            commit_messages or [],
        )

        # Replace [Unreleased] with [version] and add new [Unreleased]
        new_section = f"## [Unreleased]\n\n## [{version}] - {date}\n\n{release_content}\n"

        updated = re.sub(
            r"## \[Unreleased\]\s*\n",
            new_section,
            content,
            flags=re.IGNORECASE,
        )

        # If no replacement happened, prepend to beginning
        if updated == content:
            updated = f"# Changelog\n\n{new_section}{content.lstrip()}"

        return updated

    def _format_release_content(
        self,
        unreleased_content: str,
        commit_messages: list[str],
    ) -> str:
        """Format release content from unreleased section + commits."""
        # If unreleased section has content, use it
        if unreleased_content.strip():
            return unreleased_content

        # Auto-categorize from commit messages
        if not commit_messages:
            return ""

        categories = self._init_categories()
        self._categorize_commits(commit_messages, categories)
        return self._build_release_content(categories)

    def _init_categories(self) -> dict[str, list[str]]:
        """Initialize empty category buckets."""
        return {
            "Added": [],
            "Changed": [],
            "Deprecated": [],
            "Removed": [],
            "Fixed": [],
            "Security": [],
        }

    def _categorize_commits(self, commit_messages: list[str], categories: dict[str, list[str]]) -> None:
        """Categorize commit messages into buckets."""
        for msg in commit_messages:
            commit = parse_conventional(msg)
            if not commit:
                continue

            entry = self._format_commit_entry(commit)
            self._add_to_category(commit, entry, categories)

    def _format_commit_entry(self, commit) -> str:
        """Format a single commit as a changelog entry."""
        if commit.scope:
            return f"- **{commit.scope}:** {commit.description}"
        return f"- {commit.description}"

    def _add_to_category(self, commit, entry: str, categories: dict[str, list[str]]) -> None:
        """Add commit entry to appropriate category."""
        if commit.breaking:
            categories["Changed"].append(f"- ⚠️ **BREAKING:** {commit.description}")
        elif commit.type == "feat":
            categories["Added"].append(entry)
        elif commit.type == "fix":
            categories["Fixed"].append(entry)
        elif commit.type == "perf":
            categories["Changed"].append(f"- Performance: {commit.description}")
        elif commit.type == "security":
            categories["Security"].append(entry)
        elif commit.type in ("docs", "chore", "test"):
            pass  # Skip docs, chores, tests
        else:
            categories["Changed"].append(entry)

    def _build_release_content(self, categories: dict[str, list[str]]) -> str:
        """Build final release content from categorized entries."""
        sections = []
        for category, entries in categories.items():
            if entries:
                sections.append(f"### {category}\n" + "\n".join(entries))
        return "\n\n".join(sections) if sections else ""

    def write(self, content: str) -> None:
        """Write changelog content."""
        self.path.write_text(content, encoding="utf-8")

    def preview_release(
        self,
        version: str,
        commit_messages: Optional[list[str]] = None,
    ) -> str:
        """Preview what release section would look like."""
        date = datetime.now().strftime("%Y-%m-%d")
        unreleased = self.get_unreleased_section()

        release_content = self._format_release_content(
            unreleased,
            commit_messages or [],
        )

        if not release_content.strip():
            release_content = "_(No changes documented)_"

        return f"## [{version}] - {date}\n\n{release_content}"


def get_commits_since_tag(repo_path: Path, tag: str) -> list[str]:
    """Get commit messages since tag."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "log", f"{tag}..HEAD", "--pretty=format:%s"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return []
        return [m for m in result.stdout.strip().split("\n") if m]
    except Exception:
        return []

"""Git integration for version management.

Handles tagging, committing, clean checks, and signing.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from .manifest import GitConfig


class GitIntegrationError(Exception):
    """Git operation failed."""
    pass


class GitIntegration:
    """Git operations for version management."""

    def __init__(self, config: GitConfig, repo_path: Path = Path(".")):
        self.config = config
        self.repo_path = repo_path

    def _run(self, cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run git command in repo directory."""
        try:
            return subprocess.run(
                ["git"] + cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=check,
            )
        except subprocess.CalledProcessError as e:
            raise GitIntegrationError(f"Git failed: {' '.join(cmd)}\n{e.stderr}")
        except FileNotFoundError:
            raise GitIntegrationError("Git not found in PATH")

    def require_clean(self) -> bool:
        """Check if working directory is clean.

        Returns True if clean, raises GitIntegrationError if dirty.
        """
        result = self._run(["status", "--porcelain"], check=False)
        if result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            raise GitIntegrationError(
                f"Working directory not clean ({len(lines)} changes).\n"
                f"Use --allow-dirty to bypass, or commit changes first.\n"
                f"First 5: {', '.join(lines[:5])}"
            )
        return True

    def is_clean(self) -> bool:
        """Check if working directory is clean (no raise)."""
        result = self._run(["status", "--porcelain"], check=False)
        return not result.stdout.strip()

    def get_dirty_files(self) -> list[str]:
        """Get list of dirty files."""
        result = self._run(["status", "--porcelain"], check=False)
        if not result.stdout.strip():
            return []
        return [line[3:] for line in result.stdout.strip().split("\n")]

    def stage_files(self, files: list[Path]) -> None:
        """Stage files for commit."""
        if not files:
            return
        paths = [str(f) for f in files]
        self._run(["add"] + paths)

    def commit(self, version: str, files: Optional[list[Path]] = None) -> str:
        """Create commit with version bump.

        Returns commit hash.
        """
        message = self.config.commit_message.format(version=version)

        if files:
            self.stage_files(files)

        self._run(["commit", "-m", message])

        # Get commit hash
        result = self._run(["rev-parse", "HEAD"])
        return result.stdout.strip()

    def tag(self, version: str, annotate: bool = True, sign: bool = False) -> str:
        """Create git tag for version.

        Returns tag name.
        """
        tag_name = self.config.tag_format.format(version=version)

        cmd = ["tag"]
        if annotate:
            cmd.append("-a")
        if sign or self.config.sign_tag:
            cmd.append("-s")
        cmd.extend(["-m", self.config.tag_message.format(version=version)])
        cmd.append(tag_name)

        self._run(cmd)
        return tag_name

    def push(self, remote: str = "origin", follow_tags: bool = True) -> None:
        """Push commits and tags to remote."""
        if follow_tags:
            self._run(["push", "--follow-tags", remote])
        else:
            self._run(["push", remote])

    def tag_exists(self, version: str) -> bool:
        """Check if tag already exists."""
        tag_name = self.config.tag_format.format(version=version)
        result = self._run(["tag", "-l", tag_name], check=False)
        return tag_name in result.stdout

    def get_last_tag(self) -> Optional[str]:
        """Get most recent tag."""
        result = self._run(["describe", "--tags", "--abbrev=0"], check=False)
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    def get_commits_since(self, tag: str) -> list[str]:
        """Get commit messages since tag."""
        result = self._run(
            ["log", f"{tag}..HEAD", "--pretty=format:%s"],
            check=False,
        )
        if result.returncode != 0:
            return []
        return [m for m in result.stdout.strip().split("\n") if m]

    def get_current_branch(self) -> str:
        """Get current branch name."""
        result = self._run(["branch", "--show-current"])
        return result.stdout.strip()

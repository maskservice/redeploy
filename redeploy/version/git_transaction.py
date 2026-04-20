"""Extended transaction with Git integration.

Combines atomic file updates with git staging, commit, and tagging.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .git_integration import GitIntegration, GitIntegrationError
from .manifest import VersionManifest
from .transaction import VersionBumpTransaction, StagingResult


@dataclass
class GitTransactionResult:
    """Result of full version bump transaction with git."""

    version: str
    files_updated: int
    commit_hash: Optional[str] = None
    tag_name: Optional[str] = None
    pushed: bool = False


class GitVersionBumpTransaction(VersionBumpTransaction):
    """Version bump transaction with Git integration.

    Extends atomic file transaction with git commit and tagging.
    """

    def __init__(
        self,
        manifest: VersionManifest,
        new_version: str,
        repo_path: Path = Path("."),
        allow_dirty: bool = False,
    ):
        super().__init__(manifest, new_version)
        self.git = GitIntegration(manifest.git, repo_path)
        self.allow_dirty = allow_dirty
        self._touched_files: list[Path] = []

    def prepare(self) -> list[StagingResult]:
        """Stage file changes and validate git state."""
        # Check clean working directory
        if self.manifest.git.require_clean and not self.allow_dirty:
            try:
                self.git.require_clean()
            except GitIntegrationError as e:
                # Add context about what we're trying to do
                raise GitIntegrationError(f"{e}\n\nRun with --allow-dirty to bypass.")

        # Run normal file staging
        results = super().prepare()

        # Collect touched files (for git add)
        self._touched_files = [
            r.source.path for r in results
            if r.ok and r.temp_path is not None  # Skip optional not-found
        ]
        # Add manifest file itself
        manifest_path = Path(".redeploy/version.yaml")
        if manifest_path.exists():
            self._touched_files.append(manifest_path)

        return results

    def commit_and_tag(
        self,
        create_commit: bool = True,
        create_tag: bool = True,
        sign_tag: bool = False,
    ) -> GitTransactionResult:
        """Commit and tag after successful file update.

        Must be called after commit() applies file changes.
        """
        commit_hash = None
        tag_name = None

        if create_commit and self._touched_files:
            commit_hash = self.git.commit(self.new_version, self._touched_files)

        if create_tag:
            tag_name = self.git.tag(self.new_version, sign=sign_tag)

        return GitTransactionResult(
            version=self.new_version,
            files_updated=len(self._touched_files),
            commit_hash=commit_hash,
            tag_name=tag_name,
        )

    def push(self) -> None:
        """Push to origin."""
        self.git.push(follow_tags=True)

    def rollback(self) -> None:
        """Rollback file changes. Note: git operations are not rolled back."""
        super().rollback()
        # Note: If commit/tag was created, we don't auto-rollback git
        # User must handle manually or we provide separate git-rollback command

"""Conventional commits analyzer for automatic bump detection.

Parses commit messages since last tag to determine next version bump.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .manifest import CommitRules, CommitsConfig


@dataclass
class ConventionalCommit:
    """Parsed conventional commit."""

    type: str
    scope: Optional[str]
    description: str
    breaking: bool
    body: str
    raw: str


@dataclass
class BumpAnalysis:
    """Result of analyzing commits for bump decision."""

    bump_type: Optional[str]  # "major", "minor", "patch", or None
    commits_analyzed: int
    breaking_count: int
    feat_count: int
    fix_count: int
    other_count: int
    reason: str


def parse_conventional(message: str) -> Optional[ConventionalCommit]:
    """Parse a conventional commit message.

    Format: <type>[optional scope]: <description>

    Breaking change indicated by:
    - "!" after type/scope: "feat!: breaking change"
    - "BREAKING CHANGE:" in body
    """
    lines = message.split("\n")
    header = lines[0].strip()

    # Pattern: type(scope): description or type!: description or type(scope)!: description
    pattern = r"^(\w+)(?:\(([^)]+)\))?(!)?\s*:\s*(.+)$"
    match = re.match(pattern, header)

    if not match:
        return None

    commit_type, scope, breaking_mark, description = match.groups()
    breaking = breaking_mark == "!"

    # Check body for BREAKING CHANGE
    body = "\n".join(lines[1:])
    if "BREAKING CHANGE:" in body or "BREAKING-CHANGE:" in body:
        breaking = True

    return ConventionalCommit(
        type=commit_type,
        scope=scope,
        description=description,
        breaking=breaking,
        body=body,
        raw=message,
    )


def analyze_commits(
    since_tag: str,
    repo_path: Path = Path("."),
    config: Optional[CommitsConfig] = None,
) -> BumpAnalysis:
    """Analyze commits since tag to determine bump type.

    Args:
        since_tag: Git tag to compare against (e.g., "v1.0.0")
        repo_path: Path to git repository
        config: Commit analysis configuration

    Returns:
        BumpAnalysis with recommended bump type
    """
    if config is None:
        config = CommitsConfig()

    # Get commits since tag
    try:
        result = subprocess.run(
            ["git", "log", f"{since_tag}..HEAD", "--pretty=format:%s%n%b%n---COMMIT---"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return BumpAnalysis(
                bump_type=None,
                commits_analyzed=0,
                breaking_count=0,
                feat_count=0,
                fix_count=0,
                other_count=0,
                reason=f"Git error: {result.stderr}",
            )
    except FileNotFoundError:
        return BumpAnalysis(
            bump_type=None,
            commits_analyzed=0,
            breaking_count=0,
            feat_count=0,
            fix_count=0,
            other_count=0,
            reason="Git not available",
        )

    # Parse commits
    commit_blocks = result.stdout.split("\n---COMMIT---\n")
    commits = [parse_conventional(block) for block in commit_blocks if block.strip()]
    valid_commits = [c for c in commits if c is not None]

    # Analyze
    breaking_count = sum(1 for c in valid_commits if c.breaking)
    type_counts: dict[str, int] = {}
    for c in valid_commits:
        type_counts[c.type] = type_counts.get(c.type, 0) + 1

    feat_count = type_counts.get("feat", 0)
    fix_count = type_counts.get("fix", 0)
    other_count = len(valid_commits) - breaking_count - feat_count - fix_count

    # Determine bump type based on rules
    rules = config.rules
    bumps = []

    for commit in valid_commits:
        if commit.breaking:
            bumps.append(rules.breaking)
        elif commit.type in rules.model_dump():
            rule_value = getattr(rules, commit.type, "none")
            if rule_value != "none":
                bumps.append(rule_value)

    # Priority: major > minor > patch
    if "major" in bumps:
        return BumpAnalysis(
            bump_type="major",
            commits_analyzed=len(valid_commits),
            breaking_count=breaking_count,
            feat_count=feat_count,
            fix_count=fix_count,
            other_count=other_count,
            reason=f"{breaking_count} breaking change(s) found",
        )
    elif "minor" in bumps:
        return BumpAnalysis(
            bump_type="minor",
            commits_analyzed=len(valid_commits),
            breaking_count=breaking_count,
            feat_count=feat_count,
            fix_count=fix_count,
            other_count=other_count,
            reason=f"{feat_count} feature(s) found",
        )
    elif "patch" in bumps:
        return BumpAnalysis(
            bump_type="patch",
            commits_analyzed=len(valid_commits),
            breaking_count=breaking_count,
            feat_count=feat_count,
            fix_count=fix_count,
            other_count=other_count,
            reason=f"{fix_count} fix(es) found",
        )

    return BumpAnalysis(
        bump_type=None,
        commits_analyzed=len(valid_commits),
        breaking_count=breaking_count,
        feat_count=feat_count,
        fix_count=fix_count,
        other_count=other_count,
        reason="No bump-worthy commits found",
    )


def format_analysis_report(analysis: BumpAnalysis) -> str:
    """Format bump analysis as human-readable report."""
    lines = [
        f"Analyzed {analysis.commits_analyzed} commit(s)",
        f"  Breaking changes: {analysis.breaking_count}",
        f"  Features: {analysis.feat_count}",
        f"  Fixes: {analysis.fix_count}",
        f"  Other: {analysis.other_count}",
        "",
    ]

    if analysis.bump_type:
        lines.extend([
            f"Recommended bump: [bold]{analysis.bump_type}[/bold]",
            f"Reason: {analysis.reason}",
        ])
    else:
        lines.extend([
            "No bump recommended",
            f"Reason: {analysis.reason}",
        ])

    return "\n".join(lines)

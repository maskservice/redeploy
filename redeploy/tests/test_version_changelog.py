"""Tests for redeploy.version.commits and redeploy.version.changelog."""
from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from redeploy.version.commits import (
    ConventionalCommit,
    BumpAnalysis,
    parse_conventional,
    analyze_commits,
    format_analysis_report,
)
from redeploy.version.changelog import ChangelogManager, get_commits_since_tag
from redeploy.version.manifest import CommitsConfig, CommitRules


# ── parse_conventional ────────────────────────────────────────────────────────


class TestParseConventional:
    def test_simple_feat(self):
        c = parse_conventional("feat: add dark mode")
        assert c is not None
        assert c.type == "feat"
        assert c.scope is None
        assert c.description == "add dark mode"
        assert c.breaking is False

    def test_with_scope(self):
        c = parse_conventional("fix(auth): handle token expiry")
        assert c.type == "fix"
        assert c.scope == "auth"
        assert c.description == "handle token expiry"

    def test_breaking_bang(self):
        c = parse_conventional("feat!: remove legacy API")
        assert c.breaking is True
        assert c.type == "feat"

    def test_breaking_bang_with_scope(self):
        c = parse_conventional("refactor(api)!: rename endpoints")
        assert c.breaking is True
        assert c.scope == "api"

    def test_breaking_change_in_body(self):
        c = parse_conventional("feat: new auth system\n\nBREAKING CHANGE: old tokens invalid")
        assert c.breaking is True

    def test_breaking_change_hyphen_in_body(self):
        c = parse_conventional("feat: overhaul\n\nBREAKING-CHANGE: migration required")
        assert c.breaking is True

    def test_chore(self):
        c = parse_conventional("chore: update deps")
        assert c.type == "chore"
        assert c.breaking is False

    def test_docs(self):
        c = parse_conventional("docs(readme): update install instructions")
        assert c.type == "docs"
        assert c.scope == "readme"

    def test_non_conventional_returns_none(self):
        assert parse_conventional("update some stuff") is None
        assert parse_conventional("Merge branch 'main'") is None
        assert parse_conventional("") is None

    def test_multi_word_description(self):
        c = parse_conventional("feat: add user profile page with avatar upload")
        assert c.description == "add user profile page with avatar upload"

    def test_body_captured(self):
        c = parse_conventional("fix: memory leak\n\nDetails: freed buffer in loop")
        assert "Details" in c.body

    def test_raw_preserved(self):
        msg = "feat(ui): add button"
        c = parse_conventional(msg)
        assert c.raw == msg

    def test_perf_type(self):
        c = parse_conventional("perf(db): add index on created_at")
        assert c.type == "perf"

    def test_test_type(self):
        c = parse_conventional("test: add coverage for auth module")
        assert c.type == "test"


# ── analyze_commits ───────────────────────────────────────────────────────────


class TestAnalyzeCommits:
    def _mock_git(self, commits: list[str]):
        """Return a mock subprocess result with commits formatted as git log output."""
        output = "\n---COMMIT---\n".join(commits) + "\n---COMMIT---\n"
        result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=output, stderr=""
        )
        return result

    def test_feat_gives_minor(self, tmp_path):
        with patch("subprocess.run", return_value=self._mock_git(["feat: add user export"])):
            analysis = analyze_commits("v1.0.0", repo_path=tmp_path)
        assert analysis.bump_type == "minor"
        assert analysis.feat_count == 1

    def test_fix_gives_patch(self, tmp_path):
        with patch("subprocess.run", return_value=self._mock_git(["fix: handle null pointer"])):
            analysis = analyze_commits("v1.0.0", repo_path=tmp_path)
        assert analysis.bump_type == "patch"
        assert analysis.fix_count == 1

    def test_breaking_gives_major(self, tmp_path):
        with patch("subprocess.run", return_value=self._mock_git(["feat!: drop Python 3.9"])):
            analysis = analyze_commits("v1.0.0", repo_path=tmp_path)
        assert analysis.bump_type == "major"
        assert analysis.breaking_count == 1

    def test_major_wins_over_minor(self, tmp_path):
        with patch("subprocess.run", return_value=self._mock_git([
            "feat: add feature",
            "feat!: breaking change",
        ])):
            analysis = analyze_commits("v1.0.0", repo_path=tmp_path)
        assert analysis.bump_type == "major"

    def test_minor_wins_over_patch(self, tmp_path):
        with patch("subprocess.run", return_value=self._mock_git([
            "fix: typo",
            "feat: new endpoint",
        ])):
            analysis = analyze_commits("v1.0.0", repo_path=tmp_path)
        assert analysis.bump_type == "minor"

    def test_chore_no_bump(self, tmp_path):
        with patch("subprocess.run", return_value=self._mock_git([
            "chore: update deps",
            "docs: fix typo",
        ])):
            analysis = analyze_commits("v1.0.0", repo_path=tmp_path)
        assert analysis.bump_type is None
        assert "No bump" in analysis.reason

    def test_no_commits_no_bump(self, tmp_path):
        result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with patch("subprocess.run", return_value=result):
            analysis = analyze_commits("v1.0.0", repo_path=tmp_path)
        assert analysis.bump_type is None
        assert analysis.commits_analyzed == 0

    def test_git_error_returns_none_bump(self, tmp_path):
        result = subprocess.CompletedProcess(
            args=[], returncode=128, stdout="", stderr="fatal: no such ref"
        )
        with patch("subprocess.run", return_value=result):
            analysis = analyze_commits("v999.0.0", repo_path=tmp_path)
        assert analysis.bump_type is None
        assert "Git error" in analysis.reason

    def test_git_not_found_returns_gracefully(self, tmp_path):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            analysis = analyze_commits("v1.0.0", repo_path=tmp_path)
        assert analysis.bump_type is None
        assert "not available" in analysis.reason

    def test_commits_analyzed_count(self, tmp_path):
        with patch("subprocess.run", return_value=self._mock_git([
            "feat: a", "fix: b", "chore: c",
        ])):
            analysis = analyze_commits("v1.0.0", repo_path=tmp_path)
        assert analysis.commits_analyzed == 3

    def test_custom_config_changes_rules(self, tmp_path):
        config = CommitsConfig(
            analyze=True,
            rules=CommitRules(feat="patch"),  # feat → patch instead of minor
        )
        with patch("subprocess.run", return_value=self._mock_git(["feat: small thing"])):
            analysis = analyze_commits("v1.0.0", repo_path=tmp_path, config=config)
        assert analysis.bump_type == "patch"


# ── format_analysis_report ────────────────────────────────────────────────────


class TestFormatAnalysisReport:
    def test_report_with_bump(self):
        a = BumpAnalysis(bump_type="minor", commits_analyzed=5,
                         breaking_count=0, feat_count=2, fix_count=1,
                         other_count=2, reason="2 feature(s) found")
        report = format_analysis_report(a)
        assert "5" in report
        assert "minor" in report
        assert "2 feature" in report

    def test_report_no_bump(self):
        a = BumpAnalysis(bump_type=None, commits_analyzed=3,
                         breaking_count=0, feat_count=0, fix_count=0,
                         other_count=3, reason="No bump-worthy commits found")
        report = format_analysis_report(a)
        assert "No bump" in report
        assert "3" in report


# ── ChangelogManager ──────────────────────────────────────────────────────────


class TestChangelogManager:
    def test_exists_false_when_missing(self, tmp_path):
        cm = ChangelogManager(tmp_path / "CHANGELOG.md")
        assert cm.exists() is False

    def test_exists_true_when_present(self, tmp_path):
        p = tmp_path / "CHANGELOG.md"
        p.write_text("# Changelog\n")
        cm = ChangelogManager(p)
        assert cm.exists() is True

    def test_read_returns_default_template_when_missing(self, tmp_path):
        cm = ChangelogManager(tmp_path / "CHANGELOG.md")
        content = cm.read()
        assert "Unreleased" in content
        assert "Changelog" in content

    def test_read_returns_file_content(self, tmp_path):
        p = tmp_path / "CHANGELOG.md"
        p.write_text("# My Changelog\n\n## [Unreleased]\n")
        cm = ChangelogManager(p)
        assert "My Changelog" in cm.read()

    def test_write_creates_file(self, tmp_path):
        p = tmp_path / "CHANGELOG.md"
        cm = ChangelogManager(p)
        cm.write("# Test\n")
        assert p.read_text() == "# Test\n"

    def test_get_unreleased_section_empty(self, tmp_path):
        p = tmp_path / "CHANGELOG.md"
        # Only whitespace between [Unreleased] and next section → strip → ""
        p.write_text("# Changelog\n\n## [Unreleased]\n\n## [1.0.0] - 2024-01-01\n")
        cm = ChangelogManager(p)
        section = cm.get_unreleased_section()
        # After strip, section should have no user-written content (only possible header text)
        assert "Added" not in section
        assert "Fixed" not in section
        assert "feature" not in section.lower()

    def test_get_unreleased_section_with_content(self, tmp_path):
        p = tmp_path / "CHANGELOG.md"
        p.write_text("# Changelog\n\n## [Unreleased]\n\n### Added\n- New feature\n\n## [1.0.0]\n")
        cm = ChangelogManager(p)
        section = cm.get_unreleased_section()
        assert "Added" in section
        assert "New feature" in section

    def test_prepare_release_replaces_unreleased(self, tmp_path):
        p = tmp_path / "CHANGELOG.md"
        p.write_text("# Changelog\n\n## [Unreleased]\n\n### Added\n- Dark mode\n\n")
        cm = ChangelogManager(p)
        updated = cm.prepare_release("1.2.0", date="2024-06-01")
        assert "## [1.2.0] - 2024-06-01" in updated
        assert "## [Unreleased]" in updated  # new empty unreleased section
        assert "Dark mode" in updated

    def test_prepare_release_date_defaults_to_today(self, tmp_path):
        from datetime import datetime
        p = tmp_path / "CHANGELOG.md"
        p.write_text("# Changelog\n\n## [Unreleased]\n\n")
        cm = ChangelogManager(p)
        updated = cm.prepare_release("2.0.0")
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in updated

    def test_prepare_release_auto_categorize_from_commits(self, tmp_path):
        p = tmp_path / "CHANGELOG.md"
        p.write_text("# Changelog\n\n## [Unreleased]\n\n")
        cm = ChangelogManager(p)
        commits = ["feat: add export", "fix(auth): token bug", "chore: lint"]
        updated = cm.prepare_release("1.1.0", date="2024-01-01", commit_messages=commits)
        assert "Added" in updated
        assert "Fixed" in updated
        assert "add export" in updated

    def test_prepare_release_breaking_change_in_commits(self, tmp_path):
        p = tmp_path / "CHANGELOG.md"
        p.write_text("# Changelog\n\n## [Unreleased]\n\n")
        cm = ChangelogManager(p)
        commits = ["feat!: drop Python 3.9 support"]
        updated = cm.prepare_release("2.0.0", date="2024-01-01", commit_messages=commits)
        assert "BREAKING" in updated

    def test_prepare_release_no_commits_no_unreleased(self, tmp_path):
        p = tmp_path / "CHANGELOG.md"
        p.write_text("# Changelog\n\n## [Unreleased]\n\n")
        cm = ChangelogManager(p)
        updated = cm.prepare_release("1.0.1", date="2024-01-01", commit_messages=[])
        assert "## [1.0.1]" in updated

    def test_preview_release(self, tmp_path):
        p = tmp_path / "CHANGELOG.md"
        p.write_text("# Changelog\n\n## [Unreleased]\n\n### Added\n- A feature\n\n")
        cm = ChangelogManager(p)
        preview = cm.preview_release("1.5.0")
        assert "## [1.5.0]" in preview
        assert "A feature" in preview

    def test_preview_release_empty_shows_placeholder(self, tmp_path):
        p = tmp_path / "CHANGELOG.md"
        p.write_text("# Changelog\n\n## [Unreleased]\n\n")
        cm = ChangelogManager(p)
        preview = cm.preview_release("1.0.0")
        assert "No changes" in preview

    def test_scope_formatted_bold_in_release(self, tmp_path):
        p = tmp_path / "CHANGELOG.md"
        p.write_text("# Changelog\n\n## [Unreleased]\n\n")
        cm = ChangelogManager(p)
        commits = ["fix(auth): token expiry"]
        updated = cm.prepare_release("1.0.1", date="2024-01-01", commit_messages=commits)
        assert "auth" in updated


# ── get_commits_since_tag ─────────────────────────────────────────────────────


class TestGetCommitsSinceTag:
    def test_returns_commit_messages(self, tmp_path):
        result = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="feat: add feature\nfix: bug fix\n", stderr=""
        )
        with patch("subprocess.run", return_value=result):
            commits = get_commits_since_tag(tmp_path, "v1.0.0")
        assert "feat: add feature" in commits
        assert "fix: bug fix" in commits

    def test_returns_empty_on_git_error(self, tmp_path):
        result = subprocess.CompletedProcess(
            args=[], returncode=128, stdout="", stderr="fatal"
        )
        with patch("subprocess.run", return_value=result):
            commits = get_commits_since_tag(tmp_path, "v1.0.0")
        assert commits == []

    def test_returns_empty_on_exception(self, tmp_path):
        with patch("subprocess.run", side_effect=Exception("no git")):
            commits = get_commits_since_tag(tmp_path, "v1.0.0")
        assert commits == []

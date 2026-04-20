"""Tests for redeploy.version.git_integration and git_transaction."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from redeploy.version.git_integration import GitIntegration, GitIntegrationError
from redeploy.version.manifest import GitConfig, VersionManifest, SourceConfig


# ── helpers ───────────────────────────────────────────────────────────────────


def _config(**kw) -> GitConfig:
    defaults = dict(
        tag_format="v{version}",
        tag_message="Release {version}",
        commit_message="chore(release): {version}",
        sign_tag=False,
        require_clean=True,
    )
    defaults.update(kw)
    return GitConfig(**defaults)


def _ok(stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr=stderr)


def _fail(stdout: str = "", stderr: str = "error") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=1, stdout=stdout, stderr=stderr)


# ── GitIntegration._run ────────────────────────────────────────────────────────


class TestGitIntegrationRun:
    def test_success(self, tmp_path):
        gi = GitIntegration(_config(), repo_path=tmp_path)
        with patch("subprocess.run", return_value=_ok("main\n")) as mock_run:
            result = gi._run(["branch", "--show-current"])
        mock_run.assert_called_once()
        assert result.stdout == "main\n"

    def test_raises_on_called_process_error(self, tmp_path):
        gi = GitIntegration(_config(), repo_path=tmp_path)
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "git", stderr="fail")):
            with pytest.raises(GitIntegrationError, match="Git failed"):
                gi._run(["tag", "v1.0.0"])

    def test_raises_when_git_not_found(self, tmp_path):
        gi = GitIntegration(_config(), repo_path=tmp_path)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(GitIntegrationError, match="not found"):
                gi._run(["status"])

    def test_check_false_does_not_raise_on_nonzero(self, tmp_path):
        gi = GitIntegration(_config(), repo_path=tmp_path)
        with patch("subprocess.run", return_value=_fail("dirty\n")):
            result = gi._run(["status", "--porcelain"], check=False)
        assert result.returncode == 1


# ── require_clean / is_clean ──────────────────────────────────────────────────


class TestCleanState:
    def test_require_clean_passes_on_empty_output(self, tmp_path):
        gi = GitIntegration(_config(), repo_path=tmp_path)
        with patch("subprocess.run", return_value=_ok("")):
            assert gi.require_clean() is True

    def test_require_clean_raises_on_dirty(self, tmp_path):
        gi = GitIntegration(_config(), repo_path=tmp_path)
        with patch("subprocess.run", return_value=_ok(" M redeploy/cli.py\n")):
            with pytest.raises(GitIntegrationError, match="not clean"):
                gi.require_clean()

    def test_is_clean_true_when_empty(self, tmp_path):
        gi = GitIntegration(_config(), repo_path=tmp_path)
        with patch("subprocess.run", return_value=_ok("")):
            assert gi.is_clean() is True

    def test_is_clean_false_when_dirty(self, tmp_path):
        gi = GitIntegration(_config(), repo_path=tmp_path)
        with patch("subprocess.run", return_value=_ok(" M file.py\n")):
            assert gi.is_clean() is False

    def test_get_dirty_files_empty(self, tmp_path):
        gi = GitIntegration(_config(), repo_path=tmp_path)
        with patch("subprocess.run", return_value=_ok("")):
            assert gi.get_dirty_files() == []

    def test_get_dirty_files_returns_paths(self, tmp_path):
        gi = GitIntegration(_config(), repo_path=tmp_path)
        # git status --porcelain: "XY filename", line[3:] strips status prefix
        # stdout.strip() eats leading whitespace of whole string, so use "??" prefix
        with patch("subprocess.run", return_value=_ok("?? file.py\n?? other.py\n")):
            files = gi.get_dirty_files()
        assert any("file.py" in f for f in files)
        assert any("other.py" in f for f in files)


# ── commit ─────────────────────────────────────────────────────────────────────


class TestCommit:
    def test_commit_uses_message_format(self, tmp_path):
        gi = GitIntegration(_config(commit_message="bump: {version}"), repo_path=tmp_path)
        calls = []
        with patch("subprocess.run", side_effect=lambda cmd, **kw: (calls.append(cmd), _ok("abc123\n"))[1]):
            gi.commit("1.2.3")
        commit_call = next(c for c in calls if "commit" in c)
        assert "bump: 1.2.3" in commit_call

    def test_commit_returns_hash(self, tmp_path):
        gi = GitIntegration(_config(), repo_path=tmp_path)
        with patch("subprocess.run", return_value=_ok("abc1234\n")):
            h = gi.commit("1.0.0")
        assert h == "abc1234"

    def test_commit_stages_files(self, tmp_path):
        gi = GitIntegration(_config(), repo_path=tmp_path)
        version_file = tmp_path / "VERSION"
        calls = []
        with patch("subprocess.run", side_effect=lambda cmd, **kw: (calls.append(cmd), _ok("hash\n"))[1]):
            gi.commit("1.0.0", files=[version_file])
        add_call = next(c for c in calls if "add" in c)
        assert str(version_file) in add_call


# ── tag ───────────────────────────────────────────────────────────────────────


class TestTag:
    def test_tag_name_uses_format(self, tmp_path):
        gi = GitIntegration(_config(tag_format="release-{version}"), repo_path=tmp_path)
        calls = []
        with patch("subprocess.run", side_effect=lambda cmd, **kw: (calls.append(cmd), _ok())[1]):
            name = gi.tag("1.2.3")
        assert name == "release-1.2.3"
        tag_call = next(c for c in calls if "tag" in c)
        assert "release-1.2.3" in tag_call

    def test_tag_default_format_v_prefix(self, tmp_path):
        gi = GitIntegration(_config(), repo_path=tmp_path)
        with patch("subprocess.run", return_value=_ok()):
            name = gi.tag("2.0.0")
        assert name == "v2.0.0"

    def test_tag_with_sign(self, tmp_path):
        gi = GitIntegration(_config(sign_tag=True), repo_path=tmp_path)
        calls = []
        with patch("subprocess.run", side_effect=lambda cmd, **kw: (calls.append(cmd), _ok())[1]):
            gi.tag("1.0.0")
        tag_call = next(c for c in calls if "tag" in c)
        assert "-s" in tag_call

    def test_tag_without_sign(self, tmp_path):
        gi = GitIntegration(_config(sign_tag=False), repo_path=tmp_path)
        calls = []
        with patch("subprocess.run", side_effect=lambda cmd, **kw: (calls.append(cmd), _ok())[1]):
            gi.tag("1.0.0", sign=False)
        tag_call = next(c for c in calls if "tag" in c)
        assert "-s" not in tag_call

    def test_tag_exists_true(self, tmp_path):
        gi = GitIntegration(_config(), repo_path=tmp_path)
        with patch("subprocess.run", return_value=_ok("v1.0.0\n")):
            assert gi.tag_exists("1.0.0") is True

    def test_tag_exists_false(self, tmp_path):
        gi = GitIntegration(_config(), repo_path=tmp_path)
        with patch("subprocess.run", return_value=_ok("")):
            assert gi.tag_exists("1.0.0") is False


# ── push ──────────────────────────────────────────────────────────────────────


class TestPush:
    def test_push_with_follow_tags(self, tmp_path):
        gi = GitIntegration(_config(), repo_path=tmp_path)
        calls = []
        with patch("subprocess.run", side_effect=lambda cmd, **kw: (calls.append(cmd), _ok())[1]):
            gi.push(follow_tags=True)
        assert "--follow-tags" in calls[0]

    def test_push_without_follow_tags(self, tmp_path):
        gi = GitIntegration(_config(), repo_path=tmp_path)
        calls = []
        with patch("subprocess.run", side_effect=lambda cmd, **kw: (calls.append(cmd), _ok())[1]):
            gi.push(follow_tags=False)
        assert "--follow-tags" not in calls[0]


# ── get_last_tag / get_commits_since / get_current_branch ────────────────────


class TestQueryMethods:
    def test_get_last_tag(self, tmp_path):
        gi = GitIntegration(_config(), repo_path=tmp_path)
        with patch("subprocess.run", return_value=_ok("v1.5.0\n")):
            assert gi.get_last_tag() == "v1.5.0"

    def test_get_last_tag_none_when_no_tags(self, tmp_path):
        gi = GitIntegration(_config(), repo_path=tmp_path)
        result = subprocess.CompletedProcess(args=[], returncode=128, stdout="", stderr="")
        with patch("subprocess.run", return_value=result):
            assert gi.get_last_tag() is None

    def test_get_commits_since(self, tmp_path):
        gi = GitIntegration(_config(), repo_path=tmp_path)
        with patch("subprocess.run", return_value=_ok("feat: add x\nfix: bug\n")):
            commits = gi.get_commits_since("v1.0.0")
        assert "feat: add x" in commits
        assert "fix: bug" in commits

    def test_get_commits_since_empty(self, tmp_path):
        gi = GitIntegration(_config(), repo_path=tmp_path)
        result = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
        with patch("subprocess.run", return_value=result):
            assert gi.get_commits_since("v1.0.0") == []

    def test_get_current_branch(self, tmp_path):
        gi = GitIntegration(_config(), repo_path=tmp_path)
        with patch("subprocess.run", return_value=_ok("main\n")):
            assert gi.get_current_branch() == "main"


# ── GitVersionBumpTransaction ──────────────────────────────────────────────────


class TestGitVersionBumpTransaction:
    def _manifest(self, version: str, tmp_path: Path) -> VersionManifest:
        plain = tmp_path / "VERSION"
        plain.write_text(version + "\n")
        return VersionManifest(
            version=version,
            sources=[SourceConfig(path=plain, format="plain")],
            git=GitConfig(
                tag_format="v{version}",
                commit_message="chore(release): {version}",
                require_clean=False,
            ),
        )

    def test_prepare_stages_files(self, tmp_path):
        from redeploy.version.git_transaction import GitVersionBumpTransaction

        m = self._manifest("1.0.0", tmp_path)
        tx = GitVersionBumpTransaction(m, "1.0.1", repo_path=tmp_path, allow_dirty=True)
        with patch("subprocess.run", return_value=_ok("")):
            results = tx.prepare()
        assert all(r.ok for r in results)
        assert len(tx._touched_files) >= 1

    def test_prepare_fails_on_dirty_when_require_clean(self, tmp_path):
        from redeploy.version.git_transaction import GitVersionBumpTransaction

        m = self._manifest("1.0.0", tmp_path)
        m.git.require_clean = True
        tx = GitVersionBumpTransaction(m, "1.0.1", repo_path=tmp_path, allow_dirty=False)
        with patch("subprocess.run", return_value=_ok(" M file.py\n")):
            with pytest.raises(GitIntegrationError, match="not clean"):
                tx.prepare()

    def test_prepare_bypasses_dirty_with_allow_dirty(self, tmp_path):
        from redeploy.version.git_transaction import GitVersionBumpTransaction

        m = self._manifest("1.0.0", tmp_path)
        m.git.require_clean = True
        tx = GitVersionBumpTransaction(m, "1.0.1", repo_path=tmp_path, allow_dirty=True)
        with patch("subprocess.run", return_value=_ok("")):
            results = tx.prepare()
        assert all(r.ok for r in results)

    def test_commit_and_tag_returns_result(self, tmp_path):
        from redeploy.version.git_transaction import GitVersionBumpTransaction

        m = self._manifest("1.0.0", tmp_path)
        tx = GitVersionBumpTransaction(m, "1.0.1", repo_path=tmp_path, allow_dirty=True)

        with patch("subprocess.run", return_value=_ok("")):
            tx.prepare()
            tx.commit()

        with patch("subprocess.run", return_value=_ok("deadbeef\n")):
            result = tx.commit_and_tag(create_commit=True, create_tag=True)

        assert result.version == "1.0.1"
        assert result.tag_name == "v1.0.1"

    def test_rollback_cleans_staged_files(self, tmp_path):
        from redeploy.version.git_transaction import GitVersionBumpTransaction

        m = self._manifest("1.0.0", tmp_path)
        tx = GitVersionBumpTransaction(m, "1.0.1", repo_path=tmp_path, allow_dirty=True)
        with patch("subprocess.run", return_value=_ok("")):
            tx.prepare()
        tx.rollback()
        # Original file unchanged
        assert (tmp_path / "VERSION").read_text().strip() == "1.0.0"

    def test_push_calls_git_push(self, tmp_path):
        from redeploy.version.git_transaction import GitVersionBumpTransaction

        m = self._manifest("1.0.0", tmp_path)
        tx = GitVersionBumpTransaction(m, "1.0.1", repo_path=tmp_path, allow_dirty=True)
        calls = []
        with patch("subprocess.run", side_effect=lambda cmd, **kw: (calls.append(cmd), _ok())[1]):
            tx.push()
        assert any("push" in c for c in calls)

    def test_git_transaction_result_fields(self):
        from redeploy.version.git_transaction import GitTransactionResult

        r = GitTransactionResult(version="1.2.3", files_updated=3,
                                 commit_hash="abc", tag_name="v1.2.3")
        assert r.version == "1.2.3"
        assert r.files_updated == 3
        assert r.pushed is False

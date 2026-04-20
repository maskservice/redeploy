"""Unit tests for redeploy.ssh — no real SSH required."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from redeploy.ssh import RemoteProbe, SshClient, SshResult


# ── SshResult ─────────────────────────────────────────────────────────────────

def test_ssh_result_ok():
    assert SshResult(0, "out", "").ok is True
    assert SshResult(1, "", "err").ok is False


def test_ssh_result_success_alias():
    assert SshResult(0, "out", "").success is True
    assert SshResult(1, "", "err").success is False


def test_ssh_result_out_strips():
    r = SshResult(0, "  hello \n", "")
    assert r.out == "hello"


# ── SshClient local ───────────────────────────────────────────────────────────

def test_local_run_echo():
    c = SshClient("local")
    r = c.run("echo hello")
    assert r.ok
    assert "hello" in r.out


def test_local_is_reachable():
    c = SshClient("localhost")
    assert c.is_reachable()


# ── SshClient SSH opts ────────────────────────────────────────────────────────

def test_ssh_opts_with_key():
    c = SshClient("user@host", port=2222, key="/tmp/id_rsa")
    opts = c._ssh_opts()
    assert "-p" in opts
    assert "2222" in opts
    assert "-i" in opts
    assert "/tmp/id_rsa" in opts


def test_ssh_opts_no_key():
    c = SshClient("user@host", key=None)
    c._key_explicit = None
    with patch.object(SshClient, "_detect_ssh_key", return_value=None):
        opts = c._ssh_opts()
    assert "-i" not in opts


# ── SshClient remote run (mocked) ─────────────────────────────────────────────

@patch("redeploy.ssh.subprocess.run")
def test_run_success(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="pong\n", stderr="")
    c = SshClient("root@1.2.3.4", key="/tmp/k")
    r = c.run("echo pong")
    assert r.ok
    assert "pong" in r.stdout


@patch("redeploy.ssh.subprocess.run")
def test_run_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="fail")
    c = SshClient("root@1.2.3.4", key="/tmp/k")
    r = c.run("bad cmd")
    assert not r.ok
    assert r.stderr == "fail"


@patch("redeploy.ssh.subprocess.run")
def test_run_timeout(mock_run):
    import subprocess
    mock_run.side_effect = subprocess.TimeoutExpired("ssh", 5)
    c = SshClient("root@1.2.3.4", key="/tmp/k")
    r = c.run("sleep 100", timeout=1)
    assert not r.ok
    assert r.exit_code == 124


# ── RemoteProbe backwards compat ──────────────────────────────────────────────

def test_remote_probe_is_local():
    p = RemoteProbe("local")
    assert p.is_local


def test_remote_probe_not_local():
    p = RemoteProbe("root@1.2.3.4")
    assert not p.is_local


# ── version helpers ───────────────────────────────────────────────────────────

def test_check_version_match():
    from redeploy.version import check_version
    ok, detail = check_version("1.0.19", "1.0.19")
    assert ok
    assert "✓" in detail


def test_check_version_mismatch():
    from redeploy.version import check_version
    ok, detail = check_version("1.0.19", "1.0.18")
    assert not ok
    assert "MISMATCH" in detail


def test_check_version_no_local():
    from redeploy.version import check_version
    ok, detail = check_version(None, "1.0.19")
    assert ok   # skip when no local version


def test_read_local_version(tmp_path):
    from redeploy.version import read_local_version
    (tmp_path / "VERSION").write_text("2.0.0\n")
    v = read_local_version(tmp_path)
    assert v == "2.0.0"


# ── data_sync ─────────────────────────────────────────────────────────────────

def test_collect_sqlite_counts(tmp_path):
    import sqlite3
    from redeploy.data_sync import collect_sqlite_counts
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO items VALUES (1)")
    conn.execute("INSERT INTO items VALUES (2)")
    conn.commit()
    conn.close()
    counts = collect_sqlite_counts(tmp_path, [("test.db", ["items"])])
    assert counts["items"] == 2


def test_collect_sqlite_missing_db(tmp_path):
    from redeploy.data_sync import collect_sqlite_counts
    counts = collect_sqlite_counts(tmp_path, [("nonexistent.db", ["items"])])
    assert counts == {}


# ── SshClient.put_file ────────────────────────────────────────────────────────


class TestPutFile:
    def test_local_writes_file(self, tmp_path):
        client = SshClient("local")
        target = str(tmp_path / "sub" / "config.env")
        result = client.put_file("KEY=VALUE\n", target)
        assert result.ok
        from pathlib import Path
        assert Path(target).read_text() == "KEY=VALUE\n"

    def test_local_creates_parent_dirs(self, tmp_path):
        client = SshClient("local")
        target = str(tmp_path / "a" / "b" / "c" / "file.txt")
        result = client.put_file("hello", target)
        assert result.ok
        from pathlib import Path
        assert Path(target).exists()

    def test_local_applies_chmod(self, tmp_path):
        import os
        client = SshClient("local")
        target = str(tmp_path / "secret.env")
        client.put_file("SECRET=1\n", target, mode="0600")
        assert (os.stat(target).st_mode & 0o777) == 0o600

    def test_local_write_error_returns_failure(self, tmp_path):
        client = SshClient("local")
        # directory as target — write_text will fail
        result = client.put_file("data", str(tmp_path))
        assert not result.ok
        assert result.exit_code != 0

    def test_remote_calls_ssh(self):
        from unittest.mock import patch, MagicMock
        client = SshClient("root@10.0.0.1")
        client._key_explicit = "/tmp/key"
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        mock_proc.stderr = ""
        with patch("redeploy.ssh.subprocess.run", return_value=mock_proc) as mock_run:
            result = client.put_file("MY_VAR=1\n", "/remote/path/.env")
        assert result.ok
        called_args = mock_run.call_args
        cmd = called_args[0][0]
        assert "ssh" in cmd[0]
        assert "/remote/path/.env" in " ".join(cmd)

    def test_remote_failure_returned(self):
        from unittest.mock import patch, MagicMock
        client = SshClient("root@10.0.0.1")
        client._key_explicit = "/tmp/key"
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        mock_proc.stderr = "Permission denied"
        with patch("redeploy.ssh.subprocess.run", return_value=mock_proc):
            result = client.put_file("data", "/root/.env")
        assert not result.ok

    def test_remote_exception_returns_failure(self):
        from unittest.mock import patch
        client = SshClient("root@10.0.0.1")
        client._key_explicit = "/tmp/key"
        with patch("redeploy.ssh.subprocess.run", side_effect=Exception("timeout")):
            result = client.put_file("data", "/root/.env")
        assert not result.ok
        assert "timeout" in result.stderr


# ── verify ────────────────────────────────────────────────────────────────────

def test_verify_context_pass():
    from redeploy.verify import VerifyContext
    ctx = VerifyContext("test")
    ctx.add_pass("docker running")
    assert ctx.passed == 1
    assert ctx.failed == 0
    assert ctx.ok


def test_verify_context_fail():
    from redeploy.verify import VerifyContext
    ctx = VerifyContext("test")
    ctx.add_fail("backend health", "HTTP 502")
    assert ctx.failed == 1
    assert not ctx.ok
    assert "backend health" in ctx.summary()


def test_verify_data_integrity_ok():
    from redeploy.verify import VerifyContext, verify_data_integrity
    ctx = VerifyContext("test")
    verify_data_integrity(ctx, {"users": 10}, {"users": 10})
    assert ctx.passed == 1
    assert ctx.failed == 0


def test_verify_data_integrity_mismatch():
    from redeploy.verify import VerifyContext, verify_data_integrity
    ctx = VerifyContext("test")
    verify_data_integrity(ctx, {"users": 10}, {"users": 5})
    assert ctx.failed == 1

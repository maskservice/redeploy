"""Tests for version.py — read_local_version, read_remote_version,
check_version, check_version_http."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

import pytest

from redeploy.version import (
    check_version,
    check_version_http,
    read_local_version,
    read_remote_version,
)


# ── read_local_version ────────────────────────────────────────────────────────


class TestReadLocalVersion:
    def test_reads_app_subdir_version(self, tmp_path):
        app_dir = tmp_path / "myapp"
        app_dir.mkdir()
        (app_dir / "VERSION").write_text("1.0.20\n")
        assert read_local_version(tmp_path, app="myapp") == "1.0.20"

    def test_reads_root_version_fallback(self, tmp_path):
        (tmp_path / "VERSION").write_text("2.0.0")
        assert read_local_version(tmp_path, app="missing") == "2.0.0"

    def test_strips_whitespace(self, tmp_path):
        (tmp_path / "VERSION").write_text("  1.2.3  \n")
        assert read_local_version(tmp_path, app="x") == "1.2.3"

    def test_returns_none_when_missing(self, tmp_path):
        assert read_local_version(tmp_path, app="x") is None

    def test_returns_none_for_empty_version(self, tmp_path):
        (tmp_path / "VERSION").write_text("   \n")
        assert read_local_version(tmp_path, app="x") is None

    def test_app_subdir_takes_priority(self, tmp_path):
        (tmp_path / "VERSION").write_text("root")
        app_dir = tmp_path / "myapp"
        app_dir.mkdir()
        (app_dir / "VERSION").write_text("subdir")
        assert read_local_version(tmp_path, app="myapp") == "subdir"


# ── read_remote_version ───────────────────────────────────────────────────────


class TestReadRemoteVersion:
    def _remote(self, responses: dict[str, tuple[bool, str]]):
        r = MagicMock()
        def _run(cmd, timeout=30):
            for key, (ok, out) in responses.items():
                if key in cmd:
                    res = MagicMock()
                    res.success = ok
                    res.stdout = out
                    return res
            res = MagicMock()
            res.success = False
            res.stdout = ""
            return res
        r.run = _run
        return r

    def test_reads_app_subdir_path(self):
        remote = self._remote({"myapp/VERSION": (True, "1.0.20\n")})
        assert read_remote_version(remote, "~/deploy", app="myapp") == "1.0.20"

    def test_reads_root_path_fallback(self):
        remote = self._remote({
            "myapp/VERSION": (False, ""),
            "~/deploy/VERSION": (True, "1.0.19"),
        })
        assert read_remote_version(remote, "~/deploy", app="myapp") == "1.0.19"

    def test_strips_whitespace(self):
        remote = self._remote({"app/VERSION": (True, "  2.0.0  \n")})
        assert read_remote_version(remote, "~", app="app") == "2.0.0"

    def test_returns_none_when_not_found(self):
        remote = self._remote({})
        assert read_remote_version(remote, "~/deploy") is None


# ── check_version ─────────────────────────────────────────────────────────────


class TestCheckVersion:
    def test_match(self):
        ok, detail = check_version("1.0.20", "1.0.20")
        assert ok is True
        assert "✓" in detail

    def test_mismatch(self):
        ok, detail = check_version("1.0.20", "1.0.19")
        assert ok is False
        assert "MISMATCH" in detail
        assert "1.0.20" in detail
        assert "1.0.19" in detail

    def test_local_none_returns_true(self):
        ok, detail = check_version(None, "1.0.20")
        assert ok is True
        assert "skip" in detail.lower()

    def test_remote_none_returns_false(self):
        ok, detail = check_version("1.0.20", None)
        assert ok is False
        assert "1.0.20" in detail

    def test_both_none_local_wins(self):
        ok, detail = check_version(None, None)
        assert ok is True   # local None → skip


# ── check_version_http ────────────────────────────────────────────────────────


def _mock_urlopen(payload: dict, status: int = 200):
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestCheckVersionHttp:
    def _payload(self, match=True, expected="1.0.20", mismatches=None, versions=None):
        return {
            "match": match,
            "expected_version": expected,
            "mismatches": mismatches or [],
            "versions": versions or {"backend": {"version": expected}},
        }

    def test_success_match(self):
        payload = self._payload(match=True, expected="1.0.20")
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(payload)):
            ok, detail, data = check_version_http("http://localhost", "1.0.20")
        assert ok is True
        assert "1.0.20" in detail
        assert "✓" in detail

    def test_mismatch_in_api(self):
        payload = self._payload(match=False, expected="1.0.19",
                                mismatches=["backend 1.0.19 ≠ 1.0.20"])
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(payload)):
            ok, detail, data = check_version_http("http://localhost", "1.0.20")
        assert ok is False
        assert "MISMATCH" in detail

    def test_expected_version_mismatch(self):
        # API reports 1.0.19 but we expect 1.0.20
        payload = self._payload(match=True, expected="1.0.19")
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(payload)):
            ok, detail, _ = check_version_http("http://localhost", expected_version="1.0.20")
        assert ok is False
        assert "1.0.20" in detail

    def test_http_error(self):
        with patch("urllib.request.urlopen",
                   side_effect=HTTPError("url", 503, "Service Unavailable", {}, None)):
            ok, detail, data = check_version_http("http://localhost")
        assert ok is False
        assert "503" in detail
        assert data == {}

    def test_connection_error(self):
        with patch("urllib.request.urlopen",
                   side_effect=Exception("Connection refused")):
            ok, detail, data = check_version_http("http://localhost")
        assert ok is False
        assert "unreachable" in detail.lower()
        assert data == {}

    def test_no_expected_version_passed(self):
        payload = self._payload(match=True, expected="1.0.20")
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(payload)):
            ok, detail, _ = check_version_http("http://localhost")
        assert ok is True

    def test_payload_returned(self):
        payload = self._payload(match=True)
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(payload)):
            _, _, data = check_version_http("http://localhost")
        assert data["match"] is True
        assert "versions" in data

    def test_trailing_slash_stripped_in_url(self):
        payload = self._payload(match=True)
        called_url = []

        def _fake_open(req, timeout=10):
            called_url.append(req.full_url)
            return _mock_urlopen(payload)

        with patch("urllib.request.urlopen", side_effect=_fake_open):
            check_version_http("http://localhost/")

        assert called_url[0].endswith("/api/v3/version/check")
        assert "//" not in called_url[0].replace("http://", "")

    def test_versions_in_summary(self):
        payload = self._payload(
            match=True, expected="1.0.20",
            versions={"backend": {"version": "1.0.20"}, "frontend": {"version": "1.0.20"}},
        )
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(payload)):
            _, detail, _ = check_version_http("http://localhost")
        assert "backend" in detail
        assert "frontend" in detail

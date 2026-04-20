"""Version utilities — moved from deploy/core/version.py.

Used by both deploy/ and redeploy/.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional


def read_local_version(workspace_root: Path, app: str = "c2004") -> Optional[str]:
    """Read VERSION file from local workspace."""
    for candidate in [
        workspace_root / app / "VERSION",
        workspace_root / "VERSION",
    ]:
        if candidate.exists():
            v = candidate.read_text().strip()
            if v:
                return v
    return None


def read_remote_version(remote, remote_dir: str, app: str = "c2004") -> Optional[str]:
    """Read VERSION file from remote device via SSH.

    *remote* can be any object with a ``.run(cmd) -> result`` method where
    ``result.success`` and ``result.stdout`` are available (SshClient, RemoteProbe,
    RemoteExecutor all qualify).
    """
    for path in [f"{remote_dir}/{app}/VERSION", f"{remote_dir}/VERSION"]:
        r = remote.run(f"cat {path} 2>/dev/null")
        if r.success and r.stdout.strip():
            return r.stdout.strip()
    return None


def check_version(local: Optional[str], remote: Optional[str]) -> tuple[bool, str]:
    """Compare local vs remote version string. Returns (match, detail_line)."""
    if local is None:
        return True, "local VERSION not found (skip)"
    if remote is None:
        return False, f"remote VERSION not found (expected {local})"
    match = local == remote
    detail = f"local={local} remote={remote} {'✓' if match else '✗ MISMATCH'}"
    return match, detail


def check_version_http(
    base_url: str,
    expected_version: Optional[str] = None,
    timeout: int = 10,
    endpoint: str = "/api/v3/version/check",
) -> tuple[bool, str, dict[str, Any]]:
    """Call *endpoint* on a running service (default: ``/api/v3/version/check``).

    Returns ``(ok, summary_line, full_payload)``.
    Compares all service versions (backend/frontend/firmware) and optionally
    checks they match *expected_version*.
    """
    url = base_url.rstrip("/") + "/" + endpoint.lstrip("/")
    try:
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "curl/7.88.1",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload: dict[str, Any] = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code} from {url}", {}
    except Exception as exc:
        return False, f"unreachable: {exc}", {}

    match: bool = payload.get("match", False)
    reported_version: Optional[str] = payload.get("expected_version")
    mismatches: list[str] = payload.get("mismatches", [])
    versions: dict[str, Any] = payload.get("versions", {})

    svc_summary = ", ".join(
        f"{svc}={info.get('version', '?')}"
        for svc, info in versions.items()
    )

    if expected_version and reported_version and reported_version != expected_version:
        match = False
        mismatches = [f"expected {expected_version} but API reports {reported_version}"] + mismatches

    if match:
        detail = f"all services {reported_version} ✓ ({svc_summary})"
    else:
        detail = f"MISMATCH — {'; '.join(mismatches)} ({svc_summary})"

    return match, detail, payload

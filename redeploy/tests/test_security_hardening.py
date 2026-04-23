"""Security hardening tests for command construction and MCP guards."""
from __future__ import annotations

import io
from unittest.mock import patch

import pytest
from rich.console import Console

from redeploy.config_apply.handlers.display import apply_display_transform
from redeploy.detect.probes import probe_k3s_services


class _Result:
    def __init__(self, ok: bool = True, out: str = ""):
        self.ok = ok
        self.out = out


class _Probe:
    def __init__(self):
        self.commands: list[str] = []

    def run(self, cmd: str):
        self.commands.append(cmd)
        if cmd.startswith("cat "):
            return _Result(ok=False, out="")
        return _Result(ok=True, out="")


def test_apply_display_transform_rejects_unsafe_output_name():
    probe = _Probe()
    console = Console(file=io.StringIO(), force_terminal=False)

    with pytest.raises(ValueError, match="Unsafe display output name"):
        apply_display_transform(
            console,
            probe,
            "DSI-2; rm -rf /",
            "270",
        )


def test_apply_display_transform_rejects_unsupported_transform():
    probe = _Probe()
    console = Console(file=io.StringIO(), force_terminal=False)

    with pytest.raises(ValueError, match="Unsupported transform"):
        apply_display_transform(console, probe, "DSI-2", "drop-table")


def test_probe_k3s_services_skips_unsafe_namespace():
    commands: list[str] = []

    class Probe:
        def run(self, cmd: str):
            commands.append(cmd)
            return _Result(ok=True, out="pod-a|1/1|Running")

    services = probe_k3s_services(Probe(), ["default; rm -rf /", "c2004"])

    assert len(services) == 1
    assert services[0].name == "pod-a"
    assert all("default; rm -rf /" not in c for c in commands)


def test_exec_ssh_rejects_unsafe_command_tokens(monkeypatch):
    pytest.importorskip("mcp.server.fastmcp")
    from redeploy import mcp_server

    with patch("redeploy.mcp_server.subprocess.run") as run:
        result = mcp_server.exec_ssh("pi@192.168.1.10", "echo ok && whoami")

    assert result["success"] is False
    assert "Unsafe command token" in result["stderr"]
    run.assert_not_called()


def test_exec_ssh_allows_override_for_trusted_environments(monkeypatch):
    pytest.importorskip("mcp.server.fastmcp")
    from redeploy import mcp_server

    monkeypatch.setenv("REDEPLOY_MCP_ALLOW_UNSAFE_SSH", "1")

    class Proc:
        returncode = 0
        stdout = "ok"
        stderr = ""

    with patch("redeploy.mcp_server.subprocess.run", return_value=Proc()):
        result = mcp_server.exec_ssh("pi@192.168.1.10", "echo ok && whoami")

    assert result["success"] is True

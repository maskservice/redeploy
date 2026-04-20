"""Tests for parse.py — SSH output parsers."""
from __future__ import annotations

import pytest

from redeploy.parse import (
    parse_container_line,
    parse_diagnostics,
    parse_docker_ps,
    parse_health_info,
    parse_system_info,
)


# ── parse_docker_ps ───────────────────────────────────────────────────────────


class TestParseDockerPs:
    def _out(self):
        return (
            "c2004-backend|ghcr.io/maskservice/c2004:1.0.20|Up 3 hours (healthy)|0.0.0.0:8000->8000/tcp|running\n"
            "traefik|traefik:v2.10|Up 3 hours|0.0.0.0:80->80/tcp,0.0.0.0:443->443/tcp|running\n"
        )

    def test_returns_list(self):
        result = parse_docker_ps(self._out())
        assert isinstance(result, list)

    def test_count(self):
        result = parse_docker_ps(self._out())
        assert len(result) == 2

    def test_name(self):
        result = parse_docker_ps(self._out())
        assert result[0]["name"] == "c2004-backend"

    def test_image(self):
        result = parse_docker_ps(self._out())
        assert result[0]["image"] == "ghcr.io/maskservice/c2004:1.0.20"

    def test_status(self):
        result = parse_docker_ps(self._out())
        assert "healthy" in result[0]["status"]

    def test_state(self):
        result = parse_docker_ps(self._out())
        assert result[0]["state"] == "running"

    def test_empty_output(self):
        assert parse_docker_ps("") == []

    def test_no_prefix_line_skipped(self):
        result = parse_docker_ps("__NO_CONTAINERS__\n")
        assert result == []

    def test_partial_line_two_parts(self):
        result = parse_docker_ps("myapp|myimage\n")
        assert len(result) == 1
        assert result[0]["name"] == "myapp"
        assert result[0]["image"] == "myimage"

    def test_multiple_containers(self):
        out = "\n".join(f"app{i}|img{i}|Up|ports|running" for i in range(5))
        result = parse_docker_ps(out)
        assert len(result) == 5


# ── parse_container_line ──────────────────────────────────────────────────────


class TestParseContainerLine:
    def test_full_line(self):
        r = parse_container_line("myapp|Up 2 hours|nginx:latest")
        assert r["name"] == "myapp"
        assert r["status"] == "Up 2 hours"
        assert r["image"] == "nginx:latest"

    def test_two_parts(self):
        r = parse_container_line("myapp|running")
        assert r["name"] == "myapp"
        assert r["status"] == "running"
        assert r["image"] == ""

    def test_single_part_returns_none(self):
        assert parse_container_line("justname") is None

    def test_empty_string_returns_none(self):
        assert parse_container_line("") is None


# ── parse_system_info ─────────────────────────────────────────────────────────


class TestParseSystemInfo:
    def _out(self):
        return (
            "HOSTNAME:myserver\n"
            "UPTIME: 5 days, 3:12\n"
            "LOAD:0.12 0.08 0.05\n"
            "KERNEL:6.1.0-amd64\n"
            "CPU_CORES:4\n"
            "DISK:/ 50G 20G 28G 42%\n"
            "MEM: total 8G used 3G free 5G avail 4G\n"
        )

    def test_hostname(self):
        info = parse_system_info(self._out())
        assert info["hostname"] == "myserver"

    def test_uptime(self):
        info = parse_system_info(self._out())
        assert "5 days" in info["uptime"]

    def test_load(self):
        info = parse_system_info(self._out())
        assert "0.12" in info["load"]

    def test_kernel(self):
        info = parse_system_info(self._out())
        assert info["kernel"] == "6.1.0-amd64"

    def test_cpu_cores(self):
        info = parse_system_info(self._out())
        assert info["cpu_cores"] == "4"

    def test_disk_parsed(self):
        info = parse_system_info(self._out())
        assert "disk" in info
        assert info["disk"]["use_pct"] == "42%"

    def test_memory_parsed(self):
        info = parse_system_info(self._out())
        assert "memory" in info
        assert info["memory"]["total"] == "8G"

    def test_empty_output(self):
        info = parse_system_info("")
        assert info == {}

    def test_unknown_lines_ignored(self):
        info = parse_system_info("RANDOM:stuff\nHOSTNAME:ok\n")
        assert info["hostname"] == "ok"
        assert "random" not in info


# ── parse_diagnostics ─────────────────────────────────────────────────────────


class TestParseDiagnostics:
    def _diag(self):
        return (
            "===SYSTEM===\n"
            "HOSTNAME:vps-prod\n"
            "UPTIME:10 days\n"
            "LOAD:0.5\n"
            "DISK:/ 100G 40G 55G 42%\n"
            "===CONTAINERS===\n"
            "c2004-backend|Up|c2004:1.0.20\n"
            "traefik|Up|traefik:v2\n"
            "===GIT===\n"
            "BRANCH:main\n"
            "COMMIT:abc1234\n"
            "DIRTY:false\n"
            "===HEALTH===\n"
            "200\n"
            "===NETWORK===\n"
            "PORTS:5\n"
        )

    def test_system_hostname(self):
        r = parse_diagnostics(self._diag())
        assert r["system"]["hostname"] == "vps-prod"

    def test_system_disk(self):
        r = parse_diagnostics(self._diag())
        assert "disk" in r["system"]
        assert r["system"]["disk"]["use_pct"] == "42%"

    def test_containers_count(self):
        r = parse_diagnostics(self._diag())
        assert len(r["containers"]) == 2

    def test_container_names(self):
        r = parse_diagnostics(self._diag())
        names = [c["name"] for c in r["containers"]]
        assert "c2004-backend" in names
        assert "traefik" in names

    def test_git_branch(self):
        r = parse_diagnostics(self._diag())
        assert r["git"]["branch"] == "main"

    def test_git_commit(self):
        r = parse_diagnostics(self._diag())
        assert r["git"]["commit"] == "abc1234"

    def test_health_code(self):
        r = parse_diagnostics(self._diag())
        assert r["health_code"] == 200

    def test_listening_ports(self):
        r = parse_diagnostics(self._diag())
        assert r["listening_ports"] == 5

    def test_empty_output_defaults(self):
        r = parse_diagnostics("")
        assert r["system"] == {}
        assert r["containers"] == []
        assert r["health_code"] == 0

    def test_no_prefix_lines_skipped(self):
        r = parse_diagnostics("__NO_CONTAINERS__\n===SYSTEM===\nHOSTNAME:ok\n")
        assert r["system"]["hostname"] == "ok"

    def test_invalid_health_code_ignored(self):
        r = parse_diagnostics("===HEALTH===\nnot_a_number\n")
        assert r["health_code"] == 0

    def test_docker_section_alias(self):
        r = parse_diagnostics("===DOCKER===\napp|Up|img\n")
        assert len(r["containers"]) == 1


# ── parse_health_info ─────────────────────────────────────────────────────────


class TestParseHealthInfo:
    def _out(self):
        return (
            "HOSTNAME:vps-prod\n"
            "UPTIME:5 days\n"
            "HEALTH:200\n"
            "DISK:42%\n"
            "LOAD:0.15\n"
        )

    def test_hostname(self):
        info = parse_health_info(self._out())
        assert info["hostname"] == "vps-prod"

    def test_uptime(self):
        info = parse_health_info(self._out())
        assert "5 days" in info["uptime"]

    def test_health_code(self):
        info = parse_health_info(self._out())
        assert info["health"] == 200

    def test_disk(self):
        info = parse_health_info(self._out())
        assert "42%" in info["disk_pct"]

    def test_load(self):
        info = parse_health_info(self._out())
        assert "0.15" in info["load"]

    def test_empty_output_defaults(self):
        info = parse_health_info("")
        assert info["health"] == 0
        assert info["hostname"] == ""

    def test_invalid_health_ignored(self):
        info = parse_health_info("HEALTH:not_int\n")
        assert info["health"] == 0

    def test_unknown_lines_ignored(self):
        info = parse_health_info("RANDOM:val\nHOSTNAME:ok\n")
        assert info["hostname"] == "ok"

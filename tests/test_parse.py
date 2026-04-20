"""Tests for redeploy.parse — SSH output parsers."""
import pytest
from redeploy.parse import (
    parse_docker_ps,
    parse_container_line,
    parse_system_info,
    parse_diagnostics,
    parse_health_info,
)


# ── parse_docker_ps ───────────────────────────────────────────────────────────

def test_parse_docker_ps_full_format():
    output = "web|nginx:latest|Up 2 hours|0.0.0.0:80->80/tcp|running"
    result = parse_docker_ps(output)
    assert len(result) == 1
    assert result[0] == {"name": "web", "image": "nginx:latest", "status": "Up 2 hours",
                         "ports": "0.0.0.0:80->80/tcp", "state": "running"}


def test_parse_docker_ps_partial_format():
    output = "api|python:3.11|Up 1 hour"
    result = parse_docker_ps(output)
    assert result[0]["name"] == "api"
    assert result[0]["ports"] == ""


def test_parse_docker_ps_skips_empty_lines():
    output = "web|nginx|Up|\n\n  \ndb|postgres|Up|"
    result = parse_docker_ps(output)
    assert len(result) == 2


def test_parse_docker_ps_skips_no_containers_marker():
    result = parse_docker_ps("__NO_CONTAINERS__")
    assert result == []


def test_parse_docker_ps_empty():
    assert parse_docker_ps("") == []


# ── parse_container_line ──────────────────────────────────────────────────────

def test_parse_container_line_full():
    c = parse_container_line("web|running|nginx:latest")
    assert c == {"name": "web", "status": "running", "image": "nginx:latest"}


def test_parse_container_line_no_image():
    c = parse_container_line("web|running")
    assert c["image"] == ""


def test_parse_container_line_invalid_returns_none():
    assert parse_container_line("nopipe") is None


# ── parse_system_info ─────────────────────────────────────────────────────────

def test_parse_system_info_basic():
    output = "HOSTNAME:myhost\nUPTIME:up 2 days\nLOAD:0.10 0.05 0.01 1/120 12345"
    info = parse_system_info(output)
    assert info["hostname"] == "myhost"
    assert info["uptime"] == "up 2 days"
    assert info["load"] == "0.10 0.05 0.01 1/120 12345"


def test_parse_system_info_disk():
    output = "DISK:/dev/sda1 50G 30G 20G 60% /"
    info = parse_system_info(output)
    assert info["disk"]["use_pct"] == "60%"
    assert info["disk"]["avail"] == "20G"


def test_parse_system_info_memory():
    output = "MEM:Mem: 8.0G 4.0G 1.0G 0 2.5G 3.0G 3.2G"
    info = parse_system_info(output)
    assert info["memory"]["total"] == "8.0G"
    assert info["memory"]["used"] == "4.0G"


def test_parse_system_info_unknown_lines_ignored():
    info = parse_system_info("UNKNOWN:stuff\nHOSTNAME:ok")
    assert "unknown" not in info
    assert info["hostname"] == "ok"


# ── parse_diagnostics ─────────────────────────────────────────────────────────

DIAG_OUTPUT = """===SYSTEM===
HOSTNAME:remotehost
UPTIME:up 1 day
LOAD:0.05 0.03 0.01 1/50 999
===CONTAINERS===
web|Up 3 hours|nginx:latest
===GIT===
BRANCH:main
COMMIT:abc1234
DIRTY:0
===HEALTH===
200
===NETWORK===
PORTS:3
"""


def test_parse_diagnostics_sections():
    result = parse_diagnostics(DIAG_OUTPUT)
    assert result["system"]["hostname"] == "remotehost"
    assert len(result["containers"]) == 1
    assert result["containers"][0]["name"] == "web"
    assert result["git"]["branch"] == "main"
    assert result["git"]["commit"] == "abc1234"
    assert result["health_code"] == 200
    assert result["listening_ports"] == 3


def test_parse_diagnostics_empty():
    result = parse_diagnostics("")
    assert result["containers"] == []
    assert result["health_code"] == 0


def test_parse_diagnostics_docker_section_alias():
    """===DOCKER=== is treated same as ===CONTAINERS==="""
    output = "===DOCKER===\napi|Up|python:3.11"
    result = parse_diagnostics(output)
    assert result["containers"][0]["name"] == "api"


def test_parse_diagnostics_skips_no_markers():
    output = "===CONTAINERS===\n__NO_CONTAINERS__\n"
    result = parse_diagnostics(output)
    assert result["containers"] == []


# ── parse_health_info ─────────────────────────────────────────────────────────

def test_parse_health_info_full():
    output = "HOSTNAME:mybox\nUPTIME:up 5h\nHEALTH:200\nDISK:45%\nLOAD:0.12"
    info = parse_health_info(output)
    assert info["hostname"] == "mybox"
    assert info["health"] == 200
    assert info["disk_pct"] == "45%"
    assert info["load"] == "0.12"


def test_parse_health_info_invalid_health_code():
    info = parse_health_info("HEALTH:notanumber")
    assert info["health"] == 0


def test_parse_health_info_empty():
    info = parse_health_info("")
    assert info == {"hostname": "", "uptime": "", "health": 0, "disk_pct": "", "load": ""}

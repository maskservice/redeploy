"""SSH output parsers — common text parsing utilities for remote command output.

These parsers handle the pipe-delimited and KEY:VALUE output formats produced by
standard diagnostic/status commands run over SSH on remote devices.
"""
from __future__ import annotations


# ── docker ps ─────────────────────────────────────────────────────────────────

def parse_docker_ps(output: str) -> list[dict]:
    """Parse 'docker ps --format "{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}|{{.State}}"' output."""
    containers = []
    for line in output.split("\n"):
        line = line.strip()
        if not line or line.startswith("__NO_"):
            continue
        parts = line.split("|")
        if len(parts) >= 5:
            containers.append({
                "name": parts[0], "image": parts[1],
                "status": parts[2], "ports": parts[3], "state": parts[4],
            })
        elif len(parts) >= 2:
            containers.append({
                "name": parts[0],
                "image": parts[1] if len(parts) > 1 else "",
                "status": parts[2] if len(parts) > 2 else "",
                "ports": "", "state": "",
            })
    return containers


def parse_container_line(line: str) -> dict | None:
    """Parse a single NAME|STATUS|IMAGE pipe-delimited container line."""
    parts = line.split("|")
    if len(parts) >= 2:
        return {"name": parts[0], "status": parts[1], "image": parts[2] if len(parts) > 2 else ""}
    return None


# ── system info ───────────────────────────────────────────────────────────────

def parse_system_info(output: str) -> dict:
    """Parse KEY:VALUE system info lines (HOSTNAME, UPTIME, DISK, MEM, LOAD) into a dict."""
    info: dict = {}
    for line in output.split("\n"):
        line = line.strip()
        if line.startswith("HOSTNAME:"):
            info["hostname"] = line[9:]
        elif line.startswith("UPTIME:"):
            info["uptime"] = line[7:]
        elif line.startswith("LOAD:"):
            info["load"] = line[5:]
        elif line.startswith("KERNEL:"):
            info["kernel"] = line[7:]
        elif line.startswith("CPU_CORES:"):
            info["cpu_cores"] = line[10:]
        elif line.startswith("DISK:"):
            parts = line[5:].split()
            if len(parts) >= 5:
                info["disk"] = {
                    "filesystem": parts[0], "size": parts[1],
                    "used": parts[2], "avail": parts[3], "use_pct": parts[4],
                }
        elif line.startswith("MEM:"):
            parts = line[4:].split()
            if len(parts) >= 4:
                info["memory"] = {
                    "total": parts[1], "used": parts[2], "free": parts[3],
                    "available": parts[6] if len(parts) > 6 else "",
                }
    return info


# ── full diagnostics ──────────────────────────────────────────────────────────

_SECTION_HEADERS = {
    "===SYSTEM===": "system",
    "===DOCKER===": "containers",
    "===CONTAINERS===": "containers",
    "===GIT===": "git",
    "===HEALTH===": "health",
    "===NETWORK===": "network",
}


def parse_diagnostics(output: str) -> dict:
    """Parse multi-section SSH diagnostics output into structured dict.

    Handles sections: ===SYSTEM===, ===CONTAINERS===, ===GIT===, ===HEALTH===, ===NETWORK===.
    """
    result: dict = {"system": {}, "containers": [], "git": {}, "health_code": 0, "listening_ports": 0}
    section = ""
    for raw_line in output.split("\n"):
        line = raw_line.strip()
        if line in _SECTION_HEADERS:
            section = _SECTION_HEADERS[line]
        elif not line or line.startswith("__NO_"):
            continue
        else:
            _parse_section_line(section, result, line)
    return result


def _apply_system_line(sys: dict, line: str) -> None:
    for prefix in ("HOSTNAME:", "UPTIME:", "LOAD:", "KERNEL:", "CPU_CORES:"):
        if line.startswith(prefix):
            sys[prefix[:-1].lower()] = line[len(prefix):]
            return
    if line.startswith("DISK:"):
        parts = line[5:].split()
        if len(parts) >= 5:
            sys["disk"] = {"size": parts[1], "used": parts[2], "avail": parts[3], "use_pct": parts[4]}
    elif line.startswith("MEM:"):
        parts = line[4:].split()
        if len(parts) >= 4:
            sys["memory"] = {
                "total": parts[1], "used": parts[2], "free": parts[3],
                "available": parts[6] if len(parts) > 6 else "",
            }


def _apply_git_line(git: dict, line: str) -> bool:
    for prefix in ("BRANCH:", "COMMIT:", "DIRTY:"):
        if line.startswith(prefix):
            git[prefix[:-1].lower()] = line[len(prefix):]
            return True
    return False


def _apply_health_line(result: dict, line: str) -> bool:
    try:
        result["health_code"] = int(line)
        return True
    except ValueError:
        return False


def _apply_network_line(result: dict, line: str) -> bool:
    if line.startswith("PORTS:"):
        try:
            result["listening_ports"] = int(line[6:])
            return True
        except ValueError:
            pass
    return False


def _parse_section_line(section: str, result: dict, line: str) -> None:
    if section == "system":
        _apply_system_line(result["system"], line)
    elif section == "containers":
        c = parse_container_line(line)
        if c:
            result["containers"].append(c)
    elif section == "git":
        _apply_git_line(result["git"], line)
    elif section == "health":
        _apply_health_line(result, line)
    elif section == "network":
        _apply_network_line(result, line)


# ── health check ─────────────────────────────────────────────────────────────

_HEALTH_PREFIXES: dict[str, str] = {
    "HOSTNAME:": "hostname",
    "UPTIME:": "uptime",
    "DISK:": "disk_pct",
    "LOAD:": "load",
}


def parse_health_info(output: str) -> dict:
    """Parse health-check SSH output (HOSTNAME, UPTIME, HEALTH, DISK, LOAD) into a dict."""
    info: dict = {"hostname": "", "uptime": "", "health": 0, "disk_pct": "", "load": ""}
    for line in output.split("\n"):
        line = line.strip()
        for prefix, key in _HEALTH_PREFIXES.items():
            if line.startswith(prefix):
                info[key] = line[len(prefix):]
                break
        else:
            if line.startswith("HEALTH:"):
                try:
                    info["health"] = int(line[7:])
                except ValueError:
                    pass
    return info

"""Device discovery — find SSH-accessible nodes in the local network.

Strategies (in order of invasiveness):
  1. known_hosts — parse ~/.ssh/known_hosts (zero network I/O)
  2. arp          — read ARP cache (arp -a / ip neigh) — passive, fast
  3. ping_sweep   — ICMP ping sweep of local subnet — active, needs permission
  4. mdns         — query _ssh._tcp via avahi-browse / dns-sd — passive
  5. ssh_probe    — try SSH echo on discovered IPs — verifies reachability

Results are merged into DeviceRegistry and persisted to
~/.config/redeploy/devices.yaml (chmod 600).
"""
from __future__ import annotations

import ipaddress
import re
import shutil
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from .models import DeviceRegistry, KnownDevice


# ── Discovery result ──────────────────────────────────────────────────────────

@dataclass
class DiscoveredHost:
    ip: str
    mac: str = ""
    hostname: str = ""
    ssh_ok: bool = False
    ssh_user: str = ""
    source: str = "unknown"
    ports_open: list[int] = field(default_factory=list)


# ── Individual scanners ───────────────────────────────────────────────────────

def _scan_known_hosts(ssh_user: str = "") -> list[DiscoveredHost]:
    """Parse ~/.ssh/known_hosts for known SSH hosts."""
    kh = __import__("pathlib").Path.home() / ".ssh" / "known_hosts"
    if not kh.exists():
        return []
    results: list[DiscoveredHost] = []
    for line in kh.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Format: host[,ip] keytype key  OR  [host]:port keytype key
        host_field = line.split()[0]
        # Hashed entries ([|1|...]) — skip
        if host_field.startswith("|"):
            continue
        # Strip [host]:port format
        host_field = re.sub(r"^\[(.+)\]:\d+$", r"\1", host_field)
        for candidate in host_field.split(","):
            candidate = candidate.strip()
            if not candidate:
                continue
            try:
                ip = socket.gethostbyname(candidate)
            except Exception:
                ip = candidate
            results.append(DiscoveredHost(
                ip=ip,
                hostname=candidate if not _is_ip(candidate) else "",
                source="known_hosts",
                ssh_user=ssh_user,
            ))
    logger.debug(f"known_hosts: {len(results)} hosts")
    return results


def _scan_arp_cache() -> list[DiscoveredHost]:
    """Read ARP/neighbor cache — no packets sent."""
    results: list[DiscoveredHost] = []

    # Try 'ip neigh' first (Linux)
    if shutil.which("ip"):
        out = _run("ip neigh show")
        for line in out.splitlines():
            # 192.168.1.1 dev eth0 lladdr aa:bb:cc:dd:ee:ff REACHABLE
            parts = line.split()
            if len(parts) >= 5 and re.match(r"\d+\.\d+\.\d+\.\d+", parts[0]):
                mac = parts[4] if len(parts) > 4 else ""
                results.append(DiscoveredHost(ip=parts[0], mac=mac, source="arp"))
        if results:
            logger.debug(f"arp (ip neigh): {len(results)} hosts")
            return results

    # Fallback: arp -a (macOS + Linux)
    if shutil.which("arp"):
        out = _run("arp -a")
        for line in out.splitlines():
            # ? (192.168.1.1) at aa:bb:cc:dd:ee:ff [ether] on eth0
            m = re.search(r"\((\d+\.\d+\.\d+\.\d+)\).*?([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f:]+)", line, re.I)
            if m:
                results.append(DiscoveredHost(ip=m.group(1), mac=m.group(2), source="arp"))
    logger.debug(f"arp: {len(results)} hosts")
    return results


def _scan_mdns(timeout: int = 5) -> list[DiscoveredHost]:
    """Query mDNS for _ssh._tcp services via avahi-browse or dns-sd."""
    results: list[DiscoveredHost] = []

    if shutil.which("avahi-browse"):
        out = _run(f"avahi-browse -t -r -p _ssh._tcp 2>/dev/null", timeout=timeout + 2)
        for line in out.splitlines():
            # =;eth0;IPv4;hostname;_ssh._tcp;local;hostname.local;192.168.1.x;22;
            if line.startswith("="):
                parts = line.split(";")
                if len(parts) >= 8:
                    hostname = parts[3]
                    ip = parts[7]
                    if _is_ip(ip):
                        results.append(DiscoveredHost(
                            ip=ip, hostname=hostname, source="mdns",
                            ports_open=[22],
                        ))

    elif shutil.which("dns-sd"):  # macOS
        # dns-sd -B _ssh._tcp — not easy to parse in a one-shot call, skip
        pass

    logger.debug(f"mdns: {len(results)} hosts")
    return results


def _ping_sweep(subnet: str, timeout: int = 1) -> list[DiscoveredHost]:
    """ICMP ping sweep of a /24 subnet. Active — sends packets."""
    try:
        net = ipaddress.ip_network(subnet, strict=False)
    except ValueError:
        logger.warning(f"Invalid subnet: {subnet}")
        return []

    hosts_to_ping = list(net.hosts())
    if len(hosts_to_ping) > 254:
        logger.warning("Ping sweep limited to /24 (254 hosts)")
        hosts_to_ping = hosts_to_ping[:254]

    alive: list[DiscoveredHost] = []

    def ping_one(ip: str) -> Optional[DiscoveredHost]:
        r = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), str(ip)],
            capture_output=True, timeout=timeout + 1,
        )
        if r.returncode == 0:
            return DiscoveredHost(ip=str(ip), source="ping_sweep")
        return None

    with ThreadPoolExecutor(max_workers=64) as ex:
        futures = {ex.submit(ping_one, str(h)): str(h) for h in hosts_to_ping}
        for f in as_completed(futures):
            res = f.result()
            if res:
                alive.append(res)

    logger.debug(f"ping sweep {subnet}: {len(alive)} alive")
    return alive


def _probe_ssh(
    hosts: list[DiscoveredHost],
    users: list[str],
    port: int = 22,
    timeout: int = 4,
    max_workers: int = 32,
) -> list[DiscoveredHost]:
    """Try SSH echo on each host to confirm reachability + pick valid user."""

    def try_ssh(host: DiscoveredHost) -> DiscoveredHost:
        for user in users:
            target = f"{user}@{host.ip}"
            cmd = [
                "ssh",
                "-o", "ConnectTimeout=4",
                "-o", "StrictHostKeyChecking=no",
                "-o", "BatchMode=yes",
                "-o", "PasswordAuthentication=no",
                "-p", str(port),
                target, "echo ok",
            ]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 1)
                if r.returncode == 0 and "ok" in r.stdout:
                    host.ssh_ok = True
                    host.ssh_user = user
                    host.last_ssh_ok = datetime.now(timezone.utc)  # type: ignore[attr-defined]
                    break
            except Exception:
                pass
        return host

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        return list(ex.map(try_ssh, hosts))


# ── Local subnet detection ────────────────────────────────────────────────────

def _detect_local_subnet() -> Optional[str]:
    """Best-effort detection of local LAN subnet (e.g. 192.168.1.0/24)."""
    # Try ip route
    if shutil.which("ip"):
        out = _run("ip route show")
        for line in out.splitlines():
            # 192.168.1.0/24 dev eth0 proto kernel scope link src 192.168.1.100
            m = re.search(r"(\d+\.\d+\.\d+\.\d+/\d+)\s+dev", line)
            if m:
                net = m.group(1)
                try:
                    n = ipaddress.ip_network(net, strict=False)
                    if not n.is_loopback and n.prefixlen >= 16:
                        return str(n)
                except ValueError:
                    pass
    # Fallback: derive from hostname
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
        parts = local_ip.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
    except Exception:
        pass
    return None


# ── Merge + deduplicate ───────────────────────────────────────────────────────

def _merge(hosts: list[DiscoveredHost]) -> list[DiscoveredHost]:
    """Deduplicate by IP, merging fields from multiple sources."""
    by_ip: dict[str, DiscoveredHost] = {}
    for h in hosts:
        if h.ip in by_ip:
            existing = by_ip[h.ip]
            if not existing.mac and h.mac:
                existing.mac = h.mac
            if not existing.hostname and h.hostname:
                existing.hostname = h.hostname
            if h.ssh_ok:
                existing.ssh_ok = True
                existing.ssh_user = existing.ssh_user or h.ssh_user
            if existing.source == "unknown":
                existing.source = h.source
        else:
            by_ip[h.ip] = h
    return list(by_ip.values())


# ── Public API ────────────────────────────────────────────────────────────────

def discover(
    subnet: Optional[str] = None,
    ssh_users: Optional[list[str]] = None,
    ssh_port: int = 22,
    ping: bool = False,
    mdns: bool = True,
    probe_ssh: bool = True,
    timeout: int = 5,
) -> list[DiscoveredHost]:
    """Discover SSH-accessible hosts in the local network.

    Args:
        subnet:     CIDR to ping-sweep (None = auto-detect). Only used if *ping=True*.
        ssh_users:  SSH usernames to try (default: current user + common ones).
        ssh_port:   SSH port to probe.
        ping:       Run ICMP ping sweep (active — sends packets).
        mdns:       Query mDNS for _ssh._tcp services.
        probe_ssh:  Verify SSH reachability on each discovered host.
        timeout:    Per-host timeout for SSH probe (seconds).

    Returns:
        List of DiscoveredHost, sorted by IP.
    """
    import getpass
    ssh_users = ssh_users or [getpass.getuser(), "root", "pi", "ubuntu", "admin"]

    found: list[DiscoveredHost] = []

    # Always: known_hosts + ARP cache (passive, fast)
    found.extend(_scan_known_hosts(ssh_user=ssh_users[0]))
    found.extend(_scan_arp_cache())

    # Optional: mDNS (passive)
    if mdns:
        found.extend(_scan_mdns(timeout=timeout))

    # Optional: ping sweep (active)
    if ping:
        sub = subnet or _detect_local_subnet()
        if sub:
            logger.info(f"Ping sweep: {sub}")
            found.extend(_ping_sweep(sub, timeout=timeout))

    found = _merge(found)

    # SSH probe
    if probe_ssh and found:
        logger.info(f"SSH probe: {len(found)} hosts ({timeout}s timeout each)")
        found = _probe_ssh(found, users=ssh_users, port=ssh_port, timeout=timeout)

    found.sort(key=lambda h: [int(x) for x in h.ip.split(".") if x.isdigit()])
    return found


def update_registry(
    hosts: list[DiscoveredHost],
    registry: Optional[DeviceRegistry] = None,
    save: bool = True,
) -> DeviceRegistry:
    """Merge discovered hosts into DeviceRegistry and optionally save.

    Existing devices are updated (last_seen, ssh_ok, hostname, mac).
    New SSH-accessible devices are added automatically.
    Devices not seen in this scan are NOT removed (preserved for history).
    """
    reg = registry or DeviceRegistry.load()
    now = datetime.now(timezone.utc)

    for h in hosts:
        if not h.ip:
            continue
        device_id = f"{h.ssh_user}@{h.ip}" if h.ssh_user else h.ip
        existing = reg.get(device_id) or reg.get(h.ip)

        if existing:
            existing.last_seen = now
            if h.mac:
                existing.mac = h.mac
            if h.hostname and not existing.hostname:
                existing.hostname = h.hostname
            if h.ssh_ok:
                existing.last_ssh_ok = now
            reg.upsert(existing)
        elif h.ssh_ok:
            # Only auto-add SSH-accessible devices
            reg.upsert(KnownDevice(
                id=device_id,
                host=device_id,
                ip=h.ip,
                mac=h.mac,
                hostname=h.hostname,
                ssh_user=h.ssh_user if h.ssh_user else "",  # type: ignore[call-arg]
                last_seen=now,
                last_ssh_ok=now,
                source=h.source,
                tags=["discovered"],
            ))

    if save:
        reg.save()
    return reg


# ── helpers ───────────────────────────────────────────────────────────────────

def _run(cmd: str, timeout: int = 10) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout
    except Exception:
        return ""


def _is_ip(s: str) -> bool:
    return bool(re.match(r"^\d+\.\d+\.\d+\.\d+$", s))


# ── ProbeResult ───────────────────────────────────────────────────────────────

@dataclass
class ProbeResult:
    """Full autonomous probe result for a single host."""
    ip: str
    host: str = ""                      # user@ip that worked
    ssh_user: str = ""
    ssh_key: str = ""                   # key path that succeeded
    ssh_port: int = 22
    reachable: bool = False

    # detected from remote
    strategy: str = "unknown"           # docker_full | systemd | podman_quadlet | native_kiosk
    app: str = ""
    version: str = ""
    hostname: str = ""
    arch: str = ""                      # uname -m
    os_info: str = ""
    has_docker: bool = False
    has_podman: bool = False
    has_chromium: bool = False
    running_services: list[str] = field(default_factory=list)
    error: str = ""


# ── Core autonomous probe ─────────────────────────────────────────────────────

_DEFAULT_USERS = ["pi", "ubuntu", "root", "admin", "tom", "debian"]
_DEFAULT_KEY_NAMES = [
    "id_ed25519", "id_rsa", "id_ecdsa",
    "rpi_key", "safetytwin-key",
]


def _collect_ssh_keys() -> list[str]:
    """Return all available private key paths under ~/.ssh/."""
    import os
    home = __import__("pathlib").Path.home()
    keys: list[str] = []
    # env override first
    env_key = os.environ.get("SSH_KEY_PATH") or os.environ.get("SSH_KEY_FILE")
    if env_key and __import__("pathlib").Path(env_key).is_file():
        keys.append(env_key)
    ssh_dir = home / ".ssh"
    if ssh_dir.is_dir():
        for name in _DEFAULT_KEY_NAMES:
            p = ssh_dir / name
            if p.is_file() and ".pub" not in str(p):
                k = str(p)
                if k not in keys:
                    keys.append(k)
        # also any other non-.pub files that look like keys
        for p in sorted(ssh_dir.iterdir()):
            if p.suffix in ("", ) and not p.name.endswith(".pub") \
               and p.name not in ("known_hosts", "config", "authorized_keys"):
                k = str(p)
                if k not in keys:
                    keys.append(k)
    return keys


def _tcp_reachable(ip: str, port: int = 22, timeout: float = 2.0) -> bool:
    """Fast TCP connect check — avoids waiting for SSH timeout on dead hosts."""
    import socket as _socket
    try:
        with _socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def _try_ssh_credentials(
    ip: str,
    users: list[str],
    keys: list[str],
    port: int = 22,
    timeout: int = 5,
) -> tuple[str, str, str]:
    """Try (user, key) combos on ip:port. Return (user, key_path, host_str) or ('','','').

    Starts with a fast TCP check to avoid waiting for SSH timeouts on dead hosts.
    Runs all user×key combos in parallel threads; returns first success.
    """
    import getpass
    import queue as _queue

    # Fast TCP gate — if port 22 not open, skip all SSH attempts
    if not _tcp_reachable(ip, port, timeout=min(timeout, 3.0)):
        return "", "", ""

    cur = getpass.getuser()
    users = [cur] + [u for u in users if u != cur]
    keys_to_try: list = [None] + keys  # type: ignore[list-item]

    result_q: _queue.Queue = _queue.Queue()

    def try_one(user: str, key) -> None:
        cmd = [
            "ssh",
            "-o", f"ConnectTimeout={timeout}",
            "-o", "StrictHostKeyChecking=no",
            "-o", "BatchMode=yes",
            "-o", "PasswordAuthentication=no",
            "-p", str(port),
        ]
        if key:
            cmd += ["-i", key]
        cmd += [f"{user}@{ip}", "echo __ok__"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 2)
            if r.returncode == 0 and "__ok__" in r.stdout:
                result_q.put((user, key or "", f"{user}@{ip}"))
        except Exception:
            pass

    # Try agent/default first (no key) for each user sequentially — fast path
    for user in users:
        cmd = [
            "ssh",
            "-o", f"ConnectTimeout={timeout}",
            "-o", "StrictHostKeyChecking=no",
            "-o", "BatchMode=yes",
            "-o", "PasswordAuthentication=no",
            "-p", str(port),
            f"{user}@{ip}", "echo __ok__",
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 2)
            if r.returncode == 0 and "__ok__" in r.stdout:
                return user, "", f"{user}@{ip}"
        except Exception:
            pass

    # Parallel fallback: try all user×key combos concurrently
    combos = [(u, k) for u in users for k in keys_to_try if k is not None]
    with ThreadPoolExecutor(max_workers=min(len(combos), 16)) as ex:
        futures = [ex.submit(try_one, u, k) for u, k in combos]
        try:
            return result_q.get(timeout=timeout + 3)
        except _queue.Empty:
            pass
        for f in futures:
            f.cancel()

    return "", "", ""


def _detect_strategy_remote(
    host: str, key: str, port: int = 22, timeout: int = 10
) -> dict:
    """Run a single SSH session to detect strategy, app, version, etc."""
    key_opts = ["-i", key] if key else []
    probe_cmd = _build_probe_command()
    cmd = _build_ssh_command(host, port, timeout, key_opts, probe_cmd)

    out = _run_ssh_probe(cmd, timeout)
    if out is None:
        return {}

    info, services = _parse_probe_output(out)
    info["running_services"] = services
    info["strategy"] = _infer_strategy(info, services)

    return info


def _build_probe_command() -> str:
    return (
        "echo __arch__=$(uname -m); "
        "echo __os__=$(. /etc/os-release 2>/dev/null && echo $PRETTY_NAME || uname -s); "
        "echo __hostname__=$(hostname); "
        "docker info --format 'ok' 2>/dev/null && echo __docker__=1 || echo __docker__=0; "
        "podman --version 2>/dev/null && echo __podman__=1 || echo __podman__=0; "
        "which chromium chromium-browser 2>/dev/null && echo __chromium__=1 || echo __chromium__=0; "
        "systemctl is-active --quiet docker 2>/dev/null && echo __docker_active__=1 || echo __docker_active__=0; "
        "systemctl list-units --type=service --state=running --no-pager --no-legend 2>/dev/null | awk '{print $1}' | head -30; "
        "echo __end_services__"
    )


def _build_ssh_command(host: str, port: int, timeout: int, key_opts: list[str], probe_cmd: str) -> list[str]:
    return ["ssh"] + [
        "-o", f"ConnectTimeout={timeout}",
        "-o", "StrictHostKeyChecking=no",
        "-o", "BatchMode=yes",
        "-p", str(port),
    ] + key_opts + [host, probe_cmd]


def _run_ssh_probe(cmd: list[str], timeout: int) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        if r.returncode != 0:
            return None
        return r.stdout
    except Exception:
        return None


def _parse_probe_output(out: str) -> tuple[dict, list[str]]:
    info: dict = {}
    services: list[str] = []
    in_services = False

    for line in out.splitlines():
        line = line.strip()
        if line.startswith("__arch__="):
            info["arch"] = line.split("=", 1)[1]
        elif line.startswith("__os__="):
            info["os_info"] = line.split("=", 1)[1]
        elif line.startswith("__hostname__="):
            info["hostname"] = line.split("=", 1)[1]
        elif line.startswith("__docker__="):
            info["has_docker"] = line.endswith("1")
        elif line.startswith("__podman__="):
            info["has_podman"] = line.endswith("1")
        elif line.startswith("__chromium__="):
            info["has_chromium"] = line.endswith("1")
        elif line.startswith("__docker_active__="):
            info["docker_active"] = line.endswith("1")
        elif line == "__end_services__":
            in_services = False
        elif in_services:
            if line:
                services.append(line)
        elif line.endswith(".service") or ("loaded" in line and "active" in line):
            in_services = True
            if line.endswith(".service"):
                services.append(line)

    return info, services


def _infer_strategy(info: dict, services: list[str]) -> str:
    if info.get("docker_active") or info.get("has_docker"):
        return "docker_full"
    elif info.get("has_podman"):
        return "podman_quadlet"
    elif info.get("has_chromium") and any("kiosk" in s or "chromium" in s for s in services):
        return "native_kiosk"
    else:
        return "systemd"


def _parse_probe_input(ip_or_host: str, users: Optional[list[str]]) -> tuple[str, list[str]]:
    if "@" in ip_or_host:
        forced_user, ip = ip_or_host.split("@", 1)
        return ip, [forced_user] + (users or _DEFAULT_USERS)
    else:
        return ip_or_host, users or _DEFAULT_USERS


def _detect_app_from_services(services: list[str], app_hint: str) -> str:
    if app_hint:
        return app_hint
    for svc in services:
        for candidate in ("c2004", "app", "backend", "kiosk", "api"):
            if candidate in svc.lower():
                return candidate
    return ""


def _update_existing_device(existing, result, ssh_user, ssh_key, ip, host_str, port, now) -> None:
    existing.host = host_str
    existing.ip = ip
    existing.ssh_user = ssh_user
    if ssh_key:
        existing.ssh_key = ssh_key
    existing.ssh_port = port
    existing.strategy = result.strategy
    existing.hostname = result.hostname or existing.hostname
    existing.last_seen = now
    existing.last_ssh_ok = now
    if result.app and not existing.app:
        existing.app = result.app


def _create_new_device(result, ssh_user, ssh_key, ip, host_str, port, now) -> "KnownDevice":
    from .models import KnownDevice

    return KnownDevice(
        id=host_str,
        host=host_str,
        ip=ip,
        mac="",
        hostname=result.hostname,
        ssh_user=ssh_user,
        ssh_key=ssh_key if ssh_key else None,
        ssh_port=port,
        strategy=result.strategy,
        app=result.app,
        last_seen=now,
        last_ssh_ok=now,
        source="probe",
        tags=["discovered"],
    )


def auto_probe(
    ip_or_host: str,
    users: Optional[list[str]] = None,
    port: int = 22,
    timeout: int = 6,
    app_hint: str = "",
    save: bool = True,
) -> "ProbeResult":
    """Autonomously probe a host — try all available SSH keys and users.

    Detects: SSH credentials, strategy (docker/podman/systemd/kiosk),
    running services, arch, OS. Saves to DeviceRegistry automatically.

    Args:
        ip_or_host:  IP address or ``user@ip`` string.
        users:       SSH users to try (default: pi, ubuntu, root, admin, current user).
        port:        SSH port.
        timeout:     Per-attempt SSH timeout.
        app_hint:    Hint for app name (checked in running services).
        save:        Persist result to registry.

    Returns:
        ProbeResult with all discovered fields.
    """
    # Normalise input
    ip, users = _parse_probe_input(ip_or_host, users)

    result = ProbeResult(ip=ip, ssh_port=port)

    # Collect available SSH keys
    keys = _collect_ssh_keys()

    # Find working credentials
    ssh_user, ssh_key, host_str = _try_ssh_credentials(ip, users, keys, port, timeout)
    if not host_str:
        result.error = f"No SSH access: tried {len(users)} users × {len(keys)+1} keys"
        logger.warning(f"[probe {ip}] {result.error}")
        return result

    result.reachable = True
    result.ssh_user = ssh_user
    result.ssh_key = ssh_key
    result.host = host_str
    logger.info(f"[probe {ip}] SSH OK as {ssh_user}"
                + (f" via {__import__('os').path.basename(ssh_key)}" if ssh_key else " (agent/default)"))

    # Detect remote strategy + metadata
    info = _detect_strategy_remote(host_str, ssh_key, port, timeout=timeout * 2)
    if info:
        result.strategy = info.get("strategy", "systemd")
        result.hostname = info.get("hostname", "")
        result.arch = info.get("arch", "")
        result.os_info = info.get("os_info", "")
        result.has_docker = bool(info.get("has_docker"))
        result.has_podman = bool(info.get("has_podman"))
        result.has_chromium = bool(info.get("has_chromium"))
        result.running_services = info.get("running_services", [])
        result.app = _detect_app_from_services(result.running_services, app_hint)

    # Save to registry
    if save:
        reg = DeviceRegistry.load()
        now = datetime.utcnow()
        existing = reg.get(host_str) or reg.get(ip)
        if existing:
            _update_existing_device(existing, result, ssh_user, ssh_key, ip, host_str, port, now)
            reg.upsert(existing)
        else:
            reg.upsert(_create_new_device(result, ssh_user, ssh_key, ip, host_str, port, now))
        reg.save()
        logger.info(f"[probe {ip}] saved to registry as {host_str}")

    return result

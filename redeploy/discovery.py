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
from datetime import datetime
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
                    host.last_ssh_ok = datetime.utcnow()  # type: ignore[attr-defined]
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
    now = datetime.utcnow()

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

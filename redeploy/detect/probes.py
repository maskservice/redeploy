"""Individual probes: docker, k3s, systemd, ports, health, version."""
from __future__ import annotations

import json
import re
import shlex
from typing import Optional

from ..models import (
    AppHealthInfo, ConflictInfo, ConflictSeverity, DeployStrategy,
    PortInfo, RuntimeInfo, ServiceInfo,
)
from .remote import RemoteProbe


_SAFE_K8S_NS_RE = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")


def probe_runtime(p: RemoteProbe) -> RuntimeInfo:
    """Detect installed runtimes: docker, k3s, podman, systemd."""
    def ver(cmd: str) -> Optional[str]:
        r = p.run(cmd)
        return r.out.splitlines()[0] if r.ok and r.out else None

    docker = ver("docker --version 2>/dev/null")
    dc = ver("docker compose version 2>/dev/null | head -1")
    k3s = ver("k3s --version 2>/dev/null | head -1")
    podman = ver("podman --version 2>/dev/null")
    systemd = ver("systemctl --version 2>/dev/null | head -1")

    k3s_ns: list[str] = []
    if k3s:
        r = p.run("k3s kubectl get ns -o name 2>/dev/null")
        if r.ok:
            k3s_ns = [line.replace("namespace/", "").strip() for line in r.out.splitlines() if line.strip()]

    os_info = ver("cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"'")
    arch = ver("uname -m")
    chromium = ver("which chromium chromium-browser 2>/dev/null | head -1")

    return RuntimeInfo(
        docker=docker, docker_compose=dc, k3s=k3s, k3s_namespaces=k3s_ns,
        podman=podman, systemd=systemd, os=os_info, arch=arch,
        chromium=chromium,
    )


def probe_ports(p: RemoteProbe) -> dict[int, PortInfo]:
    """Detect listening ports and which process owns them."""
    ports: dict[int, PortInfo] = {}
    r = p.run("ss -tlnp 2>/dev/null | grep LISTEN")
    if not r.ok:
        return ports

    for line in r.out.splitlines():
        # extract port from Local Address:Port column
        m = re.search(r':(\d+)\s', line)
        if not m:
            continue
        port = int(m.group(1))
        # extract process name
        proc_m = re.search(r'users:\(\("([^"]+)"', line)
        proc = proc_m.group(1) if proc_m else "unknown"
        pid_m = re.search(r'pid=(\d+)', line)
        pid = int(pid_m.group(1)) if pid_m else None
        ports[port] = PortInfo(port=port, process=proc, pid=pid)

    return ports


def probe_iptables_dnat(p: RemoteProbe, ports: list[int]) -> list[tuple[int, str]]:
    """Find iptables DNAT rules stealing specific ports (returns [(port, target_ip)])."""
    results = []
    r = p.run("iptables -t nat -L -n 2>/dev/null | grep DNAT")
    if not r.ok:
        return results
    for port in ports:
        count = 0
        for line in r.out.splitlines():
            if f"dpt:{port}" in line or f":{port} " in line:
                m = re.search(r'to:([0-9.]+:\d+)', line)
                target = m.group(1) if m else "unknown"
                results.append((port, target))
                count += 1
        # multiple DNAT rules on same port = conflict
    return results


def probe_docker_services(p: RemoteProbe) -> list[ServiceInfo]:
    """List running Docker containers."""
    services = []
    r = p.run(
        "docker ps --format '{{.Names}}|{{.Image}}|{{.Status}}' 2>/dev/null"
    )
    if not r.ok:
        return services

    for line in r.out.splitlines():
        parts = line.split("|")
        if len(parts) < 2:
            continue
        name, image = parts[0].strip(), parts[1].strip()
        status = parts[2].strip() if len(parts) > 2 else "unknown"
        healthy = "healthy" in status.lower()

        # get port mappings
        rp = p.run(f"docker inspect {name} --format '{{{{json .NetworkSettings.Ports}}}}' 2>/dev/null")
        ports: list[int] = []
        if rp.ok and rp.out:
            try:
                pmap = json.loads(rp.out)
                for k in pmap:
                    m = re.match(r'(\d+)/', k)
                    if m:
                        ports.append(int(m.group(1)))
            except json.JSONDecodeError:
                pass

        services.append(ServiceInfo(
            name=name, image=image,
            status="healthy" if healthy else status,
            ports=ports,
        ))
    return services


def probe_k3s_services(p: RemoteProbe, namespaces: list[str]) -> list[ServiceInfo]:
    """List running k3s pods."""
    services = []
    for ns in namespaces:
        if ns in ("kube-system", "kube-public", "kube-node-lease", "cert-manager"):
            continue
        if not _SAFE_K8S_NS_RE.match(ns):
            continue
        r = p.run(
            f"k3s kubectl get pods -n {shlex.quote(ns)} --no-headers 2>/dev/null"
            " | awk '{print $1\"|\"$2\"|\"$3}'"
        )
        if not r.ok:
            continue
        for line in r.out.splitlines():
            parts = line.split("|")
            if len(parts) < 3:
                continue
            name, ready, phase = parts[0].strip(), parts[1].strip(), parts[2].strip()
            services.append(ServiceInfo(
                name=name, namespace=ns,
                status=phase.lower(),
            ))
    return services


def probe_systemd_services(p: RemoteProbe, app: str) -> list[ServiceInfo]:
    """List app-related systemd units (also catches kiosk/chromium/openbox)."""
    services = []
    # Build grep chain: app name + kiosk-related patterns
    patterns = [pat for pat in [app, "kiosk", "chromium", "openbox"] if pat]
    grep_chain = " | ".join(f"grep -i {pat}" for pat in patterns)
    r = p.run(
        f"systemctl list-units --type=service --state=active --no-pager 2>/dev/null"
        f" | ({grep_chain}) | awk '{{print $1\"|\"$3\"|\"$4}}'"
    )
    if not r.ok:
        return services
    for line in r.out.splitlines():
        parts = line.split("|")
        if not parts[0].strip():
            continue
        services.append(ServiceInfo(
            name=parts[0].strip(),
            unit=parts[0].strip(),
            status=parts[1].strip() if len(parts) > 1 else "unknown",
        ))
    return services


def probe_health(host: str, app: str, domain: Optional[str] = None) -> list[AppHealthInfo]:
    """HTTP health checks against known endpoints."""
    import httpx

    results = []
    base = f"https://{domain}" if domain else None
    endpoints = []

    if base:
        endpoints += [
            (f"{base}/api/v1/health", "backend"),
            (f"{base}/firmware/health", "firmware"),
            (f"{base}/", "frontend"),
        ]

    for url, name in endpoints:
        try:
            r = httpx.get(url, timeout=5, verify=False, follow_redirects=True)
            version = None
            if r.headers.get("content-type", "").startswith("application/json"):
                try:
                    body = r.json()
                    version = body.get("version")
                except Exception:
                    pass
            results.append(AppHealthInfo(
                url=url, status_code=r.status_code,
                version=version,
                healthy=(r.status_code == 200),
            ))
        except Exception as e:
            results.append(AppHealthInfo(url=url, healthy=False))

    return results


def detect_conflicts(
    ports: dict[int, PortInfo],
    iptables_dnat: list[tuple[int, str]],
    runtime: RuntimeInfo,
    docker_services: list[ServiceInfo],
    k3s_services: list[ServiceInfo],
) -> list[ConflictInfo]:
    """Identify conflicts: port stealing, duplicate services, etc."""
    conflicts = []

    # Multiple DNAT rules on same port
    seen_ports: dict[int, int] = {}
    for port, target in iptables_dnat:
        seen_ports[port] = seen_ports.get(port, 0) + 1
    for port, count in seen_ports.items():
        if count > 1:
            conflicts.append(ConflictInfo(
                type="port_steal",
                description=f"Port {port} has {count} iptables DNAT rules — k3s may intercept before docker-proxy",
                severity=ConflictSeverity.HIGH,
                affected=[str(port)],
                fix_hint=f"Stop k3s: `systemctl stop k3s && systemctl disable k3s`",
            ))

    # k3s running alongside Docker on same app
    if runtime.k3s and docker_services:
        docker_names = {s.name for s in docker_services}
        k3s_names = {s.name for s in k3s_services}
        overlap_hint = docker_names & {s.replace("-", "") for s in k3s_names}
        if k3s_services:
            conflicts.append(ConflictInfo(
                type="dual_runtime",
                description=f"k3s ({runtime.k3s}) and Docker both running — may serve same app from different versions",
                severity=ConflictSeverity.HIGH,
                affected=list(k3s_names),
                fix_hint="Use `redeploy plan` to generate a migration plan",
            ))

    # Port 80/443 not owned by expected process
    for port in (80, 443):
        if port in ports:
            proc = ports[port].process
            if proc not in ("docker-proxy", "nginx", "traefik"):
                conflicts.append(ConflictInfo(
                    type="unexpected_port_owner",
                    description=f"Port {port} owned by '{proc}' (expected docker-proxy/nginx/traefik)",
                    severity=ConflictSeverity.MEDIUM,
                    affected=[str(port)],
                ))

    return conflicts


def detect_strategy(
    runtime: RuntimeInfo,
    docker_services: list[ServiceInfo],
    k3s_services: list[ServiceInfo],
    systemd_services: list[ServiceInfo],
) -> DeployStrategy:
    """Infer the current deployment strategy from detected services."""
    if k3s_services and not docker_services:
        return DeployStrategy.K3S
    if docker_services and not k3s_services:
        return DeployStrategy.DOCKER_FULL
    if docker_services and k3s_services:
        return DeployStrategy.K3S       # k3s is winning (has DNAT priority)
    if systemd_services and runtime.podman:
        return DeployStrategy.PODMAN_QUADLET
    if systemd_services:
        return DeployStrategy.SYSTEMD
    return DeployStrategy.UNKNOWN

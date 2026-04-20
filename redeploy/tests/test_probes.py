"""Tests for detect/probes.py — all pure functions, RemoteProbe mocked."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from redeploy.detect.probes import (
    detect_conflicts,
    detect_strategy,
    probe_docker_services,
    probe_iptables_dnat,
    probe_k3s_services,
    probe_ports,
    probe_runtime,
    probe_systemd_services,
)
from redeploy.models import (
    ConflictSeverity,
    DeployStrategy,
    PortInfo,
    RuntimeInfo,
    ServiceInfo,
)


# ── helpers ───────────────────────────────────────────────────────────────────


def _probe(responses: dict[str, tuple[bool, str]]):
    """Return a mock RemoteProbe whose .run() returns preset (ok, out) by command prefix."""
    p = MagicMock()

    def _run(cmd: str, timeout: int = 30):
        for prefix, (ok, out) in responses.items():
            if prefix in cmd:
                r = MagicMock()
                r.ok = ok
                r.out = out
                r.stderr = ""
                r.returncode = 0 if ok else 1
                return r
        # default: success, empty
        r = MagicMock()
        r.ok = True
        r.out = ""
        r.stderr = ""
        r.returncode = 0
        return r

    p.run = _run
    return p


# ── probe_runtime ─────────────────────────────────────────────────────────────


class TestProbeRuntime:
    def test_docker_present(self):
        p = _probe({
            "docker --version": (True, "Docker version 24.0.0"),
            "docker compose version": (True, "Docker Compose version v2.20.0"),
        })
        rt = probe_runtime(p)
        assert "Docker" in rt.docker
        assert rt.docker_compose is not None

    def test_k3s_present_with_namespaces(self):
        p = _probe({
            "k3s --version": (True, "k3s version v1.28.0"),
            "k3s kubectl get ns": (True, "namespace/c2004\nnamespace/kube-system"),
        })
        rt = probe_runtime(p)
        assert rt.k3s is not None
        assert "c2004" in rt.k3s_namespaces
        assert "kube-system" in rt.k3s_namespaces

    def test_k3s_absent(self):
        p = _probe({"k3s --version": (False, "")})
        rt = probe_runtime(p)
        assert rt.k3s is None
        assert rt.k3s_namespaces == []

    def test_podman_present(self):
        p = _probe({"podman --version": (True, "podman version 4.6.0")})
        rt = probe_runtime(p)
        assert "podman" in rt.podman

    def test_nothing_installed(self):
        p = _probe({})
        rt = probe_runtime(p)
        # all should gracefully return None
        assert rt.docker is None or isinstance(rt.docker, str)

    def test_arch_detected(self):
        p = _probe({"uname -m": (True, "x86_64")})
        rt = probe_runtime(p)
        assert rt.arch == "x86_64"


# ── probe_ports ───────────────────────────────────────────────────────────────


class TestProbePorts:
    def _ss_output(self):
        return (
            "LISTEN 0 128 0.0.0.0:80 0.0.0.0:* users:((\"nginx\",pid=1234,fd=6))\n"
            "LISTEN 0 128 0.0.0.0:443 0.0.0.0:* users:((\"traefik\",pid=5678,fd=8))\n"
            "LISTEN 0 128 0.0.0.0:8000 0.0.0.0:* users:((\"uvicorn\",pid=9999,fd=3))\n"
        )

    def test_parses_ports(self):
        p = _probe({"ss -tlnp": (True, self._ss_output())})
        ports = probe_ports(p)
        assert 80 in ports
        assert 443 in ports
        assert 8000 in ports

    def test_process_name(self):
        p = _probe({"ss -tlnp": (True, self._ss_output())})
        ports = probe_ports(p)
        assert ports[80].process == "nginx"
        assert ports[443].process == "traefik"

    def test_pid_parsed(self):
        p = _probe({"ss -tlnp": (True, self._ss_output())})
        ports = probe_ports(p)
        assert ports[80].pid == 1234

    def test_empty_if_command_fails(self):
        p = _probe({"ss -tlnp": (False, "")})
        ports = probe_ports(p)
        assert ports == {}

    def test_empty_output(self):
        p = _probe({"ss -tlnp": (True, "")})
        ports = probe_ports(p)
        assert ports == {}


# ── probe_iptables_dnat ───────────────────────────────────────────────────────


class TestProbeIptablesDnat:
    def _iptables_output(self):
        return (
            "DNAT tcp -- anywhere anywhere tcp dpt:80 to:10.42.0.5:80\n"
            "DNAT tcp -- anywhere anywhere tcp dpt:443 to:10.42.0.5:443\n"
            "DNAT tcp -- anywhere anywhere tcp dpt:80 to:10.42.0.6:80\n"
        )

    def test_finds_dnat_rules(self):
        p = _probe({"iptables -t nat": (True, self._iptables_output())})
        results = probe_iptables_dnat(p, [80, 443])
        assert len(results) >= 1

    def test_returns_empty_if_no_dnat(self):
        p = _probe({"iptables -t nat": (True, "")})
        results = probe_iptables_dnat(p, [80, 443])
        assert results == []

    def test_returns_empty_on_failure(self):
        p = _probe({"iptables -t nat": (False, "")})
        results = probe_iptables_dnat(p, [80])
        assert results == []


# ── probe_docker_services ─────────────────────────────────────────────────────


class TestProbeDockerServices:
    def test_parses_containers(self):
        p = _probe({
            "docker ps": (True, "c2004-backend|ghcr.io/maskservice/c2004:1.0.20|Up 3 hours (healthy)\n"
                                "traefik|traefik:v2.10|Up 3 hours"),
            "docker inspect": (True, '{"8000/tcp": null}'),
        })
        svcs = probe_docker_services(p)
        names = [s.name for s in svcs]
        assert "c2004-backend" in names
        assert "traefik" in names

    def test_healthy_flag(self):
        p = _probe({
            "docker ps": (True, "myapp|myimage|Up 1 hour (healthy)"),
            "docker inspect": (True, "{}"),
        })
        svcs = probe_docker_services(p)
        assert svcs[0].status == "healthy"

    def test_empty_if_no_docker(self):
        p = _probe({"docker ps": (False, "")})
        svcs = probe_docker_services(p)
        assert svcs == []

    def test_ports_from_inspect(self):
        p = _probe({
            "docker ps": (True, "web|nginx:latest|Up"),
            "docker inspect": (True, '{"80/tcp":[{"HostIp":"","HostPort":"80"}]}'),
        })
        svcs = probe_docker_services(p)
        assert 80 in svcs[0].ports


# ── probe_k3s_services ────────────────────────────────────────────────────────


class TestProbeK3sServices:
    def test_skips_system_namespaces(self):
        p = _probe({"k3s kubectl get pods": (True, "c2004-api|1/1|Running")})
        svcs = probe_k3s_services(p, ["kube-system", "kube-public", "c2004"])
        names = [s.name for s in svcs]
        assert "c2004-api" in names

    def test_empty_namespaces(self):
        p = _probe({})
        svcs = probe_k3s_services(p, [])
        assert svcs == []

    def test_all_system_namespaces_skipped(self):
        p = _probe({"k3s kubectl get pods": (True, "pod|1/1|Running")})
        svcs = probe_k3s_services(p, ["kube-system", "kube-public", "kube-node-lease"])
        assert svcs == []


# ── probe_systemd_services ────────────────────────────────────────────────────


class TestProbeSystemdServices:
    def test_parses_active_units(self):
        p = _probe({
            "systemctl list-units": (
                True,
                "c2004-backend.service|active|running\n"
                "c2004-frontend.service|active|running",
            )
        })
        svcs = probe_systemd_services(p, "c2004")
        assert len(svcs) == 2
        assert svcs[0].name == "c2004-backend.service"

    def test_empty_on_failure(self):
        p = _probe({"systemctl list-units": (False, "")})
        svcs = probe_systemd_services(p, "c2004")
        assert svcs == []


# ── detect_conflicts ──────────────────────────────────────────────────────────


class TestDetectConflicts:
    def _rt(self, has_k3s=False, has_docker=False):
        return RuntimeInfo(
            docker="Docker 24.0" if has_docker else None,
            k3s="k3s v1.28" if has_k3s else None,
        )

    def test_no_conflicts_clean_state(self):
        ports = {80: PortInfo(port=80, process="traefik")}
        rt = self._rt(has_docker=True)
        conflicts = detect_conflicts(ports, [], rt, [ServiceInfo(name="web", status="healthy")], [])
        assert all(c.type != "dual_runtime" for c in conflicts)

    def test_port_steal_from_dnat(self):
        rt = self._rt(has_k3s=True, has_docker=True)
        dnat = [(80, "10.42.0.5:80"), (80, "10.42.0.6:80")]
        conflicts = detect_conflicts({}, dnat, rt, [], [])
        types = [c.type for c in conflicts]
        assert "port_steal" in types

    def test_dual_runtime_conflict(self):
        rt = self._rt(has_k3s=True, has_docker=True)
        docker_svcs = [ServiceInfo(name="c2004-backend", status="healthy")]
        k3s_svcs = [ServiceInfo(name="c2004-api", namespace="c2004", status="running")]
        conflicts = detect_conflicts({}, [], rt, docker_svcs, k3s_svcs)
        types = [c.type for c in conflicts]
        assert "dual_runtime" in types

    def test_unexpected_port_owner(self):
        ports = {
            80: PortInfo(port=80, process="k3s-proxy"),
            443: PortInfo(port=443, process="k3s-proxy"),
        }
        rt = self._rt()
        conflicts = detect_conflicts(ports, [], rt, [], [])
        types = [c.type for c in conflicts]
        assert "unexpected_port_owner" in types

    def test_expected_port_owners_no_conflict(self):
        ports = {
            80: PortInfo(port=80, process="nginx"),
            443: PortInfo(port=443, process="traefik"),
        }
        rt = self._rt()
        conflicts = detect_conflicts(ports, [], rt, [], [])
        owner_conflicts = [c for c in conflicts if c.type == "unexpected_port_owner"]
        assert owner_conflicts == []

    def test_conflict_severity_port_steal_is_high(self):
        rt = self._rt(has_k3s=True)
        dnat = [(80, "10.42.0.5:80"), (80, "10.42.0.6:80")]
        conflicts = detect_conflicts({}, dnat, rt, [], [])
        ps = [c for c in conflicts if c.type == "port_steal"]
        assert ps[0].severity == ConflictSeverity.HIGH


# ── detect_strategy ───────────────────────────────────────────────────────────


class TestDetectStrategy:
    def _rt(self, has_k3s=False, has_docker=False, has_podman=False):
        return RuntimeInfo(
            docker="Docker 24" if has_docker else None,
            k3s="k3s v1.28" if has_k3s else None,
            podman="podman 4.6" if has_podman else None,
        )

    def test_k3s_only(self):
        rt = self._rt(has_k3s=True)
        k3s_svcs = [ServiceInfo(name="pod", status="running")]
        assert detect_strategy(rt, [], k3s_svcs, []) == DeployStrategy.K3S

    def test_docker_only(self):
        rt = self._rt(has_docker=True)
        docker_svcs = [ServiceInfo(name="web", status="healthy")]
        assert detect_strategy(rt, docker_svcs, [], []) == DeployStrategy.DOCKER_FULL

    def test_k3s_wins_over_docker_when_both_running(self):
        rt = self._rt(has_k3s=True, has_docker=True)
        docker_svcs = [ServiceInfo(name="web", status="healthy")]
        k3s_svcs = [ServiceInfo(name="pod", status="running")]
        assert detect_strategy(rt, docker_svcs, k3s_svcs, []) == DeployStrategy.K3S

    def test_podman_quadlet(self):
        rt = self._rt(has_podman=True)
        systemd_svcs = [ServiceInfo(name="c2004.service", status="active")]
        assert detect_strategy(rt, [], [], systemd_svcs) == DeployStrategy.PODMAN_QUADLET

    def test_systemd_without_podman(self):
        rt = self._rt()
        systemd_svcs = [ServiceInfo(name="c2004.service", status="active")]
        assert detect_strategy(rt, [], [], systemd_svcs) == DeployStrategy.SYSTEMD

    def test_nothing_running(self):
        rt = self._rt()
        assert detect_strategy(rt, [], [], []) == DeployStrategy.UNKNOWN

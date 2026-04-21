"""Detector — orchestrates all probes and produces InfraState."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from loguru import logger

from ..models import HardwareInfo, InfraState
from .hardware import probe_hardware
from .probes import (
    detect_conflicts, detect_strategy, probe_docker_services,
    probe_health, probe_iptables_dnat, probe_k3s_services,
    probe_ports, probe_runtime, probe_systemd_services,
)
from .remote import RemoteProbe


class Detector:
    """Probe infrastructure and produce InfraState."""

    def __init__(self, host: str, app: str = "c2004", domain: Optional[str] = None):
        self.host = host
        self.app = app
        self.domain = domain
        self.probe = RemoteProbe(host)

    def run(self) -> InfraState:
        logger.info(f"Detecting infrastructure on {self.host} (app={self.app})")

        if not self.probe.is_reachable():
            raise ConnectionError(f"Host {self.host} is not reachable via SSH")

        logger.debug("Probing runtime...")
        runtime = probe_runtime(self.probe)
        logger.debug(f"  docker={runtime.docker}, k3s={runtime.k3s}, podman={runtime.podman}")

        logger.debug("Probing ports...")
        ports = probe_ports(self.probe)
        logger.debug(f"  listening ports: {sorted(ports.keys())}")

        logger.debug("Probing iptables DNAT...")
        dnat = probe_iptables_dnat(self.probe, [80, 443, 8000, 8080, 8443])

        logger.debug("Probing Docker services...")
        docker_svcs = probe_docker_services(self.probe) if runtime.docker else []

        logger.debug("Probing k3s services...")
        k3s_svcs = probe_k3s_services(self.probe, runtime.k3s_namespaces) if runtime.k3s else []

        logger.debug("Probing systemd services...")
        systemd_svcs = probe_systemd_services(self.probe, self.app)

        logger.debug("Probing HTTP health...")
        health = probe_health(self.host, self.app, self.domain)

        logger.debug("Detecting conflicts...")
        conflicts = detect_conflicts(ports, dnat, runtime, docker_svcs, k3s_svcs)

        strategy = detect_strategy(runtime, docker_svcs, k3s_svcs, systemd_svcs)
        logger.info(f"Detected strategy: {strategy.value}")

        if conflicts:
            logger.warning(f"Found {len(conflicts)} conflict(s):")
            for c in conflicts:
                logger.warning(f"  [{c.severity.upper()}] {c.type}: {c.description}")

        current_version = None
        for h in health:
            if h.version:
                current_version = h.version
                break

        state = InfraState(
            host=self.host,
            app=self.app,
            runtime=runtime,
            ports=ports,
            services={
                "docker": docker_svcs,
                "k3s": k3s_svcs,
                "systemd": systemd_svcs,
                "podman": [],
            },
            health=health,
            conflicts=conflicts,
            detected_strategy=strategy,
            current_version=current_version,
            raw={"dnat": [{"port": p, "target": t} for p, t in dnat]},
        )
        return state

    def save(self, state: InfraState, output: Path) -> None:
        data = state.model_dump(mode="json")
        output.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True))
        logger.info(f"InfraState saved to {output}")

    def probe_hardware(self) -> HardwareInfo:
        """Probe hardware state (display, DSI, backlight, I2C, overlays)."""
        if not self.probe.is_reachable():
            raise ConnectionError(f"Host {self.host} is not reachable via SSH")
        logger.info(f"Probing hardware on {self.host}")
        return probe_hardware(self.probe)

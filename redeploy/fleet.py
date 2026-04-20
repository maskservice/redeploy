"""Fleet model — device inventory, stages and declarative expectations.

Provides a generic fleet abstraction usable by both ``deploy`` and any other
project that uses the ``redeploy`` library.

Key concepts
------------
Stage
    A named deployment target class: ``local``, ``dev``, ``staging``, ``prod``.
    Devices belong to one stage; each stage can carry default expectations.

DeviceExpectation (tags)
    Declarative assertions about required infrastructure on a device, e.g.
    ``has_docker``, ``has_traefik``, ``has_quadlet``, ``has_podman``.
    The ``redeploy detect`` pass can verify these against live state.

FleetDevice
    Generic device descriptor — a superset of ``deploy``'s ``DeviceConfig``.

FleetConfig
    Top-level fleet manifest: list of devices grouped by stage, loadable from
    ``fleet.yaml``.

Fleet  (first-class from 0.2.0)
    Unified view over ``FleetConfig`` (fleet.yaml) **and/or** the
    ``DeviceRegistry`` (~/.config/redeploy/devices.yaml).  Supports merge,
    stage/tag/strategy queries and reachability filtering.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────


class DeviceArch(str, Enum):
    RPI3 = "rpi3"
    RPI4 = "rpi4"
    RPI5 = "rpi5"
    AMD64 = "amd64"
    ARM64 = "arm64"
    UNKNOWN = "unknown"


class Stage(str, Enum):
    LOCAL = "local"
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"
    CI = "ci"


class DeviceExpectation(str, Enum):
    """Declarative assertions about required infrastructure on a device.

    Used by ``redeploy detect --verify-expectations`` to cross-check live state.
    """
    HAS_DOCKER = "has_docker"
    HAS_DOCKER_COMPOSE = "has_docker_compose"
    HAS_PODMAN = "has_podman"
    HAS_QUADLET = "has_quadlet"         # podman quadlet units installed
    HAS_TRAEFIK = "has_traefik"         # traefik container/service running
    HAS_K3S = "has_k3s"
    HAS_SYSTEMD = "has_systemd"
    HAS_NGINX = "has_nginx"
    HTTPS_REACHABLE = "https_reachable"
    SSH_REACHABLE = "ssh_reachable"
    DISK_OK = "disk_ok"                 # < 80 % disk usage
    NO_K3S = "no_k3s"                   # k3s must NOT be active (conflicts)
    NO_NGINX = "no_nginx"               # host nginx must not conflict


# ── FleetDevice ───────────────────────────────────────────────────────────────


class FleetDevice(BaseModel):
    """Generic device descriptor — superset of ``deploy``'s DeviceConfig.

    All fields from ``deploy.core.models.DeviceConfig`` are preserved so that
    ``deploy`` can use this model directly.
    """
    id: str
    name: str = ""
    arch: DeviceArch = DeviceArch.UNKNOWN
    strategy: str = "docker_full"       # kept as str — no circular dep on StepAction

    ssh_host: str = ""
    ssh_port: int = 22
    ssh_key: Optional[str] = None
    remote_dir: str = "~/app"
    version: str = "latest"
    env_file: str = ".env"
    domain: str = ""

    compose_files: list[str] = Field(default_factory=list)
    apps: list[str] = Field(default_factory=list)

    # Fleet organisation
    stage: Stage = Stage.DEV
    tags: list[str] = Field(default_factory=list)
    expectations: list[DeviceExpectation] = Field(default_factory=list)

    # UI / misc
    debug: bool = False
    color: str = "#6b7280"
    display: Optional[dict[str, Any]] = Field(default_factory=dict)

    # ── convenience properties ─────────────────────────────────────────────

    @property
    def ssh_user(self) -> str:
        return self.ssh_host.split("@")[0] if "@" in self.ssh_host else "root"

    @property
    def ssh_ip(self) -> str:
        return self.ssh_host.split("@")[-1] if self.ssh_host else ""

    @property
    def is_local(self) -> bool:
        return not self.ssh_host

    @property
    def is_prod(self) -> bool:
        return self.stage == Stage.PROD or "prod" in self.tags

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags

    def has_expectation(self, exp: DeviceExpectation) -> bool:
        return exp in self.expectations

    def verify_expectations(self, state: Any) -> list[str]:
        """Check declared expectations against a detected ``InfraState``.

        Returns list of unmet expectation descriptions (empty = all met).
        Uses duck typing so there is no hard dependency on InfraState.
        """
        failures: list[str] = []
        rt = getattr(state, "runtime", None)
        ports = getattr(state, "ports", {})
        health = getattr(state, "health", [])

        for exp in self.expectations:
            if exp == DeviceExpectation.HAS_DOCKER and rt:
                if not rt.docker:
                    failures.append(f"{exp.value}: docker not found")
            elif exp == DeviceExpectation.HAS_DOCKER_COMPOSE and rt:
                if not rt.docker_compose:
                    failures.append(f"{exp.value}: docker compose not found")
            elif exp == DeviceExpectation.HAS_PODMAN and rt:
                if not rt.podman:
                    failures.append(f"{exp.value}: podman not found")
            elif exp == DeviceExpectation.HAS_K3S and rt:
                if not rt.k3s:
                    failures.append(f"{exp.value}: k3s not found")
            elif exp == DeviceExpectation.NO_K3S and rt:
                if rt.k3s:
                    failures.append(f"{exp.value}: k3s is active (should not be)")
            elif exp == DeviceExpectation.SSH_REACHABLE:
                if not getattr(state, "ssh_ok", True):
                    failures.append(f"{exp.value}: SSH not reachable")
            elif exp == DeviceExpectation.HTTPS_REACHABLE:
                if not any(getattr(h, "healthy", False) for h in health):
                    failures.append(f"{exp.value}: no healthy HTTPS endpoint")
            elif exp == DeviceExpectation.HAS_TRAEFIK:
                docker_svcs = getattr(getattr(state, "services", {}), "get", lambda k, d: d)("docker", [])
                has = any("traefik" in getattr(s, "name", "").lower() for s in docker_svcs)
                if not has:
                    failures.append(f"{exp.value}: traefik not found in docker services")

        return failures


# ── Stage defaults ─────────────────────────────────────────────────────────────


STAGE_DEFAULT_EXPECTATIONS: dict[Stage, list[DeviceExpectation]] = {
    Stage.LOCAL: [DeviceExpectation.HAS_DOCKER, DeviceExpectation.HAS_DOCKER_COMPOSE],
    Stage.DEV: [DeviceExpectation.HAS_DOCKER, DeviceExpectation.HAS_DOCKER_COMPOSE,
                DeviceExpectation.SSH_REACHABLE],
    Stage.STAGING: [DeviceExpectation.HAS_DOCKER, DeviceExpectation.HAS_DOCKER_COMPOSE,
                    DeviceExpectation.SSH_REACHABLE, DeviceExpectation.HTTPS_REACHABLE],
    Stage.PROD: [DeviceExpectation.HAS_DOCKER, DeviceExpectation.HAS_DOCKER_COMPOSE,
                 DeviceExpectation.SSH_REACHABLE, DeviceExpectation.HTTPS_REACHABLE,
                 DeviceExpectation.NO_K3S],
    Stage.CI: [DeviceExpectation.HAS_DOCKER],
}


# ── FleetConfig ───────────────────────────────────────────────────────────────


class FleetConfig(BaseModel):
    """Top-level fleet manifest — list of devices with stage / tag organisation."""

    workspace_root: Path = Field(default_factory=Path.cwd)
    devices: list[FleetDevice] = Field(default_factory=list)

    # ── query helpers ──────────────────────────────────────────────────────

    def get_device(self, device_id: str) -> Optional[FleetDevice]:
        return next((d for d in self.devices if d.id == device_id), None)

    def by_tag(self, tag: str) -> list[FleetDevice]:
        return [d for d in self.devices if tag in d.tags]

    def by_stage(self, stage: Stage) -> list[FleetDevice]:
        return [d for d in self.devices if d.stage == stage]

    def by_strategy(self, strategy: str) -> list[FleetDevice]:
        return [d for d in self.devices if d.strategy == strategy]

    def prod_devices(self) -> list[FleetDevice]:
        return self.by_stage(Stage.PROD)

    # ── loader ────────────────────────────────────────────────────────────

    @classmethod
    def from_file(cls, path: Path, workspace_root: Optional[Path] = None) -> "FleetConfig":
        """Load FleetConfig from a YAML file.

        The YAML may contain a top-level ``devices`` list; each entry is parsed
        as ``FleetDevice``.  Unknown fields are silently ignored so old
        ``fleet.yaml`` files (from ``deploy``) remain compatible.

        ``stage`` is inferred from ``tags`` when not explicitly set:
        ``prod`` tag → Stage.PROD, ``dev`` tag → Stage.DEV, etc.
        """
        with Path(path).open() as f:
            raw = yaml.safe_load(f) or {}

        devices: list[FleetDevice] = []
        for entry in raw.get("devices", []):
            entry = dict(entry)
            # Infer stage from tags when absent
            if "stage" not in entry:
                tags = entry.get("tags", [])
                if "prod" in tags:
                    entry["stage"] = Stage.PROD
                elif "dev" in tags or "debug" in str(entry.get("debug", "")):
                    entry["stage"] = Stage.DEV
                elif "ci" in tags:
                    entry["stage"] = Stage.CI
                else:
                    entry["stage"] = Stage.DEV
            # Add stage default expectations when none declared
            if "expectations" not in entry:
                stage = Stage(entry["stage"])
                entry["expectations"] = [e.value for e in STAGE_DEFAULT_EXPECTATIONS.get(stage, [])]
            devices.append(FleetDevice(**{k: v for k, v in entry.items()
                                          if k in FleetDevice.model_fields}))

        return cls(
            workspace_root=workspace_root or Path(path).parent,
            devices=devices,
        )


# ── Fleet — unified first-class view (0.2.0) ──────────────────────────────────


class Fleet:
    """Unified first-class fleet — wraps FleetConfig and/or DeviceRegistry.

    Provides a single query interface regardless of whether devices come from
    a declarative ``fleet.yaml`` or the personal ``devices.yaml`` registry.

    Usage::

        # From fleet.yaml only
        fleet = Fleet.from_file("fleet.yaml")

        # From personal registry only
        fleet = Fleet.from_registry()

        # Merged: fleet.yaml + registry (registry fills in live metadata)
        fleet = Fleet.from_file("fleet.yaml").merge(Fleet.from_registry())

        # Queries
        prod_devices = fleet.by_stage(Stage.PROD)
        kiosk_devices = fleet.by_strategy("kiosk_appliance")
        live_devices = fleet.reachable()
    """

    def __init__(self, devices: list[FleetDevice]) -> None:
        self._devices = list(devices)

    # ── constructors ──────────────────────────────────────────────────────────

    @classmethod
    def from_file(cls, path: "Path | str") -> "Fleet":
        """Load from a ``fleet.yaml`` file."""
        config = FleetConfig.from_file(Path(path))
        return cls(config.devices)

    @classmethod
    def from_registry(cls, path: "Optional[Path]" = None) -> "Fleet":
        """Load from the personal device registry (devices.yaml).

        Registry ``KnownDevice`` records are converted to ``FleetDevice`` so
        that the same query API applies to both sources.
        """
        from .models import DeviceRegistry
        reg = DeviceRegistry.load(path)
        devices: list[FleetDevice] = []
        for kd in reg.devices:
            devices.append(FleetDevice(
                id=kd.id,
                name=kd.name or kd.hostname or kd.id,
                ssh_host=kd.host,
                ssh_port=kd.ssh_port,
                ssh_key=kd.ssh_key,
                strategy=kd.strategy,
                remote_dir=kd.remote_dir or "~/app",
                domain=kd.domain,
                tags=list(kd.tags),
                stage=Stage.PROD if "prod" in kd.tags else Stage.DEV,
            ))
        return cls(devices)

    @classmethod
    def from_config(cls, config: FleetConfig) -> "Fleet":
        """Wrap an existing ``FleetConfig``."""
        return cls(config.devices)

    # ── queries ───────────────────────────────────────────────────────────────

    @property
    def devices(self) -> list[FleetDevice]:
        return list(self._devices)

    def get(self, device_id: str) -> Optional[FleetDevice]:
        return next((d for d in self._devices if d.id == device_id), None)

    def by_tag(self, tag: str) -> list[FleetDevice]:
        return [d for d in self._devices if tag in d.tags]

    def by_stage(self, stage: Stage) -> list[FleetDevice]:
        return [d for d in self._devices if d.stage == stage]

    def by_strategy(self, strategy: str) -> list[FleetDevice]:
        return [d for d in self._devices if d.strategy == strategy]

    def prod(self) -> list[FleetDevice]:
        return self.by_stage(Stage.PROD)

    def reachable(self, within_seconds: int = 300) -> list[FleetDevice]:
        """Return devices whose registry ``last_seen`` is within *within_seconds*.

        For devices loaded from ``fleet.yaml`` (no registry metadata) this
        always returns them as nominally reachable — use ``from_registry()``
        or ``merge()`` for accurate liveness filtering.
        """
        from datetime import datetime, timezone
        from .models import DeviceRegistry
        reg = DeviceRegistry.load()
        now = datetime.now(timezone.utc)
        result: list[FleetDevice] = []
        for d in self._devices:
            kd = reg.get(d.id)
            if kd and kd.last_seen:
                if (now - kd.last_seen).total_seconds() < within_seconds:
                    result.append(d)
            else:
                result.append(d)  # unknown → optimistically include
        return result

    # ── merge ─────────────────────────────────────────────────────────────────

    def merge(self, other: "Fleet") -> "Fleet":
        """Return a new Fleet that is the union of *self* and *other*.

        Devices with the same ``id`` are taken from *other* (other wins —
        registry metadata is preferred over static fleet.yaml).
        """
        index: dict[str, FleetDevice] = {d.id: d for d in self._devices}
        for d in other._devices:
            index[d.id] = d
        return Fleet(list(index.values()))

    # ── helpers ───────────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._devices)

    def __iter__(self):
        return iter(self._devices)

    def __repr__(self) -> str:
        return f"Fleet({len(self._devices)} devices)"

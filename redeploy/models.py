"""Shared data models for redeploy: InfraState, MigrationPlan, Target."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, PrivateAttr


# ── Enums ─────────────────────────────────────────────────────────────────────

class ConflictSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class StepAction(str, Enum):
    SYSTEMCTL_STOP = "systemctl_stop"
    SYSTEMCTL_DISABLE = "systemctl_disable"
    SYSTEMCTL_START = "systemctl_start"
    KUBECTL_DELETE = "kubectl_delete"
    DOCKER_COMPOSE_UP = "docker_compose_up"
    DOCKER_COMPOSE_DOWN = "docker_compose_down"
    DOCKER_BUILD = "docker_build"
    RSYNC = "rsync"
    SCP = "scp"
    SSH_CMD = "ssh_cmd"
    HTTP_CHECK = "http_check"
    VERSION_CHECK = "version_check"
    WAIT = "wait"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class DeployStrategy(str, Enum):
    DOCKER_FULL = "docker_full"
    NATIVE_KIOSK = "native_kiosk"
    DOCKER_KIOSK = "docker_kiosk"
    PODMAN_QUADLET = "podman_quadlet"
    K3S = "k3s"
    SYSTEMD = "systemd"
    UNKNOWN = "unknown"


# ── InfraState (output of detect) ─────────────────────────────────────────────

class ServiceInfo(BaseModel):
    name: str
    image: Optional[str] = None
    status: str = "unknown"
    version: Optional[str] = None
    ports: list[int] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)
    namespace: Optional[str] = None      # k3s/k8s namespace
    unit: Optional[str] = None           # systemd unit name


class PortInfo(BaseModel):
    port: int
    process: str
    pid: Optional[int] = None
    via: Optional[str] = None            # "traefik", "nginx", "ingress-nginx"
    protocol: str = "tcp"


class ConflictInfo(BaseModel):
    type: str                             # "port_steal", "version_mismatch", "duplicate_service"
    description: str
    severity: ConflictSeverity = ConflictSeverity.MEDIUM
    affected: list[str] = Field(default_factory=list)
    fix_hint: Optional[str] = None


class RuntimeInfo(BaseModel):
    docker: Optional[str] = None
    docker_compose: Optional[str] = None
    k3s: Optional[str] = None
    k3s_namespaces: list[str] = Field(default_factory=list)
    podman: Optional[str] = None
    systemd: Optional[str] = None
    os: Optional[str] = None
    arch: Optional[str] = None


class AppHealthInfo(BaseModel):
    url: str
    status_code: Optional[int] = None
    version: Optional[str] = None
    healthy: bool = False
    response_ms: Optional[float] = None


class InfraState(BaseModel):
    """Full detected state of infrastructure — output of `detect`."""
    host: str                             # "root@1.2.3.4" or "local"
    app: str = "unknown"
    scanned_at: datetime = Field(default_factory=datetime.utcnow)

    runtime: RuntimeInfo = Field(default_factory=RuntimeInfo)
    ports: dict[int, PortInfo] = Field(default_factory=dict)

    services: dict[str, list[ServiceInfo]] = Field(
        default_factory=lambda: {"docker": [], "k3s": [], "systemd": [], "podman": []}
    )

    health: list[AppHealthInfo] = Field(default_factory=list)
    conflicts: list[ConflictInfo] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)    # raw probe output

    detected_strategy: DeployStrategy = DeployStrategy.UNKNOWN
    current_version: Optional[str] = None


# ── Target (input to plan) ─────────────────────────────────────────────────────

class TargetConfig(BaseModel):
    """Desired infrastructure state — input to `plan`."""
    strategy: DeployStrategy = DeployStrategy.DOCKER_FULL
    app: str = "c2004"
    version: Optional[str] = None

    compose_files: list[str] = Field(default_factory=list)
    env_file: Optional[str] = None
    remote_dir: str = "~/c2004"
    domain: Optional[str] = None

    stop_services: list[str] = Field(default_factory=list)   # systemd units to stop
    disable_services: list[str] = Field(default_factory=list)
    delete_k3s_namespaces: list[str] = Field(default_factory=list)

    verify_url: Optional[str] = None
    verify_version: Optional[str] = None


# ── MigrationStep ─────────────────────────────────────────────────────────────

class MigrationStep(BaseModel):
    id: str
    action: StepAction
    description: str
    status: StepStatus = StepStatus.PENDING

    # action-specific params
    service: Optional[str] = None        # systemctl service name
    command: Optional[str] = None        # raw SSH command
    compose: Optional[str] = None        # compose file path
    flags: list[str] = Field(default_factory=list)
    url: Optional[str] = None            # HTTP check URL
    expect: Optional[str] = None         # expected string in response
    src: Optional[str] = None            # rsync/scp source
    dst: Optional[str] = None            # rsync/scp destination
    excludes: list[str] = Field(default_factory=list)  # rsync --exclude patterns
    seconds: int = 0                     # wait duration
    namespace: Optional[str] = None      # k3s namespace

    reason: Optional[str] = None
    risk: ConflictSeverity = ConflictSeverity.LOW
    rollback_command: Optional[str] = None

    result: Optional[str] = None         # filled after apply
    error: Optional[str] = None


# ── MigrationSpec (single YAML: from + to) ───────────────────────────────────

class InfraSpec(BaseModel):
    """Declarative description of one infrastructure state (from OR to)."""
    strategy: DeployStrategy = DeployStrategy.UNKNOWN
    host: str = "local"
    app: str = "c2004"
    version: Optional[str] = None
    domain: Optional[str] = None
    remote_dir: str = "~/c2004"

    # docker_full
    compose_files: list[str] = Field(default_factory=list)
    env_file: Optional[str] = None

    # services to stop/disable when leaving this state
    stop_services: list[str] = Field(default_factory=list)
    disable_services: list[str] = Field(default_factory=list)
    delete_k3s_namespaces: list[str] = Field(default_factory=list)

    # verification
    verify_url: Optional[str] = None
    verify_version: Optional[str] = None


class MigrationSpec(BaseModel):
    """Single YAML file describing full migration: from-state → to-state.

    Usage:
        redeploy run --spec migration.yaml
    """
    name: str = "migration"
    description: str = ""

    source: InfraSpec          # current / "before" state
    target: InfraSpec          # desired / "after" state

    # Optional explicit steps that override auto-generated ones
    extra_steps: list[dict] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @classmethod
    def from_file(cls, path: "Path") -> "MigrationSpec":  # type: ignore[name-defined]
        import yaml
        from pathlib import Path
        with Path(path).open() as f:
            return cls(**yaml.safe_load(f))

    def to_infra_state(self) -> "InfraState":
        """Build a minimal InfraState from source spec (used when detect is skipped)."""
        rt = RuntimeInfo()
        if self.source.strategy == DeployStrategy.K3S:
            rt.k3s = "declared-in-spec"
            rt.k3s_namespaces = self.source.delete_k3s_namespaces or [self.source.app]
        if self.source.strategy == DeployStrategy.DOCKER_FULL:
            rt.docker = "declared-in-spec"
        return InfraState(
            host=self.source.host,
            app=self.source.app,
            runtime=rt,
            detected_strategy=self.source.strategy,
            current_version=self.source.version,
        )

    def to_target_config(self) -> "TargetConfig":
        """Convert target InfraSpec to TargetConfig for Planner."""
        return TargetConfig(
            strategy=self.target.strategy,
            app=self.target.app,
            version=self.target.version,
            compose_files=self.target.compose_files,
            env_file=self.target.env_file,
            remote_dir=self.target.remote_dir,
            domain=self.target.domain,
            stop_services=self.source.stop_services,
            disable_services=self.source.disable_services,
            delete_k3s_namespaces=self.source.delete_k3s_namespaces,
            verify_url=self.target.verify_url,
            verify_version=self.target.verify_version or self.target.version,
        )


# ── MigrationPlan (output of plan, input to apply) ───────────────────────────

class MigrationPlan(BaseModel):
    """Full migration plan — output of `plan`, input to `apply`."""
    infra_file: str = "infra.yaml"
    target_file: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    host: str
    app: str
    from_strategy: DeployStrategy
    to_strategy: DeployStrategy

    risk: ConflictSeverity = ConflictSeverity.LOW
    estimated_downtime: str = "unknown"
    steps: list[MigrationStep] = Field(default_factory=list)

    notes: list[str] = Field(default_factory=list)


# ── ProjectManifest (redeploy.yaml — project-level config) ───────────────────

class ProjectManifest(BaseModel):
    """Per-project redeploy.yaml — replaces repetitive Makefile variables.

    Place ``redeploy.yaml`` in the project root; then just run ``redeploy run``
    with no arguments and it will pick up spec, host, app, domain automatically.

    Example::

        spec: migration.yaml
        local_spec: migration-local.yaml
        host: root@1.2.3.4
        app: myapp
        domain: myapp.example.com
        ssh_key: ~/.ssh/id_ed25519
    """
    spec: str = "migration.yaml"
    local_spec: str = "migration-local.yaml"
    host: Optional[str] = None
    app: str = "app"
    domain: Optional[str] = None
    ssh_key: Optional[str] = None
    ssh_port: int = 22
    remote_dir: Optional[str] = None
    env_file: str = ".env"

    @classmethod
    def find_and_load(cls, start: "Path") -> "Optional[ProjectManifest]":  # type: ignore[name-defined]
        """Walk up from *start* looking for redeploy.yaml."""
        import yaml
        from pathlib import Path
        for d in [Path(start)] + list(Path(start).parents):
            candidate = d / "redeploy.yaml"
            if candidate.exists():
                with candidate.open() as f:
                    return cls(**yaml.safe_load(f))
        return None

    def apply_to_spec(self, spec: "MigrationSpec") -> None:
        """Overlay manifest values onto a MigrationSpec (host/domain/ssh_key)."""
        if self.host:
            spec.source.host = self.host
            spec.target.host = self.host
        if self.domain and not spec.target.domain:
            spec.target.domain = self.domain
        if self.remote_dir and not spec.target.remote_dir:
            spec.target.remote_dir = self.remote_dir


# ── DeviceRegistry (znane urządzenia + historia deployów) ─────────────────────

class DeployRecord(BaseModel):
    """Single deployment event recorded for a device."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    spec_name: str = ""
    from_strategy: str = ""
    to_strategy: str = ""
    version: str = ""
    ok: bool = True
    steps_total: int = 0
    steps_ok: int = 0
    note: str = ""


class KnownDevice(BaseModel):
    """Device known to redeploy — persisted in ~/.config/redeploy/devices.yaml."""
    id: str                              # unique: user@ip or hostname
    host: str                            # SSH target: user@ip
    name: str = ""                       # human-friendly label
    tags: list[str] = Field(default_factory=list)
    strategy: str = "docker_full"        # last known deploy strategy
    app: str = ""                        # last deployed app
    domain: str = ""
    remote_dir: str = ""
    ssh_port: int = 22
    ssh_key: Optional[str] = None        # None = auto-detect

    # Discovery metadata
    ip: str = ""
    mac: str = ""
    hostname: str = ""
    last_seen: Optional[datetime] = None
    last_ssh_ok: Optional[datetime] = None
    source: str = "manual"              # manual | arp | mdns | known_hosts

    # Deploy history
    deploys: list[DeployRecord] = Field(default_factory=list)

    @property
    def last_deploy(self) -> Optional[DeployRecord]:
        return self.deploys[-1] if self.deploys else None

    @property
    def is_reachable(self) -> bool:
        if self.last_seen is None:
            return False
        return (datetime.utcnow() - self.last_seen).total_seconds() < 300

    def record_deploy(self, record: DeployRecord) -> None:
        self.deploys.append(record)
        # Keep last 50 deploy records per device
        self.deploys = self.deploys[-50:]


class DeviceRegistry(BaseModel):
    """Persistent device registry — stored at ~/.config/redeploy/devices.yaml."""
    devices: list[KnownDevice] = Field(default_factory=list)
    _path: Optional[Path] = PrivateAttr(default=None)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def get(self, device_id: str) -> Optional[KnownDevice]:
        return next((d for d in self.devices if d.id == device_id), None)

    def upsert(self, device: KnownDevice) -> None:
        for i, d in enumerate(self.devices):
            if d.id == device.id:
                self.devices[i] = device
                return
        self.devices.append(device)

    def remove(self, device_id: str) -> bool:
        before = len(self.devices)
        self.devices = [d for d in self.devices if d.id != device_id]
        return len(self.devices) < before

    def by_tag(self, tag: str) -> list[KnownDevice]:
        return [d for d in self.devices if tag in d.tags]

    def by_strategy(self, strategy: str) -> list[KnownDevice]:
        return [d for d in self.devices if d.strategy == strategy]

    def reachable(self) -> list[KnownDevice]:
        return [d for d in self.devices if d.is_reachable]

    # ── persistence ───────────────────────────────────────────────────────────

    @classmethod
    def default_path(cls) -> Path:
        return Path.home() / ".config" / "redeploy" / "devices.yaml"

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "DeviceRegistry":
        import yaml
        p = path or cls.default_path()
        if not p.exists():
            return cls()
        raw = yaml.safe_load(p.read_text()) or {}
        devices = [KnownDevice(**d) for d in raw.get("devices", [])]
        reg = cls(devices=devices)
        reg._path = p
        return reg

    def save(self, path: Optional[Path] = None) -> None:
        import yaml
        p = path or self._path or self.default_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        # Permissions: 600 — registry may contain SSH key paths
        data = {"devices": [d.model_dump(mode="json") for d in self.devices]}
        tmp = p.with_suffix(".tmp")
        tmp.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False))
        tmp.chmod(0o600)
        tmp.replace(p)

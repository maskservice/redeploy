"""Shared data models for redeploy: InfraState, MigrationPlan, Target."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, PrivateAttr, field_validator


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
    DOCKER_HEALTH_WAIT = "docker_health_wait"   # wait until all containers healthy
    CONTAINER_LOG_TAIL = "container_log_tail"   # tail container logs after start
    PODMAN_BUILD = "podman_build"               # podman build with progress polling
    RSYNC = "rsync"
    SCP = "scp"
    SSH_CMD = "ssh_cmd"
    HTTP_CHECK = "http_check"
    VERSION_CHECK = "version_check"
    WAIT = "wait"
    PLUGIN = "plugin"              # custom plugin action
    INLINE_SCRIPT = "inline_script"  # multiline bash script from YAML
    ENSURE_CONFIG_LINE = "ensure_config_line"  # idempotent config.txt editing
    RASPI_CONFIG = "raspi_config"  # raspi-config nonint wrapper
    ENSURE_KANSHI_PROFILE = "ensure_kanshi_profile"    # write/replace kanshi output profile
    ENSURE_AUTOSTART_ENTRY = "ensure_autostart_entry"  # idempotent autostart line
    ENSURE_BROWSER_KIOSK_SCRIPT = "ensure_browser_kiosk_script"  # write kiosk-launch.sh


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
    KIOSK_APPLIANCE = "kiosk_appliance"  # full install flow (doql: kiosk-appliance)
    PODMAN_QUADLET = "podman_quadlet"
    K3S = "k3s"
    SYSTEMD = "systemd"
    UNKNOWN = "unknown"


# doql / external tool aliases → canonical DeployStrategy values
_STRATEGY_ALIASES: dict[str, str] = {
    "docker-compose":  "docker_full",
    "quadlet":         "podman_quadlet",
    "kiosk-appliance": "kiosk_appliance",
    "kiosk_appliance": "kiosk_appliance",  # already canonical, keep for safety
    "kubernetes":      "k3s",
    "k8s":             "k3s",
    "native-kiosk":    "native_kiosk",
    "docker-kiosk":    "docker_kiosk",
}


# ── PersistedModel mixin ────────────────────────────────────────────────────────

class PersistedModel(BaseModel):
    """Mixin for models that can be persisted to/from YAML files."""

    def to_yaml(self) -> str:
        """Serialize model to YAML string."""
        return yaml.dump(
            self.model_dump(mode="json"),
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )

    @classmethod
    def load(cls, path: Path) -> Self:
        """Load model from YAML file."""
        raw = yaml.safe_load(path.read_text())
        return cls(**raw)


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
    chromium: Optional[str] = None


class AppHealthInfo(BaseModel):
    url: str
    status_code: Optional[int] = None
    version: Optional[str] = None
    healthy: bool = False
    response_ms: Optional[float] = None


# ── Hardware (output of hardware probe) ───────────────────────────────────────

class DrmOutput(BaseModel):
    """One DRM connector (e.g. card1-DSI-2, card2-HDMI-A-1)."""
    name: str                           # e.g. "card1-DSI-2"
    connector: str                      # e.g. "DSI-2", "HDMI-A-1"
    status: str = "unknown"             # connected / disconnected
    enabled: str = "unknown"            # enabled / disabled
    modes: list[str] = Field(default_factory=list)    # e.g. ["1280x800@60"]
    transform: str = "normal"
    position: str = "0,0"
    scale: str = "1.0"
    edid_bytes: int = 0                 # EDID size in bytes; 0 = no physical panel
    power_state: Optional[str] = None  # DPMS: "on", "off", "suspend" — /sys/class/drm/<name>/dpms
    sysfs_path: str = ""               # e.g. /sys/class/drm/card1-DSI-2


class BacklightInfo(BaseModel):
    """Sysfs backlight device."""
    name: str                           # e.g. "11-0045"
    brightness: int = 0
    max_brightness: int = 255
    bl_power: int = 0                   # 0=on, 4=off
    display_name: Optional[str] = None  # e.g. "DSI-2"
    sysfs_path: str = ""               # e.g. /sys/class/backlight/11-0045


class I2CBusInfo(BaseModel):
    bus: int
    devices: list[str] = Field(default_factory=list)  # hex addresses found
    sysfs_path: str = ""               # e.g. /dev/i2c-11


class HardwareDiagnostic(BaseModel):
    """Problem found during hardware probe."""
    component: str                      # "dsi", "backlight", "i2c", "gpio", "overlay"
    severity: str = "warning"           # info / warning / error / critical
    message: str
    fix: Optional[str] = None          # suggested fix command or action


class HardwareInfo(BaseModel):
    """Hardware state produced by hardware probe."""
    board: Optional[str] = None         # e.g. "Raspberry Pi 5 Model B Rev 1.0"
    kernel: Optional[str] = None        # uname -r
    config_txt: str = ""                # full /boot/firmware/config.txt
    config_txt_path: str = "/boot/firmware/config.txt"  # probed path, varies by OS

    # Display
    drm_outputs: list[DrmOutput] = Field(default_factory=list)
    backlights: list[BacklightInfo] = Field(default_factory=list)
    framebuffers: list[str] = Field(default_factory=list)   # /dev/fb* names
    wlr_outputs: list[dict] = Field(default_factory=list)   # raw wlr-randr output

    # DSI specific
    dsi_overlays: list[str] = Field(default_factory=list)   # active dtoverlay lines
    dsi_dmesg: list[str] = Field(default_factory=list)      # relevant dmesg lines
    dsi_dmesg_errors: list[str] = Field(default_factory=list)  # lines with fail/error from dsi_dmesg

    # I2C
    i2c_buses: list[I2CBusInfo] = Field(default_factory=list)

    # GPIO header
    gpio_4pin_detected: Optional[bool] = None  # 5V/GND/SDA/SCL header present

    # Kernel modules — names of loaded DRM/DSI/panel modules
    kernel_modules: list[str] = Field(default_factory=list)  # lsmod filtered

    # Wayland/compositor runtime state
    wayland_sockets: list[str] = Field(default_factory=list)  # e.g. ["wayland-0"]
    # process_name → list of PIDs; e.g. {"labwc": [1234], "chromium": [5678]}
    compositor_processes: dict[str, list[int]] = Field(default_factory=dict)

    # Diagnostics
    diagnostics: list[HardwareDiagnostic] = Field(default_factory=list)

    @property
    def has_dsi(self) -> bool:
        return any("DSI" in o.name for o in self.drm_outputs)

    @property
    def kms_enabled(self) -> bool:
        """True if vc4-kms-v3d overlay is present in config.txt."""
        return any(
            re.match(r'\s*dtoverlay=vc4-kms-v3d', line)
            for line in self.config_txt.splitlines()
            if not line.strip().startswith("#")
        )

    @property
    def dsi_connected(self) -> bool:
        """DRM reports connected — always True on RPi5 when DSI overlay is loaded."""
        return any("DSI" in o.name and o.status == "connected" for o in self.drm_outputs)

    @property
    def dsi_physically_connected(self) -> bool:
        """True only when a physical panel is present (EDID > 0 bytes)."""
        return any("DSI" in o.name and o.edid_bytes > 0 for o in self.drm_outputs)

    @property
    def dsi_enabled(self) -> bool:
        return any("DSI" in o.name and o.enabled == "enabled" for o in self.drm_outputs)

    @property
    def backlight_on(self) -> bool:
        return any(b.bl_power == 0 and b.brightness > 0 for b in self.backlights)

    @property
    def errors(self) -> list[HardwareDiagnostic]:
        return [d for d in self.diagnostics if d.severity in ("error", "critical")]

    @property
    def warnings(self) -> list[HardwareDiagnostic]:
        return [d for d in self.diagnostics if d.severity == "warning"]


class InfraState(BaseModel):
    """Full detected state of infrastructure — output of `detect`."""
    host: str                             # "root@1.2.3.4" or "local"
    app: str = "unknown"
    scanned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
    host: Optional[str] = None           # override InfraState.host when set
    app: str = ""
    version: Optional[str] = None

    compose_files: list[str] = Field(default_factory=list)
    env_file: Optional[str] = None
    remote_dir: str = ""
    domain: Optional[str] = None

    @field_validator("strategy", mode="before")
    @classmethod
    def _accept_strategy_aliases(cls, v: object) -> object:
        if isinstance(v, str):
            return _STRATEGY_ALIASES.get(v, v)
        return v

    stop_services: list[str] = Field(default_factory=list)   # systemd units to stop
    disable_services: list[str] = Field(default_factory=list)
    delete_k3s_namespaces: list[str] = Field(default_factory=list)

    verify_url: Optional[str] = None
    verify_version: Optional[str] = None

    # Deploy pattern (Phase 4) — optional multi-step strategy overlay
    pattern: Optional[str] = None           # "blue_green" | "canary" | "rollback_on_failure"
    pattern_config: dict[str, Any] = Field(default_factory=dict)


# ── MigrationStep ─────────────────────────────────────────────────────────────

class MigrationStep(BaseModel):
    id: str
    action: StepAction
    description: str
    status: StepStatus = StepStatus.PENDING

    # action-specific params
    service: Optional[str] = None        # systemctl service name
    command: Optional[str] = None        # raw SSH command or inline script
    command_ref: Optional[str] = None    # reference to script in markdown: "./file.md#section-id" or "#section-id"
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
    timeout: int = 300                   # step timeout in seconds
    log_lines: int = 20                  # lines to tail (container_log_tail)

    # plugin-specific params
    plugin_type: Optional[str] = None    # e.g. "browser_reload"
    plugin_params: dict = Field(default_factory=dict)  # passed to plugin

    # ensure_config_line params
    config_file: Optional[str] = None              # remote path, e.g. /boot/firmware/config.txt
    config_line: Optional[str] = None              # line to ensure presence of
    config_section: str = "all"                    # [all], [pi5], etc.
    config_replaces_pattern: Optional[str] = None  # regex — replace matching line

    # raspi_config params
    raspi_interface: Optional[str] = None   # i2c, spi, camera, onewire, ssh, vnc, serial
    raspi_state: Optional[str] = None       # enable, disable

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

    def resolve_versions(self, manifest_version: Optional[str] = None) -> None:
        """Resolve @manifest references in version fields.

        If manifest_version is provided, replaces '@manifest' with actual version.
        Called before deploy to ensure spec.version matches manifest.
        """
        if manifest_version:
            if self.source.version == "@manifest":
                self.source.version = manifest_version
            if self.target.version == "@manifest":
                self.target.version = manifest_version
            if self.target.verify_version == "@manifest":
                self.target.verify_version = manifest_version

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
    spec_path: Optional[str] = None  # Path to the original spec file (for command_ref resolution)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    host: str
    app: str
    from_strategy: DeployStrategy
    to_strategy: DeployStrategy

    risk: ConflictSeverity = ConflictSeverity.LOW
    estimated_downtime: str = "unknown"
    steps: list[MigrationStep] = Field(default_factory=list)

    notes: list[str] = Field(default_factory=list)


# ── ProjectManifest (redeploy.yaml — project-level config) ───────────────────

class EnvironmentConfig(BaseModel):
    """One named environment (prod / dev / rpi5 / staging …) in redeploy.yaml."""
    host: Optional[str] = None
    strategy: Optional[str] = None
    app: Optional[str] = None
    domain: Optional[str] = None
    remote_dir: Optional[str] = None
    env_file: Optional[str] = None
    ssh_key: Optional[str] = None
    ssh_port: int = 22
    verify_url: Optional[str] = None
    spec: Optional[str] = None           # override spec file for this env


class ProjectManifest(BaseModel):
    """Per-project redeploy.yaml — replaces repetitive Makefile variables.

    Place ``redeploy.yaml`` in the project root; then just run ``redeploy run``
    with no arguments and it will pick up spec, host, app, domain automatically.

    Supports named environments (prod/dev/rpi5/…).

    Example::

        spec: migration.yaml
        app: myapp

        environments:
          prod:
            host: root@87.106.87.183
            strategy: docker_full
            env_file: envs/vps.env
            verify_url: https://myapp.example.com/api/v1/health
          rpi5:
            host: pi@192.168.188.108
            strategy: systemd
            env_file: .env
            verify_url: http://192.168.188.108:8000/api/v1/health
          dev:
            host: local
            strategy: docker_full
            env_file: .env.local
            verify_url: http://localhost:8000/api/v1/health
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
    environments: dict[str, EnvironmentConfig] = Field(default_factory=dict)

    @classmethod
    def find_and_load(cls, start: "Path") -> "Optional[ProjectManifest]":  # type: ignore[name-defined]
        """Walk up from *start* looking for redeploy.css (preferred) or redeploy.yaml.

        Priority: redeploy.css > redeploy.less > redeploy.yaml
        """
        import yaml
        from pathlib import Path
        for d in [Path(start)] + list(Path(start).parents):
            # CSS-like DSL format — highest priority
            for css_name in ("redeploy.css", "redeploy.less"):
                candidate = d / css_name
                if candidate.exists():
                    from .dsl.loader import load_css
                    result = load_css(candidate)
                    if result.manifest:
                        return result.manifest
            # YAML fallback
            candidate = d / "redeploy.yaml"
            if candidate.exists():
                with candidate.open() as f:
                    return cls(**yaml.safe_load(f))
        return None

    @classmethod
    def find_css(cls, start: "Path") -> "Optional[Path]":  # type: ignore[name-defined]
        """Return path to redeploy.css/less if found, else None."""
        from pathlib import Path
        for d in [Path(start)] + list(Path(start).parents):
            for name in ("redeploy.css", "redeploy.less"):
                p = d / name
                if p.exists():
                    return p
        return None

    def env(self, name: str) -> "Optional[EnvironmentConfig]":
        """Return named environment config, or None if not defined."""
        return self.environments.get(name)

    def resolve_env(self, name: str) -> "EnvironmentConfig":
        """Return env config merged with manifest defaults (env overrides manifest)."""
        base = EnvironmentConfig(
            host=self.host,
            app=self.app,
            domain=self.domain,
            remote_dir=self.remote_dir,
            env_file=self.env_file,
            ssh_key=self.ssh_key,
            ssh_port=self.ssh_port,
        )
        override = self.environments.get(name)
        if not override:
            return base
        return EnvironmentConfig(
            host=override.host or base.host,
            strategy=override.strategy,
            app=override.app or base.app,
            domain=override.domain or base.domain,
            remote_dir=override.remote_dir or base.remote_dir,
            env_file=override.env_file or base.env_file,
            ssh_key=override.ssh_key or base.ssh_key,
            ssh_port=override.ssh_port if override.ssh_port != 22 else base.ssh_port,
            verify_url=override.verify_url,
            spec=override.spec,
        )

    @classmethod
    def from_dotenv(cls, project_dir: "Path") -> "Optional[ProjectManifest]":  # type: ignore[name-defined]
        """Read DEPLOY_* vars from .env file in project_dir as a fallback.

        Supports::

            DEPLOY_HOST=pi@192.168.188.108
            DEPLOY_STRATEGY=systemd
            DEPLOY_APP=c2004
            DEPLOY_ENV_FILE=.env
            DEPLOY_VERIFY_URL=http://192.168.188.108:8000/api/v1/health
        """
        from pathlib import Path
        env_path = Path(project_dir) / ".env"
        if not env_path.exists():
            return None
        data: dict = {}
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip().upper()
            v = v.strip().strip('"').strip("'")
            if k == "DEPLOY_HOST":
                data["host"] = v
            elif k == "DEPLOY_APP":
                data["app"] = v
            elif k == "DEPLOY_DOMAIN":
                data["domain"] = v
            elif k == "DEPLOY_ENV_FILE":
                data["env_file"] = v
            elif k == "DEPLOY_SSH_KEY":
                data["ssh_key"] = v
        if not data:
            return None
        return cls(**data)

    def apply_to_spec(self, spec: "MigrationSpec", env_name: str = "") -> None:
        """Overlay manifest values onto a MigrationSpec.

        If *env_name* is given, uses that environment's config (merged with defaults).
        """
        cfg = self.resolve_env(env_name) if env_name else self
        host = cfg.host if isinstance(cfg, EnvironmentConfig) else self.host
        domain = cfg.domain if isinstance(cfg, EnvironmentConfig) else self.domain
        remote_dir = cfg.remote_dir if isinstance(cfg, EnvironmentConfig) else self.remote_dir
        env_file = cfg.env_file if isinstance(cfg, EnvironmentConfig) else self.env_file
        verify_url = cfg.verify_url if isinstance(cfg, EnvironmentConfig) else None
        strategy_str = cfg.strategy if isinstance(cfg, EnvironmentConfig) else None

        if host:
            spec.source.host = host
            spec.target.host = host
        if domain and not spec.target.domain:
            spec.target.domain = domain
        if remote_dir and not spec.target.remote_dir:
            spec.target.remote_dir = remote_dir
        if env_file and not spec.target.env_file:
            spec.target.env_file = env_file
        if verify_url and not spec.target.verify_url:
            spec.target.verify_url = verify_url
        if strategy_str:
            try:
                spec.target.strategy = DeployStrategy(strategy_str)
            except ValueError:
                pass


# ── DeviceRegistry (znane urządzenia + historia deployów) ─────────────────────

class DeployRecord(BaseModel):
    """Single deployment event recorded for a device."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
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
    ssh_user: str = ""                   # SSH username that worked (auto-detected)
    last_seen: Optional[datetime] = None
    last_ssh_ok: Optional[datetime] = None
    source: str = "manual"              # manual | arp | mdns | known_hosts | probe

    # Hardware snapshot (optional — filled by `redeploy device-map`)
    hardware: Optional["HardwareInfo"] = None

    # Deploy history
    deploys: list[DeployRecord] = Field(default_factory=list)

    @property
    def last_deploy(self) -> Optional[DeployRecord]:
        return self.deploys[-1] if self.deploys else None

    @property
    def is_reachable(self) -> bool:
        if self.last_seen is None:
            return False
        return (datetime.now(timezone.utc) - self.last_seen).total_seconds() < 300

    def record_deploy(self, record: DeployRecord) -> None:
        self.deploys.append(record)
        # Keep last 50 deploy records per device
        self.deploys = self.deploys[-50:]


# ── DeviceMap (full device snapshot: identity + infra + hardware) ──────────────

_DEFAULT_DEVICE_MAP_DIR = Path.home() / ".config" / "redeploy" / "device-maps"


class DeviceMap(PersistedModel):
    """Full, persisted snapshot of a device: identity + InfraState + HardwareInfo.

    Standardized format analogous to source/target/InfraState — can be saved
    as YAML and later loaded for diff, audit or reporting.

    File is stored at::

        ~/.config/redeploy/device-maps/<device-id>.yaml

    Generate with::

        redeploy device-map pi@192.168.188.109
        redeploy device-map pi@192.168.188.109 --save
        redeploy device-map pi@192.168.188.109 --save --out ./rpi5.device-map.yaml
    """

    # Identity
    id: str                                  # e.g. "pi@192.168.188.109"
    host: str                                # SSH target
    name: str = ""                           # optional human label
    tags: list[str] = Field(default_factory=list)

    # Timestamps
    scanned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Sub-maps
    hardware: Optional[HardwareInfo] = None
    infra: Optional[InfraState] = None

    # Diagnostics summary (merged from hardware + infra)
    issues: list[dict] = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(i.get("severity") in ("error", "critical") for i in self.issues)

    @property
    def display_summary(self) -> str:
        """Human-readable one-liner for the display state."""
        if not self.hardware:
            return "no hardware data"
        hw = self.hardware
        dsi = next((o for o in hw.drm_outputs if "DSI" in o.name), None)
        if dsi:
            mode = dsi.modes[0] if dsi.modes else "?"
            bl = hw.backlights[0].brightness if hw.backlights else "?"
            return f"DSI {dsi.connector} {dsi.status} {mode} backlight={bl}"
        return "no DSI"

    def save(self, path: Optional[Path] = None) -> Path:
        p = path or _DEFAULT_DEVICE_MAP_DIR / f"{self.id.replace('/', '_').replace('@', '_at_')}.yaml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_yaml())
        return p

    @classmethod
    def load_for(cls, device_id: str) -> Optional["DeviceMap"]:
        """Load saved DeviceMap for a device id, or None if not found."""
        p = _DEFAULT_DEVICE_MAP_DIR / f"{device_id.replace('/', '_').replace('@', '_at_')}.yaml"
        if p.exists():
            return cls.load(p)
        return None

    @classmethod
    def list_saved(cls) -> list[Path]:
        if not _DEFAULT_DEVICE_MAP_DIR.exists():
            return []
        return sorted(_DEFAULT_DEVICE_MAP_DIR.glob("*.yaml"))


# ── DeviceBlueprint ────────────────────────────────────────────────────────────

_DEFAULT_BLUEPRINT_DIR = Path.home() / ".config" / "redeploy" / "blueprints"


class ServicePort(BaseModel):
    """A single port mapping for a container service."""
    host: int
    container: int
    protocol: str = "tcp"


class VolumeMount(BaseModel):
    host: str
    container: str
    read_only: bool = False


class ServiceSpec(BaseModel):
    """Complete specification of a single containerised service."""
    name: str
    image: str                                          # full image ref incl. tag
    platform: str = ""                                  # e.g. "linux/arm64", "linux/amd64"
    ports: list[ServicePort] = Field(default_factory=list)
    volumes: list[VolumeMount] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    command: Optional[str] = None
    healthcheck: Optional[str] = None                   # curl / wget one-liner
    depends_on: list[str] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)
    restart: str = "unless-stopped"
    network_mode: Optional[str] = None
    privileged: bool = False

    # Source of truth — where this spec was extracted from
    source_ref: Optional[str] = None                    # "migration.yaml#deploy-backend"


class HardwareRequirements(BaseModel):
    """Hardware capabilities required to run the blueprint."""
    arch: str = "linux/arm64"                           # target CPU arch
    min_ram_mb: int = 0
    min_disk_gb: int = 0
    display_type: Optional[str] = None                  # "DSI" | "HDMI" | None
    display_resolution: Optional[str] = None            # "1280x800"
    i2c_required: bool = False
    gpio_required: bool = False
    features: list[str] = Field(default_factory=list)   # ["wayland", "kiosk", "gpu"]


class BlueprintSource(BaseModel):
    """Where the blueprint was extracted from — audit trail."""
    device_id: Optional[str] = None                     # "pi@192.168.188.109"
    device_name: Optional[str] = None
    migration_file: Optional[str] = None                # migration.yaml path used
    markpact_files: list[str] = Field(default_factory=list)
    compose_files: list[str] = Field(default_factory=list)
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DeviceBlueprint(PersistedModel):
    """Self-contained, portable deployment recipe.

    A DeviceBlueprint captures everything needed to reproduce a deployment on
    any target device — physical *or* virtual.  It is extracted either from a
    running device (via DeviceMap + InfraState) or compiled from definition
    files (migration.yaml, markpact markdown, docker-compose).

    Targets:

    * **physical**  — ``redeploy blueprint deploy rpi5.blueprint.yaml pi@host``
      generates a migration.yaml tailored to the new host.
    * **digital twin** — ``redeploy blueprint twin rpi5.blueprint.yaml``
      generates a ``docker-compose.twin.yml`` that runs the full stack locally
      (amd64), mocking hardware dependencies.

    Stored at::

        ~/.config/redeploy/blueprints/<name>.blueprint.yaml
    """

    # Identity
    name: str                                           # e.g. "c2004-kiosk"
    version: str = "0.0.0"
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Service definitions
    services: list[ServiceSpec] = Field(default_factory=list)

    # Hardware profile of the *original* device
    hardware: HardwareRequirements = Field(default_factory=HardwareRequirements)

    # Extra infra metadata
    app_url: Optional[str] = None                       # main endpoint, e.g. "http://host:8100"
    deploy_strategy: str = "podman_quadlet"             # podman_quadlet | docker_compose | systemd
    env_file: Optional[str] = None                      # .env file template (relative)
    notes: str = ""

    # Audit trail
    source: BlueprintSource = Field(default_factory=BlueprintSource)

    # ── helpers ───────────────────────────────────────────────────────────────

    def service(self, name: str) -> Optional[ServiceSpec]:
        return next((s for s in self.services if s.name == name), None)

    def save(self, path: Optional[Path] = None) -> Path:
        p = path or _DEFAULT_BLUEPRINT_DIR / f"{self.name}.blueprint.yaml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_yaml())
        return p

    @classmethod
    def list_saved(cls) -> list[Path]:
        if not _DEFAULT_BLUEPRINT_DIR.exists():
            return []
        return sorted(_DEFAULT_BLUEPRINT_DIR.glob("*.blueprint.yaml"))


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

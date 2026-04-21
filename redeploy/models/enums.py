"""Shared enums and type aliases for redeploy models."""
from __future__ import annotations

from enum import Enum


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
    DOCKER_HEALTH_WAIT = "docker_health_wait"
    CONTAINER_LOG_TAIL = "container_log_tail"
    PODMAN_BUILD = "podman_build"
    RSYNC = "rsync"
    SCP = "scp"
    SSH_CMD = "ssh_cmd"
    HTTP_CHECK = "http_check"
    VERSION_CHECK = "version_check"
    WAIT = "wait"
    PLUGIN = "plugin"
    INLINE_SCRIPT = "inline_script"
    ENSURE_CONFIG_LINE = "ensure_config_line"
    RASPI_CONFIG = "raspi_config"
    ENSURE_KANSHI_PROFILE = "ensure_kanshi_profile"
    ENSURE_AUTOSTART_ENTRY = "ensure_autostart_entry"
    ENSURE_BROWSER_KIOSK_SCRIPT = "ensure_browser_kiosk_script"


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
    KIOSK_APPLIANCE = "kiosk_appliance"
    PODMAN_QUADLET = "podman_quadlet"
    K3S = "k3s"
    SYSTEMD = "systemd"
    UNKNOWN = "unknown"


# doql / external tool aliases → canonical DeployStrategy values
_STRATEGY_ALIASES: dict[str, str] = {
    "docker-compose":  "docker_full",
    "quadlet":         "podman_quadlet",
    "kiosk-appliance": "kiosk_appliance",
    "kiosk_appliance": "kiosk_appliance",
    "kubernetes":      "k3s",
    "k8s":             "k3s",
    "native-kiosk":    "native_kiosk",
    "docker-kiosk":    "docker_kiosk",
}

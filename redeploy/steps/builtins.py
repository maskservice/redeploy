"""Built-in :class:`MigrationStep` definitions organised by domain.

Each constant is a frozen template returned by :func:`_step`; the
:class:`~redeploy.steps.StepLibrary` registry collects them at import time.
"""
from __future__ import annotations

from typing import Any

from ..models import ConflictSeverity, MigrationStep, StepAction


def _step(id: str, action: StepAction, description: str, **kw: Any) -> MigrationStep:
    return MigrationStep(id=id, action=action, description=description, **kw)


# ── k3s / kube ────────────────────────────────────────────────────────────────

FLUSH_K3S_IPTABLES = _step(
    id="flush_k3s_iptables",
    action=StepAction.SSH_CMD,
    description="Flush k3s CNI-HOSTPORT-DNAT + KUBE-* chains (stale rules block Docker-proxy on 80/443)",
    command=(
        "iptables -t nat -F CNI-HOSTPORT-DNAT 2>/dev/null || true && "
        "iptables -t nat -F CNI-HOSTPORT-MASQ 2>/dev/null || true && "
        "iptables -t nat -F KUBE-SERVICES 2>/dev/null || true && "
        "iptables -t nat -F KUBE-NODEPORTS 2>/dev/null || true && "
        "iptables -t filter -F KUBE-FORWARD 2>/dev/null || true && "
        "echo iptables-flushed"
    ),
    risk=ConflictSeverity.LOW,
)

DELETE_K3S_INGRESSES = _step(
    id="delete_k3s_ingresses",
    action=StepAction.KUBECTL_DELETE,
    description="Delete k3s ingresses to remove iptables DNAT rules",
    command="k3s kubectl delete ingress --all-namespaces --all 2>/dev/null || true",
    risk=ConflictSeverity.LOW,
)

STOP_K3S = _step(
    id="stop_k3s",
    action=StepAction.SYSTEMCTL_STOP,
    service="k3s",
    description="Stop k3s to free ports 80/443",
    command="systemctl stop k3s",
    risk=ConflictSeverity.MEDIUM,
    rollback_command="systemctl start k3s",
)

DISABLE_K3S = _step(
    id="disable_k3s",
    action=StepAction.SYSTEMCTL_DISABLE,
    service="k3s",
    description="Disable k3s on boot",
    command="systemctl disable k3s",
    risk=ConflictSeverity.LOW,
)


# ── nginx ─────────────────────────────────────────────────────────────────────

STOP_NGINX = _step(
    id="stop_nginx",
    action=StepAction.SYSTEMCTL_STOP,
    service="nginx",
    description="Stop host nginx (conflicts on port 80)",
    command="systemctl stop nginx && systemctl disable nginx",
    risk=ConflictSeverity.MEDIUM,
    rollback_command="systemctl start nginx",
)


# ── traefik ───────────────────────────────────────────────────────────────────

RESTART_TRAEFIK = _step(
    id="restart_traefik",
    action=StepAction.SSH_CMD,
    description="Restart Traefik container",
    command="docker restart $(docker ps -q --filter name=traefik) 2>/dev/null || true",
    risk=ConflictSeverity.LOW,
)


# ── docker ────────────────────────────────────────────────────────────────────

DOCKER_PRUNE = _step(
    id="docker_prune",
    action=StepAction.SSH_CMD,
    description="Prune unused Docker images and build cache",
    command="docker image prune -f && docker builder prune -f",
    risk=ConflictSeverity.LOW,
)

DOCKER_COMPOSE_DOWN = _step(
    id="docker_compose_down",
    action=StepAction.DOCKER_COMPOSE_DOWN,
    description="Stop Docker Compose stack",
    command="docker compose down",
    risk=ConflictSeverity.MEDIUM,
    rollback_command="docker compose up -d",
)


# ── waits ─────────────────────────────────────────────────────────────────────

WAIT_30 = _step(
    id="wait_startup",
    action=StepAction.WAIT,
    description="Wait 30 s for services to start",
    seconds=30,
    risk=ConflictSeverity.LOW,
)

WAIT_60 = _step(
    id="wait_startup_long",
    action=StepAction.WAIT,
    description="Wait 60 s for services to start (slow build)",
    seconds=60,
    risk=ConflictSeverity.LOW,
)


# ── verify ────────────────────────────────────────────────────────────────────

HTTP_HEALTH_CHECK = _step(
    id="http_health_check",
    action=StepAction.HTTP_CHECK,
    description="Verify backend health endpoint",
    url=None,   # must be set by caller
    expect="healthy",
    risk=ConflictSeverity.LOW,
)

VERSION_CHECK = _step(
    id="version_check",
    action=StepAction.VERSION_CHECK,
    description="Verify deployed version",
    url=None,   # must be set by caller
    expect=None,
    risk=ConflictSeverity.LOW,
)


# ── data / env ────────────────────────────────────────────────────────────────

SYNC_ENV = _step(
    id="sync_env",
    action=StepAction.SCP,
    description="Copy .env file to remote",
    src=None,   # caller sets src/dst
    dst=None,
    risk=ConflictSeverity.LOW,
)


# ── quadlet / podman ─────────────────────────────────────────────────────────

PODMAN_DAEMON_RELOAD = _step(
    id="podman_daemon_reload",
    action=StepAction.SYSTEMCTL_START,
    description="Reload systemd to pick up Quadlet unit files",
    command="systemctl --user daemon-reload",
    risk=ConflictSeverity.LOW,
)

STOP_PODMAN = _step(
    id="stop_podman",
    action=StepAction.SYSTEMCTL_STOP,
    service="podman",
    description="Stop all Podman containers via systemd",
    command="systemctl stop podman.service 2>/dev/null || podman stop --all 2>/dev/null || true",
    risk=ConflictSeverity.MEDIUM,
    rollback_command="systemctl start podman.service 2>/dev/null || true",
)

ENABLE_PODMAN_UNIT = _step(
    id="enable_podman_unit",
    action=StepAction.SYSTEMCTL_START,
    description="Enable and start a Podman Quadlet unit (set service= to override)",
    command="systemctl daemon-reload && systemctl enable --now {service}.service",
    risk=ConflictSeverity.LOW,
)


# ── systemd generic ───────────────────────────────────────────────────────────

SYSTEMCTL_RESTART = _step(
    id="systemctl_restart",
    action=StepAction.SYSTEMCTL_START,
    description="Restart a systemd service (set command= to override)",
    command="systemctl restart {service}",
    risk=ConflictSeverity.LOW,
)

SYSTEMCTL_DAEMON_RELOAD = _step(
    id="systemctl_daemon_reload",
    action=StepAction.SSH_CMD,
    description="Reload systemd daemon",
    command="systemctl daemon-reload",
    risk=ConflictSeverity.LOW,
)


# ── git ───────────────────────────────────────────────────────────────────────

GIT_PULL = _step(
    id="git_pull",
    action=StepAction.SSH_CMD,
    description="Pull latest code from git (cd to remote_dir first)",
    command="git -C ~/app pull --ff-only",
    risk=ConflictSeverity.LOW,
    rollback_command="git -C ~/app reset --hard HEAD@{1}",
)


# ── process control ───────────────────────────────────────────────────────────

KILL_PROCESSES_ON_PORTS = _step(
    id="kill_processes_on_ports",
    action=StepAction.PLUGIN,
    plugin_type="process_control",
    description="Kill processes on specified ports (auto-detects PIDs)",
    plugin_params={"ports": [], "strategy": "graceful", "timeout": 10, "notify": True},
    risk=ConflictSeverity.LOW,
)

KILL_DEV_PROCESSES = _step(
    id="kill_dev_processes",
    action=StepAction.PLUGIN,
    plugin_type="process_control",
    description="Kill common dev server processes (vite, uvicorn, python)",
    plugin_params={"ports": [8100, 8101, 8202, 3000, 5173], "strategy": "graceful", "timeout": 5, "notify": True},
    risk=ConflictSeverity.LOW,
)


# ── hardware diagnostic ─────────────────────────────────────────────────────────

HARDWARE_DIAGNOSTIC = _step(
    id="hardware_diagnostic",
    action=StepAction.PLUGIN,
    plugin_type="hardware_diagnostic",
    description="Analyze system hardware and provide configuration recommendations",
    plugin_params={"checks": ["platform", "cpu", "memory", "storage"], "platform": "auto", "verbose": True},
    risk=ConflictSeverity.LOW,
)


# Flat list consumed by the registry in ``__init__.py``.
ALL: list[MigrationStep] = [
    FLUSH_K3S_IPTABLES,
    DELETE_K3S_INGRESSES,
    STOP_K3S,
    DISABLE_K3S,
    STOP_NGINX,
    RESTART_TRAEFIK,
    DOCKER_PRUNE,
    DOCKER_COMPOSE_DOWN,
    WAIT_30,
    WAIT_60,
    HTTP_HEALTH_CHECK,
    VERSION_CHECK,
    SYNC_ENV,
    PODMAN_DAEMON_RELOAD,
    STOP_PODMAN,
    ENABLE_PODMAN_UNIT,
    SYSTEMCTL_RESTART,
    SYSTEMCTL_DAEMON_RELOAD,
    GIT_PULL,
    KILL_PROCESSES_ON_PORTS,
    KILL_DEV_PROCESSES,
    HARDWARE_DIAGNOSTIC,
]

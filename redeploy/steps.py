"""Step library — pre-defined, reusable named MigrationSteps.

Usage in a MigrationSpec::

    extra_steps:
      - id: flush_k3s_iptables   # references a library step by id
      - id: stop_nginx
      - id: http_health_check
        url: https://myapp.example.com/health

Usage from Python::

    from redeploy.steps import StepLibrary
    steps = StepLibrary.get("flush_k3s_iptables")
"""
from __future__ import annotations

from typing import Any, Optional

from .models import ConflictSeverity, MigrationStep, StepAction


# ── helpers ───────────────────────────────────────────────────────────────────


def _step(id: str, action: StepAction, description: str, **kw: Any) -> MigrationStep:
    return MigrationStep(id=id, action=action, description=description, **kw)


# ── k3s / kube ────────────────────────────────────────────────────────────────

_FLUSH_K3S_IPTABLES = _step(
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

_DELETE_K3S_INGRESSES = _step(
    id="delete_k3s_ingresses",
    action=StepAction.KUBECTL_DELETE,
    description="Delete k3s ingresses to remove iptables DNAT rules",
    command="k3s kubectl delete ingress --all-namespaces --all 2>/dev/null || true",
    risk=ConflictSeverity.LOW,
)

_STOP_K3S = _step(
    id="stop_k3s",
    action=StepAction.SYSTEMCTL_STOP,
    service="k3s",
    description="Stop k3s to free ports 80/443",
    command="systemctl stop k3s",
    risk=ConflictSeverity.MEDIUM,
    rollback_command="systemctl start k3s",
)

_DISABLE_K3S = _step(
    id="disable_k3s",
    action=StepAction.SYSTEMCTL_DISABLE,
    service="k3s",
    description="Disable k3s on boot",
    command="systemctl disable k3s",
    risk=ConflictSeverity.LOW,
)

# ── nginx ─────────────────────────────────────────────────────────────────────

_STOP_NGINX = _step(
    id="stop_nginx",
    action=StepAction.SYSTEMCTL_STOP,
    service="nginx",
    description="Stop host nginx (conflicts on port 80)",
    command="systemctl stop nginx && systemctl disable nginx",
    risk=ConflictSeverity.MEDIUM,
    rollback_command="systemctl start nginx",
)

# ── traefik ───────────────────────────────────────────────────────────────────

_RESTART_TRAEFIK = _step(
    id="restart_traefik",
    action=StepAction.SSH_CMD,
    description="Restart Traefik container",
    command="docker restart $(docker ps -q --filter name=traefik) 2>/dev/null || true",
    risk=ConflictSeverity.LOW,
)

# ── docker ────────────────────────────────────────────────────────────────────

_DOCKER_PRUNE = _step(
    id="docker_prune",
    action=StepAction.SSH_CMD,
    description="Prune unused Docker images and build cache",
    command="docker image prune -f && docker builder prune -f",
    risk=ConflictSeverity.LOW,
)

_DOCKER_COMPOSE_DOWN = _step(
    id="docker_compose_down",
    action=StepAction.DOCKER_COMPOSE_DOWN,
    description="Stop Docker Compose stack",
    command="docker compose down",
    risk=ConflictSeverity.MEDIUM,
    rollback_command="docker compose up -d",
)

# ── waits ─────────────────────────────────────────────────────────────────────

_WAIT_30 = _step(
    id="wait_startup",
    action=StepAction.WAIT,
    description="Wait 30 s for services to start",
    seconds=30,
    risk=ConflictSeverity.LOW,
)

_WAIT_60 = _step(
    id="wait_startup_long",
    action=StepAction.WAIT,
    description="Wait 60 s for services to start (slow build)",
    seconds=60,
    risk=ConflictSeverity.LOW,
)

# ── verify ────────────────────────────────────────────────────────────────────

_HTTP_HEALTH_CHECK = _step(
    id="http_health_check",
    action=StepAction.HTTP_CHECK,
    description="Verify backend health endpoint",
    url=None,   # must be set by caller
    expect="healthy",
    risk=ConflictSeverity.LOW,
)

_VERSION_CHECK = _step(
    id="version_check",
    action=StepAction.VERSION_CHECK,
    description="Verify deployed version",
    url=None,   # must be set by caller
    expect=None,
    risk=ConflictSeverity.LOW,
)

# ── data / env ────────────────────────────────────────────────────────────────

_SYNC_ENV = _step(
    id="sync_env",
    action=StepAction.SCP,
    description="Copy .env file to remote",
    src=None,   # caller sets src/dst
    dst=None,
    risk=ConflictSeverity.LOW,
)

# ── quadlet / podman ─────────────────────────────────────────────────────────

_PODMAN_DAEMON_RELOAD = _step(
    id="podman_daemon_reload",
    action=StepAction.SYSTEMCTL_START,
    description="Reload systemd to pick up Quadlet unit files",
    command="systemctl --user daemon-reload",
    risk=ConflictSeverity.LOW,
)

# ── registry ──────────────────────────────────────────────────────────────────

_LIBRARY: dict[str, MigrationStep] = {
    s.id: s for s in [
        _FLUSH_K3S_IPTABLES,
        _DELETE_K3S_INGRESSES,
        _STOP_K3S,
        _DISABLE_K3S,
        _STOP_NGINX,
        _RESTART_TRAEFIK,
        _DOCKER_PRUNE,
        _DOCKER_COMPOSE_DOWN,
        _WAIT_30,
        _WAIT_60,
        _HTTP_HEALTH_CHECK,
        _VERSION_CHECK,
        _SYNC_ENV,
        _PODMAN_DAEMON_RELOAD,
    ]
}


class StepLibrary:
    """Registry of pre-defined named MigrationSteps.

    Steps are returned as copies so callers can override individual fields::

        step = StepLibrary.get("http_health_check")
        step.url = "https://myapp.example.com/health"
        step.expect = "1.0.20"
    """

    @staticmethod
    def get(step_id: str, **overrides: Any) -> Optional[MigrationStep]:
        """Return a copy of a named step, optionally with field overrides.

        Returns ``None`` if the step_id is not in the library.
        """
        template = _LIBRARY.get(step_id)
        if template is None:
            return None
        data = template.model_dump()
        data.update(overrides)
        return MigrationStep(**data)

    @staticmethod
    def list() -> list[str]:
        """Return sorted list of available step IDs."""
        return sorted(_LIBRARY.keys())

    @staticmethod
    def all() -> dict[str, MigrationStep]:
        """Return full registry (copies)."""
        return {k: v.model_copy() for k, v in _LIBRARY.items()}

    @staticmethod
    def resolve_from_spec(raw: dict[str, Any]) -> MigrationStep:
        """Resolve a raw dict (from migration YAML extra_steps) to a MigrationStep.

        If ``id`` matches a library entry and no ``action`` is given, use the
        library template as base and merge the raw dict on top.
        """
        step_id = raw.get("id", "")
        template = _LIBRARY.get(step_id)
        if template:
            data = template.model_dump()
            data.update({k: v for k, v in raw.items() if v is not None})
            return MigrationStep(**data)
        return MigrationStep(**raw)

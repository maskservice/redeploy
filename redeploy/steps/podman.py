"""Podman / Quadlet domain steps."""
from __future__ import annotations

from ..models import ConflictSeverity, MigrationStep, StepAction


def _step(id: str, action: StepAction, description: str, **kw) -> MigrationStep:
    return MigrationStep(id=id, action=action, description=description, **kw)


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

ALL: list[MigrationStep] = [
    PODMAN_DAEMON_RELOAD,
    STOP_PODMAN,
    ENABLE_PODMAN_UNIT,
]

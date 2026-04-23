"""Generic / cross-domain utility steps."""
from __future__ import annotations

from ..models import ConflictSeverity, MigrationStep, StepAction


def _step(id: str, action: StepAction, description: str, **kw) -> MigrationStep:
    return MigrationStep(id=id, action=action, description=description, **kw)


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

ALL: list[MigrationStep] = [
    WAIT_30,
    WAIT_60,
    HTTP_HEALTH_CHECK,
    VERSION_CHECK,
    SYSTEMCTL_RESTART,
    SYSTEMCTL_DAEMON_RELOAD,
    STOP_NGINX,
]

"""Docker container runtime domain steps."""
from __future__ import annotations

from ..models import ConflictSeverity, MigrationStep, StepAction


def _step(id: str, action: StepAction, description: str, **kw) -> MigrationStep:
    return MigrationStep(id=id, action=action, description=description, **kw)


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

RESTART_TRAEFIK = _step(
    id="restart_traefik",
    action=StepAction.SSH_CMD,
    description="Restart Traefik container",
    command="docker restart $(docker ps -q --filter name=traefik) 2>/dev/null || true",
    risk=ConflictSeverity.LOW,
)

ALL: list[MigrationStep] = [
    DOCKER_PRUNE,
    DOCKER_COMPOSE_DOWN,
    RESTART_TRAEFIK,
]

"""Source-control management domain steps."""
from __future__ import annotations

from ..models import ConflictSeverity, MigrationStep, StepAction


def _step(id: str, action: StepAction, description: str, **kw) -> MigrationStep:
    return MigrationStep(id=id, action=action, description=description, **kw)


GIT_PULL = _step(
    id="git_pull",
    action=StepAction.SSH_CMD,
    description="Pull latest code from git (cd to remote_dir first)",
    command="git -C ~/app pull --ff-only",
    risk=ConflictSeverity.LOW,
    rollback_command="git -C ~/app reset --hard HEAD@{1}",
)

ALL: list[MigrationStep] = [
    GIT_PULL,
]

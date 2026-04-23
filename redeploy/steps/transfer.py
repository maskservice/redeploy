"""File-transfer domain steps."""
from __future__ import annotations

from ..models import ConflictSeverity, MigrationStep, StepAction


def _step(id: str, action: StepAction, description: str, **kw) -> MigrationStep:
    return MigrationStep(id=id, action=action, description=description, **kw)


SYNC_ENV = _step(
    id="sync_env",
    action=StepAction.SCP,
    description="Copy .env file to remote",
    src=None,   # caller sets src/dst
    dst=None,
    risk=ConflictSeverity.LOW,
)

ALL: list[MigrationStep] = [
    SYNC_ENV,
]

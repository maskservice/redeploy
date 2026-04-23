"""Hardware diagnostic domain steps."""
from __future__ import annotations

from ..models import ConflictSeverity, MigrationStep, StepAction


def _step(id: str, action: StepAction, description: str, **kw) -> MigrationStep:
    return MigrationStep(id=id, action=action, description=description, **kw)


HARDWARE_DIAGNOSTIC = _step(
    id="hardware_diagnostic",
    action=StepAction.PLUGIN,
    plugin_type="hardware_diagnostic",
    description="Analyze system hardware and provide configuration recommendations",
    plugin_params={"checks": ["platform", "cpu", "memory", "storage"], "platform": "auto", "verbose": True},
    risk=ConflictSeverity.LOW,
)

ALL: list[MigrationStep] = [
    HARDWARE_DIAGNOSTIC,
]

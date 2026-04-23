"""Process-control domain steps."""
from __future__ import annotations

from ..models import ConflictSeverity, MigrationStep, StepAction


def _step(id: str, action: StepAction, description: str, **kw) -> MigrationStep:
    return MigrationStep(id=id, action=action, description=description, **kw)


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

ALL: list[MigrationStep] = [
    KILL_PROCESSES_ON_PORTS,
    KILL_DEV_PROCESSES,
]

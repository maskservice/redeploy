"""Rollback functionality for migration execution."""
from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from ..models import MigrationStep
    from .state import ResumeState
    from ..detect.remote import RemoteProbe


def rollback_steps(
    completed_steps: list[MigrationStep],
    probe: RemoteProbe,
    state: ResumeState | None,
) -> list[str]:
    """Rollback completed steps in reverse order.

    Returns:
        List of step IDs that were successfully rolled back.
    """
    logger.warning("Rolling back completed steps...")
    rolled_back: list[str] = []

    for step in reversed(completed_steps):
        if step.rollback_command:
            logger.info(f"  ↩ rollback [{step.id}]: {step.rollback_command}")
            r = probe.run(step.rollback_command, timeout=120)
            if not r.ok:
                logger.warning(f"    rollback failed: {r.stderr[:100]}")
            else:
                rolled_back.append(step.id)

    # Forget rolled-back steps so a subsequent --resume re-executes them.
    if rolled_back and state is not None:
        state.completed_step_ids = [
            sid for sid in state.completed_step_ids
            if sid not in set(rolled_back)
        ]
        state.save()

    return rolled_back

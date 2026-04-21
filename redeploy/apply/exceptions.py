"""Exceptions for the apply package."""
from __future__ import annotations

from ..models import MigrationStep


class StepError(Exception):
    """Exception raised when a migration step fails."""

    def __init__(self, step: MigrationStep, msg: str):
        self.step = step
        super().__init__(f"[{step.id}] {msg}")

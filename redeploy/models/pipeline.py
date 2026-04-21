"""Pipeline hook models — generic pre/post/failure lifecycle."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


PipelinePhase = Literal[
    "before_plan",
    "before_apply",
    "before_step",
    "after_step",
    "on_step_failure",
    "on_step_retry",
    "after_apply",
    "on_failure",
    "always",
]


class Hook(BaseModel):
    """Generyczny hook w pipeline: faza + akcja + opcjonalny warunek.

    Zastępuje ad-hoc pola typu ``post_deploy``/``pre_deploy``/``insert_before``.
    Dodatkowe pola specyficzne dla akcji (command, url, ...) idą do ``extra``.
    """
    id: str
    phase: PipelinePhase
    action: str                                  # StepAction value (ssh_cmd, http_check, local_cmd, ...)
    description: str = ""
    when: Optional[str] = None                   # opcjonalny warunek
    on_failure: Literal["abort", "continue", "warn"] = "warn"

    model_config = {"extra": "allow"}            # zachowuje dodatkowe pola (command, url, ...)

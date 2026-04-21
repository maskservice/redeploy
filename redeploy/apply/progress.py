"""Progress emission for migration execution."""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from typing import IO, Optional

import yaml
from loguru import logger

from ..models import MigrationPlan, MigrationStep


class ProgressEmitter:
    """Emits YAML-formatted progress events to a stream (default: stdout).

    Each event is a YAML document (separated by ---) so consumers can
    parse the stream incrementally with yaml.safe_load_all().

    Event types:
      - start     : deployment begins
      - step_start: a single step begins
      - step_done : step completed successfully
      - step_fail : step failed with error
      - progress  : mid-step progress update (build cache, container status…)
      - done      : all steps completed
      - failed    : deployment failed
    """

    def __init__(self, stream: IO[str] = None):
        self._out = stream or sys.stdout
        self._t0 = time.monotonic()

    def _ts(self) -> str:
        return datetime.now(timezone.utc).strftime("%H:%M:%S")

    def _elapsed(self) -> float:
        return round(time.monotonic() - self._t0, 1)

    def _emit(self, event: dict) -> None:
        event.setdefault("ts", self._ts())
        event.setdefault("elapsed_s", self._elapsed())
        self._out.write("---\n")
        self._out.write(yaml.dump(event, default_flow_style=False, allow_unicode=True))
        self._out.flush()

    def start(self, plan: MigrationPlan) -> None:
        from ..models import StepStatus

        self._emit({
            "event": "start",
            "host": plan.host,
            "strategy": f"{plan.from_strategy.value} → {plan.to_strategy.value}",
            "total_steps": len(plan.steps),
            "steps": [
                {"n": i + 1, "id": s.id, "action": s.action.value,
                 "description": s.description, "status": s.status.value}
                for i, s in enumerate(plan.steps)
            ],
        })

    def step_start(self, n: int, step: MigrationStep) -> None:
        self._emit({
            "event": "step_start",
            "n": n,
            "id": step.id,
            "action": step.action.value,
            "description": step.description,
            "status": "running",
        })

    def step_done(self, n: int, step: MigrationStep) -> None:
        self._emit({
            "event": "step_done",
            "n": n,
            "id": step.id,
            "status": "done",
            "result": step.result,
        })

    def step_fail(self, n: int, step: MigrationStep, error: str) -> None:
        self._emit({
            "event": "step_fail",
            "n": n,
            "id": step.id,
            "status": "failed",
            "error": error,
        })

    def progress(self, step_id: str, message: str) -> None:
        self._emit({
            "event": "progress",
            "id": step_id,
            "message": message,
        })

    def done(self, total: int) -> None:
        self._emit({"event": "done", "steps_completed": total, "result": "ok"})

    def failed(self, completed: int, total: int, error: str) -> None:
        self._emit({
            "event": "failed",
            "steps_completed": completed,
            "steps_total": total,
            "error": error,
        })

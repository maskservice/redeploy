"""Executor — runs MigrationPlan steps, handles rollback on failure."""
from __future__ import annotations

import time
from pathlib import Path
from typing import IO, Optional

import yaml
from loguru import logger

from ..detect.remote import RemoteProbe
from ..models import MigrationPlan, MigrationStep, StepAction, StepStatus
from .exceptions import StepError
from .handlers import (
    run_ssh, run_scp, run_rsync, run_docker_build, run_podman_build,
    run_docker_health_wait, run_container_log_tail, run_http_check,
    run_version_check, run_plugin, run_wait, run_inline_script,
    run_ensure_config_line, run_raspi_config,
    run_ensure_kanshi_profile, run_ensure_autostart_entry, run_ensure_browser_kiosk_script,
)
from .progress import ProgressEmitter
from .rollback import rollback_steps
from .state import ResumeState, default_state_path


class Executor:
    """Execute MigrationPlan steps on a remote host."""

    def __init__(self, plan: MigrationPlan, dry_run: bool = False,
                 ssh_key: Optional[str] = None,
                 progress_yaml: bool = False,
                 progress_stream: IO[str] = None,
                 audit_log: bool = True,
                 audit_path: Optional["Path"] = None,
                 resume: bool = False,
                 from_step: Optional[str] = None,
                 state_path: Optional["Path"] = None,
                 spec_path: Optional[str] = None):
        self.plan = plan
        self.dry_run = dry_run
        self.probe = RemoteProbe(plan.host)
        if ssh_key:
            self.probe.key = ssh_key
        self._completed: list[MigrationStep] = []
        self._emitter: Optional[ProgressEmitter] = (
            ProgressEmitter(progress_stream) if progress_yaml else None
        )
        self._audit_log = audit_log
        self._audit_path = audit_path
        self._t0: float = 0.0

        # ── spec path for command_ref resolution ─────────────────────────────
        if spec_path and not plan.spec_path:
            plan.spec_path = spec_path

        # ── resume / checkpoint ──────────────────────────────────────────────
        self._resume = resume
        self._from_step = from_step
        spec_id = spec_path or plan.spec_path or plan.target_file or plan.infra_file or plan.app
        if state_path is None and not dry_run:
            state_path = default_state_path(spec_id, plan.host)
        self._state_path: Optional[Path] = (
            Path(state_path) if state_path is not None else None
        )
        self._state: Optional[ResumeState] = None
        if self._state_path is not None and not dry_run:
            self._state = ResumeState.load_or_new(
                self._state_path,
                spec_path=str(spec_id),
                host=plan.host,
                total_steps=len(plan.steps),
            )
            # Keep total_steps in sync if the spec changed between runs.
            self._state.total_steps = len(plan.steps)

    @property
    def completed_steps(self) -> list[MigrationStep]:
        return list(self._completed)

    @property
    def state(self) -> Optional[ResumeState]:
        """Current ResumeState (None when dry_run or disabled)."""
        return self._state

    @property
    def state_path(self) -> Optional[Path]:
        return self._state_path

    def run(self) -> bool:
        """Execute all steps. Returns True if all passed."""
        self._t0 = time.monotonic()
        prefix = "[DRY RUN] " if self.dry_run else ""
        logger.info(f"{prefix}Applying plan: {len(self.plan.steps)} steps "
                    f"({self.plan.from_strategy.value} → {self.plan.to_strategy.value})")
        if self._emitter:
            self._emitter.start(self.plan)

        skip_ids = self._compute_skip_set()
        if skip_ids:
            logger.info(f"resume: skipping {len(skip_ids)} already-completed step(s): "
                        f"{', '.join(sorted(skip_ids))}")

        ok = self._execute_steps_loop(skip_ids)
        elapsed = time.monotonic() - self._t0

        self._handle_completion(ok, elapsed)
        self._write_audit(ok=ok, elapsed_s=elapsed)
        return ok

    def _execute_steps_loop(self, skip_ids: set[str]) -> bool:
        """Execute steps, handling skips and errors. Returns True if all passed."""
        ok = True
        for i, step in enumerate(self.plan.steps, 1):
            if step.id in skip_ids:
                self._skip_step(i, step)
                continue

            try:
                if self._emitter:
                    self._emitter.step_start(i, step)
                self._execute_step(step)
                self._completed.append(step)
                if self._state is not None:
                    self._state.mark_done(step.id)
                if self._emitter:
                    self._emitter.step_done(i, step)
            except StepError as e:
                self._handle_step_failure(i, step, e)
                ok = False
                break
        return ok

    def _skip_step(self, i: int, step: MigrationStep) -> None:
        """Handle a skipped step due to resume."""
        step.status = StepStatus.SKIPPED
        step.result = "resumed: previously completed"
        if self._emitter:
            self._emitter.step_done(i, step)

    def _handle_step_failure(self, i: int, step: MigrationStep, error: StepError) -> None:
        """Handle a step failure."""
        logger.error(f"Step failed: {error}")
        step.status = StepStatus.FAILED
        step.error = str(error)
        if self._state is not None:
            self._state.mark_failed(step.id, str(error))
        if self._emitter:
            self._emitter.step_fail(i, step, str(error))
            self._emitter.failed(len(self._completed), len(self.plan.steps), str(error))
        if not self.dry_run:
            self._rollback()

    def _handle_completion(self, ok: bool, elapsed: float) -> None:
        """Handle plan completion or failure."""
        if ok:
            logger.info(f"{'[DRY RUN] ' if self.dry_run else ''}All {len(self.plan.steps)} steps completed")
            if self._emitter:
                self._emitter.done(len(self.plan.steps))
            # Plan finished cleanly — drop the checkpoint.
            if self._state is not None:
                self._state.remove()
        else:
            if self._state is not None and self._state_path is not None:
                logger.info(f"resume: checkpoint saved → {self._state_path} "
                            f"({self._state.completed_count}/{self._state.total_steps} done)")

    def _compute_skip_set(self) -> set[str]:
        """Determine which step ids should be skipped this run.

        Sources (in priority order):
          1. ``--from-step <id>``: skip every step BEFORE that id.
          2. ``--resume`` + persisted state: skip every previously completed id.
        """
        skip: set[str] = set()
        ids = [s.id for s in self.plan.steps]

        if self._from_step:
            if self._from_step not in ids:
                logger.warning(
                    f"--from-step '{self._from_step}' not found in plan; running full plan"
                )
            else:
                idx = ids.index(self._from_step)
                skip.update(ids[:idx])

        if self._resume and self._state is not None:
            skip.update(self._state.completed_step_ids)

        return skip

    def _write_audit(self, *, ok: bool, elapsed_s: float) -> None:
        if not self._audit_log:
            return
        try:
            from ..observe import DeployAuditLog
            log = DeployAuditLog(path=self._audit_path)
            log.record(self.plan, self._completed, ok=ok,
                       elapsed_s=elapsed_s, dry_run=self.dry_run)
        except Exception as exc:  # never crash the executor
            logger.debug(f"audit_log write failed (non-fatal): {exc}")

    # ── step dispatcher ───────────────────────────────────────────────────────

    def _execute_step(self, step: MigrationStep) -> None:
        logger.info(f"  {'[DRY]' if self.dry_run else '→'} [{step.id}] {step.description}")
        step.status = StepStatus.RUNNING

        if self.dry_run:
            step.status = StepStatus.DONE
            step.result = "dry-run"
            return

        dispatch = {
            StepAction.SYSTEMCTL_STOP:      lambda s: run_ssh(s, self.probe),
            StepAction.SYSTEMCTL_DISABLE:   lambda s: run_ssh(s, self.probe),
            StepAction.SYSTEMCTL_START:     lambda s: run_ssh(s, self.probe),
            StepAction.KUBECTL_DELETE:      lambda s: run_ssh(s, self.probe),
            StepAction.DOCKER_COMPOSE_UP:   lambda s: run_ssh(s, self.probe),
            StepAction.DOCKER_COMPOSE_DOWN: lambda s: run_ssh(s, self.probe),
            StepAction.DOCKER_BUILD:        lambda s: run_docker_build(s, self.probe, self._emitter),
            StepAction.DOCKER_HEALTH_WAIT:  lambda s: run_docker_health_wait(s, self.probe),
            StepAction.CONTAINER_LOG_TAIL:  lambda s: run_container_log_tail(s, self.probe),
            StepAction.PODMAN_BUILD:        lambda s: run_podman_build(s, self.probe, self._emitter),
            StepAction.SSH_CMD:             lambda s: run_ssh(s, self.probe),
            StepAction.SCP:                 lambda s: run_scp(s, self.probe, self.plan),
            StepAction.RSYNC:               lambda s: run_rsync(s, self.probe, self.plan),
            StepAction.HTTP_CHECK:          lambda s: run_http_check(s, self.probe),
            StepAction.VERSION_CHECK:       lambda s: run_version_check(s, self.probe),
            StepAction.WAIT:                lambda s: run_wait(s),
            StepAction.PLUGIN:              lambda s: run_plugin(s, self.probe, self.plan, self._emitter, self.dry_run),
            StepAction.INLINE_SCRIPT:       lambda s: run_inline_script(s, self.probe, self.plan),
            StepAction.ENSURE_CONFIG_LINE:  lambda s: run_ensure_config_line(s, self.probe),
            StepAction.RASPI_CONFIG:        lambda s: run_raspi_config(s, self.probe),
            StepAction.ENSURE_KANSHI_PROFILE:      lambda s: run_ensure_kanshi_profile(s, self.probe),
            StepAction.ENSURE_AUTOSTART_ENTRY:     lambda s: run_ensure_autostart_entry(s, self.probe),
            StepAction.ENSURE_BROWSER_KIOSK_SCRIPT: lambda s: run_ensure_browser_kiosk_script(s, self.probe),
        }

        handler = dispatch.get(step.action)
        if not handler:
            raise StepError(step, f"No handler for action {step.action}")
        handler(step)

    # ── rollback ──────────────────────────────────────────────────────────────

    def _rollback(self) -> None:
        rollback_steps(self._completed, self.probe, self._state)

    # ── summary ───────────────────────────────────────────────────────────────

    def summary(self) -> str:
        total = len(self.plan.steps)
        done = sum(1 for s in self.plan.steps if s.status == StepStatus.DONE)
        failed = sum(1 for s in self.plan.steps if s.status == StepStatus.FAILED)
        icon = "✅" if failed == 0 else "❌"
        return f"{icon} {done}/{total} steps completed" + (f", {failed} failed" if failed else "")

    @staticmethod
    def from_file(plan_path: Path) -> "Executor":
        with plan_path.open() as f:
            raw = yaml.safe_load(f)
        plan = MigrationPlan(**raw)
        return Executor(plan)

    def save_results(self, output: Path) -> None:
        data = self.plan.model_dump(mode="json")
        output.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True))
        logger.info(f"Results saved to {output}")

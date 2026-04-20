"""Executor — runs MigrationPlan steps, handles rollback on failure."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Optional

import httpx
import yaml
from loguru import logger

from ..detect.remote import RemoteProbe
from ..models import MigrationPlan, MigrationStep, StepAction, StepStatus


class StepError(Exception):
    def __init__(self, step: MigrationStep, msg: str):
        self.step = step
        super().__init__(f"[{step.id}] {msg}")


class Executor:
    """Execute MigrationPlan steps on a remote host."""

    def __init__(self, plan: MigrationPlan, dry_run: bool = False):
        self.plan = plan
        self.dry_run = dry_run
        self.probe = RemoteProbe(plan.host)
        self._completed: list[MigrationStep] = []

    def run(self) -> bool:
        """Execute all steps. Returns True if all passed."""
        prefix = "[DRY RUN] " if self.dry_run else ""
        logger.info(f"{prefix}Applying plan: {len(self.plan.steps)} steps "
                    f"({self.plan.from_strategy.value} → {self.plan.to_strategy.value})")

        for step in self.plan.steps:
            try:
                self._execute_step(step)
                self._completed.append(step)
            except StepError as e:
                logger.error(f"Step failed: {e}")
                step.status = StepStatus.FAILED
                step.error = str(e)
                if not self.dry_run:
                    self._rollback()
                return False

        logger.info(f"{'[DRY RUN] ' if self.dry_run else ''}All {len(self.plan.steps)} steps completed")
        return True

    # ── step dispatcher ───────────────────────────────────────────────────────

    def _execute_step(self, step: MigrationStep) -> None:
        logger.info(f"  {'[DRY]' if self.dry_run else '→'} [{step.id}] {step.description}")
        step.status = StepStatus.RUNNING

        if self.dry_run:
            step.status = StepStatus.DONE
            step.result = "dry-run"
            return

        dispatch = {
            StepAction.SYSTEMCTL_STOP:    self._run_ssh,
            StepAction.SYSTEMCTL_DISABLE: self._run_ssh,
            StepAction.SYSTEMCTL_START:   self._run_ssh,
            StepAction.KUBECTL_DELETE:    self._run_ssh,
            StepAction.DOCKER_COMPOSE_UP: self._run_ssh,
            StepAction.DOCKER_COMPOSE_DOWN: self._run_ssh,
            StepAction.DOCKER_BUILD:      self._run_ssh,
            StepAction.SSH_CMD:           self._run_ssh,
            StepAction.SCP:               self._run_scp,
            StepAction.RSYNC:             self._run_rsync,
            StepAction.HTTP_CHECK:        self._run_http_check,
            StepAction.VERSION_CHECK:     self._run_version_check,
            StepAction.WAIT:              self._run_wait,
        }

        handler = dispatch.get(step.action)
        if not handler:
            raise StepError(step, f"No handler for action {step.action}")
        handler(step)

    # ── handlers ─────────────────────────────────────────────────────────────

    def _run_ssh(self, step: MigrationStep) -> None:
        cmd = step.command
        if not cmd:
            raise StepError(step, "No command specified")
        r = self.probe.run(cmd, timeout=300)
        step.result = r.out[:500]
        if not r.ok:
            raise StepError(step, f"exit={r.returncode}: {r.stderr[:200]}")
        step.status = StepStatus.DONE

    def _run_scp(self, step: MigrationStep) -> None:
        if not step.src or not step.dst:
            raise StepError(step, "scp requires src and dst")
        if self.probe.is_local:
            cmd = ["cp", step.src, step.dst]
        else:
            cmd = ["scp", "-o", "StrictHostKeyChecking=no",
                   step.src, f"{self.plan.host}:{step.dst}"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise StepError(step, f"scp failed: {result.stderr[:200]}")
        step.status = StepStatus.DONE
        step.result = "ok"

    def _run_rsync(self, step: MigrationStep) -> None:
        if not step.src or not step.dst:
            raise StepError(step, "rsync requires src and dst")
        if self.probe.is_local:
            dst = step.dst
        else:
            dst = f"{self.plan.host}:{step.dst}"
        cmd = ["rsync", "-az", "--delete", step.src, dst]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise StepError(step, f"rsync failed: {result.stderr[:200]}")
        step.status = StepStatus.DONE
        step.result = "ok"

    def _run_http_check(self, step: MigrationStep, retries: int = 5, delay: int = 8) -> None:
        if not step.url:
            raise StepError(step, "http_check requires url")
        last_err = ""
        for attempt in range(retries):
            try:
                r = httpx.get(step.url, timeout=10, verify=False, follow_redirects=True)
                body = r.text
                if step.expect and step.expect not in body:
                    last_err = f"expected '{step.expect}' not found in response"
                elif r.status_code >= 400:
                    last_err = f"HTTP {r.status_code}"
                else:
                    step.status = StepStatus.DONE
                    step.result = body[:200]
                    return
            except Exception as e:
                last_err = str(e)
            logger.debug(f"    retry {attempt + 1}/{retries}: {last_err}")
            time.sleep(delay)
        raise StepError(step, f"HTTP check failed after {retries} retries: {last_err}")

    def _run_version_check(self, step: MigrationStep) -> None:
        if not step.url or not step.expect:
            raise StepError(step, "version_check requires url and expect")
        try:
            r = httpx.get(step.url, timeout=10, verify=False, follow_redirects=True)
            body = r.text
            if step.expect not in body:
                raise StepError(step, f"version '{step.expect}' not found in response: {body[:100]}")
            step.status = StepStatus.DONE
            step.result = f"version {step.expect} confirmed"
        except StepError:
            raise
        except Exception as e:
            raise StepError(step, str(e))

    def _run_wait(self, step: MigrationStep) -> None:
        if step.seconds > 0:
            logger.debug(f"    waiting {step.seconds}s...")
            time.sleep(step.seconds)
        step.status = StepStatus.DONE
        step.result = f"waited {step.seconds}s"

    # ── rollback ──────────────────────────────────────────────────────────────

    def _rollback(self) -> None:
        logger.warning("Rolling back completed steps...")
        for step in reversed(self._completed):
            if step.rollback_command:
                logger.info(f"  ↩ rollback [{step.id}]: {step.rollback_command}")
                r = self.probe.run(step.rollback_command, timeout=120)
                if not r.ok:
                    logger.warning(f"    rollback failed: {r.stderr[:100]}")

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

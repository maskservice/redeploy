"""Executor — runs MigrationPlan steps, handles rollback on failure."""
from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

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

    def __init__(self, plan: MigrationPlan, dry_run: bool = False,
                 ssh_key: Optional[str] = None):
        self.plan = plan
        self.dry_run = dry_run
        self.probe = RemoteProbe(plan.host)
        if ssh_key:
            self.probe.key = ssh_key
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
            StepAction.SYSTEMCTL_STOP:      self._run_ssh,
            StepAction.SYSTEMCTL_DISABLE:   self._run_ssh,
            StepAction.SYSTEMCTL_START:     self._run_ssh,
            StepAction.KUBECTL_DELETE:      self._run_ssh,
            StepAction.DOCKER_COMPOSE_UP:   self._run_ssh,
            StepAction.DOCKER_COMPOSE_DOWN: self._run_ssh,
            StepAction.DOCKER_BUILD:        self._run_docker_build,
            StepAction.DOCKER_HEALTH_WAIT:  self._run_docker_health_wait,
            StepAction.CONTAINER_LOG_TAIL:  self._run_container_log_tail,
            StepAction.SSH_CMD:             self._run_ssh,
            StepAction.SCP:                 self._run_scp,
            StepAction.RSYNC:               self._run_rsync,
            StepAction.HTTP_CHECK:          self._run_http_check,
            StepAction.VERSION_CHECK:       self._run_version_check,
            StepAction.WAIT:                self._run_wait,
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
            raise StepError(step, f"exit={r.exit_code}: {r.stderr[:200]}")
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
        cmd = ["rsync", "-az", "--delete"]
        for exc in step.excludes:
            cmd += ["--exclude", exc]
        cmd += [step.src, dst]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            raise StepError(step, f"rsync failed: {result.stderr[:200]}")
        step.status = StepStatus.DONE
        step.result = "ok"

    def _run_docker_build(self, step: MigrationStep) -> None:
        """Run docker compose build on remote with periodic progress polling."""
        cmd = step.command
        if not cmd:
            raise StepError(step, "No command specified")

        timeout = step.timeout or 1800  # 30 min default for first ARM64 build
        poll_interval = 15              # seconds between progress snapshots
        done_event = threading.Event()
        result_holder: list = []

        def _ssh_build() -> None:
            r = self.probe.run(cmd, timeout=timeout)
            result_holder.append(r)
            done_event.set()

        thread = threading.Thread(target=_ssh_build, daemon=True)
        thread.start()

        elapsed = 0
        while not done_event.wait(timeout=poll_interval):
            elapsed += poll_interval
            snap = self.probe.run(
                "docker system df 2>/dev/null | grep -E 'Image|Cache' | "
                "awk '{print $1, $3, $4}'",
                timeout=10,
            )
            if snap.ok and snap.out.strip():
                lines = " | ".join(snap.out.strip().splitlines())
                logger.debug(f"    [{elapsed}s] build cache: {lines}")
            else:
                logger.debug(f"    [{elapsed}s] build in progress (cache unavailable)...")

        if not result_holder:
            raise StepError(step, "Build thread did not return a result")
        r = result_holder[0]
        step.result = r.out[:500]
        if not r.ok:
            raise StepError(step, f"exit={r.exit_code}: {r.stderr[:300]}")
        logger.debug(f"    build completed in {elapsed + poll_interval}s")
        step.status = StepStatus.DONE

    def _run_docker_health_wait(self, step: MigrationStep) -> None:
        """Wait until all containers reach 'healthy' or 'running' status.

        Replaces static wait. Polls `docker compose ps` every poll_interval
        until all containers are up or timeout is reached.
        """
        cmd = step.command  # should be: "cd <dir> && docker compose -f ... ps --format json"
        if not cmd:
            raise StepError(step, "No command specified for docker_health_wait")

        timeout = step.timeout or 120
        poll_interval = 8
        elapsed = 0
        last_status = ""

        while elapsed < timeout:
            r = self.probe.run(cmd, timeout=20)
            if r.ok and r.out.strip():
                lines = r.out.strip().splitlines()
                # Parse simple table: Name | Status
                statuses = []
                for line in lines:
                    if line.startswith("NAME") or not line.strip():
                        continue
                    parts = line.split(None, 1)
                    name = parts[0] if parts else "?"
                    status = parts[1].strip() if len(parts) > 1 else "?"
                    statuses.append((name, status))

                status_str = ", ".join(f"{n}:{s}" for n, s in statuses)
                if status_str != last_status:
                    logger.debug(f"    [{elapsed}s] containers: {status_str}")
                    last_status = status_str

                unhealthy = [
                    n for n, s in statuses
                    if not any(kw in s.lower() for kw in ("up", "running", "healthy"))
                ]
                if statuses and not unhealthy:
                    step.status = StepStatus.DONE
                    step.result = f"all containers healthy after {elapsed}s: {status_str}"
                    logger.debug(f"    ✓ all containers healthy ({elapsed}s)")
                    return
            else:
                logger.debug(f"    [{elapsed}s] waiting for containers (no output yet)...")

            time.sleep(poll_interval)
            elapsed += poll_interval

        # timeout — log final state and continue (don't fail hard, http_check will catch it)
        step.status = StepStatus.DONE
        step.result = f"timeout {timeout}s reached, last: {last_status or 'unknown'}"
        logger.warning(f"    docker_health_wait timed out after {timeout}s — proceeding to health check")

    def _run_container_log_tail(self, step: MigrationStep) -> None:
        """Fetch and log the last N lines from each container after start."""
        cmd = step.command
        if not cmd:
            raise StepError(step, "No command specified for container_log_tail")

        r = self.probe.run(cmd, timeout=30)
        if r.ok and r.out.strip():
            for line in r.out.strip().splitlines():
                logger.debug(f"    log: {line}")
            step.result = f"{len(r.out.splitlines())} log lines fetched"
        else:
            step.result = "no log output (containers may still be starting)"
        step.status = StepStatus.DONE

    def _run_http_check(self, step: MigrationStep, retries: int = 5, delay: int = 8) -> None:
        """HTTP check via SSH curl on the remote host (avoids local network/firewall issues)."""
        if not step.url:
            raise StepError(step, "http_check requires url")
        last_err = ""
        for attempt in range(retries):
            if step.expect:
                cmd = f"curl -skf --max-time 10 '{step.url}' | grep -F '{step.expect}'"
            else:
                cmd = f"curl -skf --max-time 10 '{step.url}'"
            r = self.probe.run(cmd, timeout=20)
            if r.ok and (not step.expect or step.expect in r.out):
                step.status = StepStatus.DONE
                step.result = f"OK (expect='{step.expect}' found)" if step.expect else r.out[:200]
                return
            last_err = f"expected '{step.expect}' not found in: {r.out[:80]}" if r.ok else (r.stderr[:100] or f"curl exit={r.exit_code}")
            logger.debug(f"    retry {attempt + 1}/{retries}: {last_err}")
            time.sleep(delay)
        raise StepError(step, f"HTTP check failed after {retries} retries: {last_err}")

    def _run_version_check(self, step: MigrationStep) -> None:
        """Version check via SSH curl on the remote host."""
        if not step.url or not step.expect:
            raise StepError(step, "version_check requires url and expect")
        cmd = f"curl -skf --max-time 10 '{step.url}'"
        r = self.probe.run(cmd, timeout=20)
        if not r.ok:
            raise StepError(step, f"curl failed: {r.stderr[:100]}")
        if step.expect not in r.out:
            raise StepError(step, f"version '{step.expect}' not found in response: {r.out[:100]}")
        step.status = StepStatus.DONE
        step.result = f"version {step.expect} confirmed"

    def _run_wait(self, step: MigrationStep) -> None:
        total = step.seconds
        if total <= 0:
            step.status = StepStatus.DONE
            step.result = "waited 0s"
            return
        tick = min(10, max(5, total // 6))  # log every 5–10s
        elapsed = 0
        while elapsed < total:
            chunk = min(tick, total - elapsed)
            time.sleep(chunk)
            elapsed += chunk
            if elapsed < total:
                logger.debug(f"    waiting... {elapsed}/{total}s")
        step.status = StepStatus.DONE
        step.result = f"waited {total}s"

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

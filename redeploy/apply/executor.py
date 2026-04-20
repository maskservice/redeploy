"""Executor — runs MigrationPlan steps, handles rollback on failure."""
from __future__ import annotations

import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Optional

import yaml
from loguru import logger

from ..detect.remote import RemoteProbe
from ..models import MigrationPlan, MigrationStep, StepAction, StepStatus
from ..plugins import PluginContext, registry as _plugin_registry
from .state import ResumeState, default_state_path


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


class StepError(Exception):
    def __init__(self, step: MigrationStep, msg: str):
        self.step = step
        super().__init__(f"[{step.id}] {msg}")


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
            StepAction.SYSTEMCTL_STOP:      self._run_ssh,
            StepAction.SYSTEMCTL_DISABLE:   self._run_ssh,
            StepAction.SYSTEMCTL_START:     self._run_ssh,
            StepAction.KUBECTL_DELETE:      self._run_ssh,
            StepAction.DOCKER_COMPOSE_UP:   self._run_ssh,
            StepAction.DOCKER_COMPOSE_DOWN: self._run_ssh,
            StepAction.DOCKER_BUILD:        self._run_docker_build,
            StepAction.DOCKER_HEALTH_WAIT:  self._run_docker_health_wait,
            StepAction.CONTAINER_LOG_TAIL:  self._run_container_log_tail,
            StepAction.PODMAN_BUILD:        self._run_podman_build,
            StepAction.SSH_CMD:             self._run_ssh,
            StepAction.SCP:                 self._run_scp,
            StepAction.RSYNC:               self._run_rsync,
            StepAction.HTTP_CHECK:          self._run_http_check,
            StepAction.VERSION_CHECK:       self._run_version_check,
            StepAction.WAIT:                self._run_wait,
            StepAction.PLUGIN:              self._run_plugin,
            StepAction.INLINE_SCRIPT:       self._run_inline_script,
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
        timeout = step.timeout or 300
        r = self.probe.run(cmd, timeout=timeout)
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
                msg = f"[{elapsed}s] build cache: {lines}"
                logger.debug(f"    {msg}")
                if self._emitter:
                    self._emitter.progress(step.id, msg)
            else:
                msg = f"[{elapsed}s] build in progress..."
                logger.debug(f"    {msg}")
                if self._emitter:
                    self._emitter.progress(step.id, msg)

        if not result_holder:
            raise StepError(step, "Build thread did not return a result")
        r = result_holder[0]
        step.result = r.out[:500]
        if not r.ok:
            raise StepError(step, f"exit={r.exit_code}: {r.stderr[:300]}")
        logger.debug(f"    build completed in {elapsed + poll_interval}s")
        step.status = StepStatus.DONE

    def _run_podman_build(self, step: MigrationStep) -> None:
        """Run podman build on remote with periodic progress polling."""
        cmd = step.command
        if not cmd:
            raise StepError(step, "No command specified")

        timeout = step.timeout or 1800  # 30 min default for ARM64 builds
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
                "podman system df 2>/dev/null | grep -E 'Image|Cache' | "
                "awk '{print $1, $3, $4}'",
                timeout=10,
            )
            if snap.ok and snap.out.strip():
                lines = " | ".join(snap.out.strip().splitlines())
                msg = f"[{elapsed}s] podman cache: {lines}"
                logger.debug(f"    {msg}")
                if self._emitter:
                    self._emitter.progress(step.id, msg)
            else:
                msg = f"[{elapsed}s] podman build in progress..."
                logger.debug(f"    {msg}")
                if self._emitter:
                    self._emitter.progress(step.id, msg)

        if not result_holder:
            raise StepError(step, "Podman build thread did not return a result")
        r = result_holder[0]
        step.result = r.out[:500]
        if not r.ok:
            raise StepError(step, f"exit={r.exit_code}: {r.stderr[:300]}")
        logger.debug(f"    podman build completed in {elapsed + poll_interval}s")
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

    def _run_plugin(self, step: MigrationStep) -> None:
        """Dispatch to a registered plugin handler."""
        plugin_type = step.plugin_type
        if not plugin_type:
            raise StepError(step, "plugin action requires plugin_type field")
        handler = _plugin_registry.get(plugin_type)
        if not handler:
            available = ", ".join(_plugin_registry.names()) or "(none loaded)"
            raise StepError(step, f"unknown plugin_type '{plugin_type}'. Available: {available}")
        ctx = PluginContext(
            step=step,
            host=self.plan.host,
            probe=self.probe,
            emitter=self._emitter,
            params=step.plugin_params,
            dry_run=self.dry_run,
        )
        handler(ctx)

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

    def _run_inline_script(self, step: MigrationStep) -> None:
        """Execute multiline bash script via SSH using base64 encoding."""
        import base64
        from pathlib import Path

        script = step.command
        
        # If command_ref is set, extract script from markdown file
        if step.command_ref:
            script = self._resolve_command_ref(step.command_ref, step)
        
        if not script:
            raise StepError(step, "inline_script requires command field or command_ref with script content")

        # Base64 encode the script to safely pass it through SSH
        encoded = base64.b64encode(script.encode()).decode()
        timeout = step.timeout or 300

        # Create temp file, decode script, run it, then clean up
        cmd = (
            f"tmpfile=$(mktemp) && "
            f"echo '{encoded}' | base64 -d > \"$tmpfile\" && "
            f"chmod +x \"$tmpfile\" && "
            f"\"$tmpfile\"; "
            f"rc=$?; "
            f"rm -f \"$tmpfile\"; "
            f"exit $rc"
        )

        r = self.probe.run(cmd, timeout=timeout)
        step.result = r.out[:500] if r.out else "script executed"
        if not r.ok:
            raise StepError(step, f"script failed with exit={r.exit_code}: {r.stderr[:200]}")
        step.status = StepStatus.DONE

    def _resolve_command_ref(self, command_ref: str, step: MigrationStep) -> str:
        """Resolve command_ref to script content from markdown file.
        
        command_ref formats:
        - "./file.md#section-id" - script from section in specific file
        - "#section-id" - script from section in current spec file
        - "#kiosk-browser-configuration-script" - markpact:ref block
        """
        from pathlib import Path
        from ..markpact.parser import extract_script_from_markdown, extract_script_by_ref
        
        # Parse command_ref
        if "#" in command_ref:
            file_part, section_id = command_ref.split("#", 1)
            file_path = file_part if file_part else getattr(self.plan, 'spec_path', None)
        else:
            section_id = command_ref
            file_path = getattr(self.plan, 'spec_path', None)
        
        if not file_path:
            raise StepError(step, f"Cannot resolve command_ref '{command_ref}': no file path available")
        
        file_path = Path(file_path)
        if not file_path.exists():
            raise StepError(step, f"Command ref file not found: {file_path}")
        
        # Extract script from markdown - try both methods:
        # 1. First try markpact:ref codeblock (new format)
        # 2. Then try section heading (old format)
        markdown_content = file_path.read_text(encoding="utf-8")
        
        # Try markpact:ref format first
        script = extract_script_by_ref(markdown_content, section_id, language="bash")
        
        # Fallback to section heading format
        if script is None:
            script = extract_script_from_markdown(markdown_content, section_id, language="bash")
        
        if script is None:
            raise StepError(step, f"Could not find bash script for ref '{section_id}' in {file_path} (tried markpact:ref and section heading)")
        
        return script

    # ── rollback ──────────────────────────────────────────────────────────────

    def _rollback(self) -> None:
        logger.warning("Rolling back completed steps...")
        rolled_back: list[str] = []
        for step in reversed(self._completed):
            if step.rollback_command:
                logger.info(f"  ↩ rollback [{step.id}]: {step.rollback_command}")
                r = self.probe.run(step.rollback_command, timeout=120)
                if not r.ok:
                    logger.warning(f"    rollback failed: {r.stderr[:100]}")
                else:
                    rolled_back.append(step.id)
        # Forget rolled-back steps so a subsequent --resume re-executes them.
        if rolled_back and self._state is not None:
            self._state.completed_step_ids = [
                sid for sid in self._state.completed_step_ids
                if sid not in set(rolled_back)
            ]
            self._state.save()

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

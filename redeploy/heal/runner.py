"""Self-healing runner — orchestrates detect → LLM fix → retry loop."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from .loop_detector import HealAbort, HealLoopDetector
from .log_writer import write_repair_log
from .hint_provider import (
    ask_llm,
    apply_fix_to_spec,
    collect_diagnostics,
    parse_failed_step,
)
from .decider import Action, Decision, decide_after_failure, format_decision_message


class HealRunner:
    """Wraps :class:`Executor` with a self-healing loop.

    Parameters
    ----------
    migration:
        Planned migration object (from ``Planner.run()``).
    spec_path:
        Path to the spec file (patched by the LLM on fix).
    host:
        SSH host string (e.g. ``"pi@192.168.188.109"``) for diagnostics.
    fix_hint:
        Optional user-provided description of a known issue (from ``--fix``).
    max_retries:
        Max self-healing attempts before giving up.
    dry_run:
    console:
        Rich console for progress printing.
    version:
        Current project version (for the repair log).
    executor_kwargs:
        Extra keyword arguments forwarded to :class:`Executor`.
    """

    def __init__(
        self,
        migration,
        spec_path: str | Path,
        host: str,
        fix_hint: str = "",
        max_retries: int = 3,
        dry_run: bool = False,
        console=None,
        version: str = "",
        **executor_kwargs,
    ):
        self.migration = migration
        self.spec_path = Path(spec_path)
        self.host = host
        self.fix_hint = fix_hint
        self.max_retries = max_retries
        self.dry_run = dry_run
        self.version = version
        self.executor_kwargs = executor_kwargs

        # Extract CLI-only keys not accepted by Executor
        self._state_file = executor_kwargs.pop("state_file", None)
        self._no_state = executor_kwargs.pop("no_state", False)
        self.repairs: list[dict] = []
        self._loop_detector = HealLoopDetector(max_identical_hints=3)

        if console is None:
            from rich.console import Console
            console = Console()
        self.console = console

    def _make_executor(self, resume: bool = False):
        from ..apply import Executor

        executor = Executor(
            self.migration,
            dry_run=self.dry_run,
            progress_yaml=self.executor_kwargs.get("progress_yaml", False),
            resume=resume,
            from_step=self.executor_kwargs.get("from_step", None),
            state_path=Path(self._state_file) if self._state_file else None,
            spec_path=str(self.spec_path),
        )
        if self._no_state:
            executor._state = None
            executor._state_path = None
        return executor

    def _reload_migration(self) -> None:
        """Reload migration plan from a patched spec file."""
        from ..spec_loader import load_migration_spec
        from ..plan import Planner

        spec = load_migration_spec(str(self.spec_path))
        planner = Planner.from_spec(spec)
        self.migration = planner.run()

    def _heal_step(self, executor, attempt: int) -> tuple[Decision, str, str]:
        """Single heal iteration: diagnose → LLM → decide.

        Returns *(decision, failed_step, loop_hint)*.
        """
        failed_step, step_output = parse_failed_step(executor.summary(), executor)

        if not failed_step:
            return (
                Decision(Action.ABORT, "Cannot identify failed step"),
                "",
                "",
            )

        self.console.print(
            f"\n[bold yellow]heal {attempt}/{self.max_retries}:[/bold yellow] "
            f"step [cyan]`{failed_step}`[/cyan] failed"
        )

        # Diagnostics
        self.console.print("  [dim]collecting SSH diagnostics...[/dim]")
        diag = collect_diagnostics(self.host, failed_step)
        if self.fix_hint:
            diag = f"User-reported issue: {self.fix_hint}\n\n{diag}"

        diag_hint = next(
            (
                l.strip()
                for l in diag.splitlines()
                if any(k in l.lower() for k in ["error", "fail", "no such", "cannot", "warn"])
            ),
            diag.splitlines()[0] if diag else "",
        )

        # Ask LLM
        model = os.getenv("LLM_MODEL", "openrouter/qwen/qwen3-coder-next")
        self.console.print(
            f"  [dim]asking LLM ({model}) to fix step `{failed_step}`...[/dim]"
        )
        spec_text = self.spec_path.read_text()
        log_dir = self.spec_path.parent / ".redeploy" / "logs"
        llm_response = ask_llm(
            failed_step, step_output, diag, spec_text,
            fix_hint=self.fix_hint, log_dir=log_dir,
        )

        fixed = False
        summary = "manual"
        llm_error = bool(llm_response.startswith("# LLM error"))
        if llm_response and not llm_error:
            self.console.print(
                "  [dim]LLM proposal:[/dim]\n"
                + "\n".join(f"    {l}" for l in llm_response.splitlines()[:12])
            )
            before_patch = self.spec_path.read_text()
            fixed = apply_fix_to_spec(self.spec_path, failed_step, llm_response)
            if fixed:
                desc_m = re.search(r'description:\s*"([^"]+)"', llm_response)
                summary = desc_m.group(1) if desc_m else llm_response[:60].replace("\n", " ")
                self.console.print(f"  [green]patched spec:[/green] `{failed_step}`")
                try:
                    self._reload_migration()
                except Exception as exc:
                    # LLM patch changed the file but produced an invalid spec.
                    # Restore previous content and continue heal flow safely.
                    self.spec_path.write_text(before_patch)
                    fixed = False
                    summary = f"invalid patch: {exc.__class__.__name__}"
                    self.console.print(
                        "  [yellow]LLM fix invalid for current runtime; "
                        "reverted spec patch[/yellow]"
                    )
            else:
                self.console.print("  [yellow]LLM fix not applicable[/yellow]")
        else:
            self.console.print(
                f"  [yellow]{llm_response or 'LLM unavailable'}[/yellow]"
            )

        self.repairs.append({
            "step": failed_step,
            "attempt": attempt,
            "summary": summary,
            "diag_hint": diag_hint,
            "fixed": fixed,
        })
        write_repair_log(self.spec_path, self.version, self.repairs)

        loop_hint = f"{summary} | {diag_hint}".strip()
        loop_detected = self._loop_detector.observe(failed_step, loop_hint)

        decision = decide_after_failure(
            attempt=attempt,
            max_retries=self.max_retries,
            failed_step=failed_step,
            loop_detected=loop_detected,
            llm_error=llm_error,
            spec_patched=fixed,
        )
        self.console.print(format_decision_message(decision, failed_step))

        return decision, failed_step, loop_hint

    def run(self) -> bool:
        """Execute the migration with self-healing.

        Returns *True* on final success, *False* otherwise.
        """
        if self.fix_hint:
            self.console.print(
                f"\n[cyan]fix hint:[/cyan] [italic]{self.fix_hint}[/italic]"
            )

        # First attempt
        executor = self._make_executor(resume=False)
        ok = executor.run()
        self.console.print(f"\n{executor.summary()}")

        if ok:
            write_repair_log(self.spec_path, self.version, self.repairs)
            return True

        # Self-healing loop
        for attempt in range(1, self.max_retries + 1):
            decision, failed_step, _ = self._heal_step(executor, attempt)

            if decision.action is Action.ABORT:
                break
            if decision.action is Action.SKIP:
                if not failed_step or executor.state is None:
                    self.console.print(
                        "  [yellow]cannot skip without checkpointed state; aborting heal loop[/yellow]"
                    )
                    break

                executor.state.mark_done(failed_step)
                self.console.print(
                    f"  [yellow]marking step as skipped in checkpoint:[/yellow] `{failed_step}`"
                )

                executor = self._make_executor(resume=True)
                ok = executor.run()
                self.console.print(f"\n{executor.summary()}")
                if ok:
                    self._loop_detector.reset_all()
                    write_repair_log(self.spec_path, self.version, self.repairs)
                    return True
                continue

            # Retry
            executor = self._make_executor(resume=True)
            ok = executor.run()
            self.console.print(f"\n{executor.summary()}")
            if ok:
                self._loop_detector.reset_all()
                write_repair_log(self.spec_path, self.version, self.repairs)
                return True

        write_repair_log(self.spec_path, self.version, self.repairs)
        return False

"""
redeploy.heal -- Self-healing runner with LiteLLM auto-repair.

Integrates into `redeploy run` via --heal / --fix flags.

Usage (via CLI):
    redeploy run spec.md                     # heal enabled by default
    redeploy run spec.md --heal off          # disable self-healing
    redeploy run spec.md --fix "brak ikon SVG w menu"
    redeploy run spec.md --fix "brak ikon" --max-heal-retries 5

Programmatic:
    from redeploy.heal import HealRunner
    ok = HealRunner(spec_path, host, fix_hint="brak SVG").run()
"""
from __future__ import annotations

import os
import re
import textwrap
import datetime
from collections import defaultdict
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Diagnostics catalogue -- targeted SSH commands per failed step ID
# Add more entries to improve LLM context quality.
# ---------------------------------------------------------------------------
DIAG_COMMANDS: dict[str, list[str]] = {
    "restart-chromium": [
        "pgrep -fa chromium | head -5 || echo NO_CHROMIUM",
        "ls /run/user/1000/wayland-* 2>/dev/null || echo NO_WAYLAND",
        "systemctl --user status kiosk-chromium.service --no-pager -n 10 2>&1 || true",
        "cat ~/c2004/logs/kiosk.log 2>/dev/null | tail -20 || echo NO_LOG",
    ],
    "assert-screen-kiosk-url": [
        "pgrep -fa chromium | head -3 || echo NO_CHROMIUM",
        "cat ~/c2004/scripts/kiosk-launch.sh 2>/dev/null || echo NO_SCRIPT",
        "cat ~/c2004/logs/kiosk.log 2>/dev/null | tail -30 || echo NO_LOG",
    ],
    "assert-screen-backend-healthy": [
        "systemctl --user status c2004-backend.service --no-pager -n 20",
        "journalctl --user -u c2004-backend.service --no-pager -n 20 2>/dev/null",
        "curl -sv http://localhost:8000/api/v3/health 2>&1 | tail -10",
    ],
    "e2e-svg-icons": [
        "podman exec c2004-frontend ls /usr/share/nginx/html/icons/ 2>/dev/null | head -10",
        "curl -sI http://localhost:8100/icons/sprite.svg | head -8",
        "podman exec c2004-frontend cat /etc/nginx/conf.d/default.conf 2>/dev/null | head -30",
    ],
    "e2e-api-endpoints": [
        "systemctl --user status c2004-backend.service --no-pager -n 5",
        "curl -sv http://localhost:8000/api/v3/health 2>&1 | tail -15",
        "journalctl --user -u c2004-backend.service --no-pager -n 15 2>/dev/null",
    ],
    "e2e-kiosk-page-load": [
        "curl -sf http://localhost:8100/ 2>/dev/null | head -20",
        "podman exec c2004-frontend ls /usr/share/nginx/html/ | head -10",
    ],
    "_default": [
        "systemctl --user list-units --type=service 2>/dev/null | grep -v '@' | tail -15",
        "podman ps -a --format 'table {{.Names}}\\t{{.Status}}' 2>/dev/null",
        "ss -tlnp 2>/dev/null | grep -E '8000|8100|8202' || echo PORTS_FREE",
        "journalctl --user --no-pager -n 10 2>/dev/null",
    ],
}

# Known constraints injected into every LLM prompt
KNOWN_CONSTRAINTS = """
Known constraints for this deployment target (Raspberry Pi 5, Podman Quadlet, labwc Wayland):
- pkill/killall chromium via SSH = exit 255 (kills Wayland session and drops SSH)
- Chromium requires: WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000
- Use systemd-run --user --collect to start GUI apps without blocking SSH
- I2C device 0x45 on bus 11 is owned by kernel waveshare driver -- use || true
- Redirecting /dev/null in heredoc via SSH causes exit 255
- SQLite DBs at: /data/main/identification.db, /data/menu/menu.db, /data/scenario.db
- alembic binary may not exist in container -- use python3 -c with sqlite3 module
- Quadlet unit files go to ~/.config/containers/systemd/
- Services: c2004-backend, c2004-frontend, c2004-firmware, c2004-reverse-proxy
"""


def _ssh(host: str, command: str) -> tuple[int, str]:
    import subprocess
    result = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", host, command],
        capture_output=True, text=True, timeout=30,
    )
    return result.returncode, ((result.stdout or "") + (result.stderr or "")).strip()


def collect_diagnostics(host: str, failed_step: str) -> str:
    """Run targeted SSH diagnostics for a failed step, return combined output."""
    cmds = DIAG_COMMANDS.get(failed_step, DIAG_COMMANDS["_default"])
    parts = []
    for cmd in cmds:
        rc, out = _ssh(host, cmd)
        parts.append(f"$ {cmd}\n{out}")
    return "\n\n".join(parts)


def ask_llm(
    failed_step: str,
    step_output: str,
    diag: str,
    spec_text: str,
    fix_hint: str = "",
) -> str:
    """Ask LiteLLM to propose a fixed YAML block for the failed step."""
    try:
        import litellm
    except ImportError:
        return ""

    model = os.getenv("LLM_MODEL", "openrouter/qwen/qwen3-coder-next")
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    api_base = "https://openrouter.ai/api/v1" if "openrouter" in model else None

    hint_section = f"\n## User-reported issue:\n{fix_hint}\n" if fix_hint else ""

    prompt = textwrap.dedent(f"""
        You are an expert in Raspberry Pi 5 deployments with Podman Quadlet, labwc Wayland compositor and Chromium kiosk.

        ## Failed step: `{failed_step}`
        {hint_section}
        ### Step output (error):
        ```
        {step_output[:2000]}
        ```

        ### SSH diagnostics collected after failure:
        ```
        {diag[:3000]}
        ```

        ### Current spec file (markpact YAML steps):
        ```yaml
        {spec_text[:5000]}
        ```

        {KNOWN_CONSTRAINTS}

        ## Task:
        Fix ONLY the step `{failed_step}`. Return ONLY the corrected YAML block:

        ```yaml
        - id: {failed_step}
          action: ssh_cmd
          description: "..."
          command: |
            <corrected command>
        ```

        Nothing else. No explanation outside the code block.
    """).strip()

    try:
        kwargs: dict = dict(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1500,
        )
        if api_key:
            kwargs["api_key"] = api_key
        if api_base:
            kwargs["api_base"] = api_base

        resp = litellm.completion(**kwargs)
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"# LLM error: {e}"


def apply_fix_to_spec(spec_path: Path, failed_step: str, llm_response: str) -> bool:
    """Extract YAML block from LLM response and patch it into the spec file."""
    m = re.search(r"```ya?ml\s*(.*?)```", llm_response, re.DOTALL)
    if m:
        new_block = m.group(1).strip()
    else:
        m = re.search(
            rf"(- id: {re.escape(failed_step)}.+?)(?=\n  - id:|\Z)",
            llm_response, re.DOTALL
        )
        if not m:
            return False
        new_block = m.group(1).strip()

    text = spec_path.read_text()
    pattern = rf"(  - id: {re.escape(failed_step)}\n(?:(?!  - id:).)*)"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return False

    indented = "\n".join("  " + line if line else "" for line in new_block.splitlines())
    spec_path.write_text(text[: match.start()] + indented + "\n" + text[match.end():])
    return True


def write_repair_log(spec_path: Path, version: str, repairs: list[dict]) -> None:
    """Write/update REPAIR_LOG.md adjacent to spec file."""
    log_path = spec_path.parent / "REPAIR_LOG.md"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"## {version} -- {now}\n"]
    if repairs:
        lines.append("### LLM repairs\n")
        for r in repairs:
            lines.append(f"- **`{r['step']}`**: {r.get('summary', 'fixed')}\n")
            if r.get("diag_hint"):
                lines.append(f"  - hint: `{r['diag_hint'][:120]}`\n")
    else:
        lines.append("Deployment completed without repairs.\n")
    lines.append("\n")
    entry = "".join(lines)

    if log_path.exists():
        existing = log_path.read_text()
        if "# " in existing:
            idx = existing.index("\n", existing.index("# ")) + 1
            content = existing[:idx] + "\n" + entry + existing[idx:]
        else:
            content = entry + existing
    else:
        content = "# Repair Log\n\nAuto-repairs by `redeploy run --heal`.\n\n" + entry

    log_path.write_text(content)


def parse_failed_step(executor_summary: str, executor=None) -> tuple[str | None, str]:
    """Extract (step_id, step_output) from executor state or summary string."""
    if executor is not None:
        state = getattr(executor, "state", None)
        if state and state.failed_step_id:
            # Try to get step output from executor results
            results = getattr(executor, "_results", {})
            step_out = results.get(state.failed_step_id, {})
            if isinstance(step_out, dict):
                out = step_out.get("output") or step_out.get("error") or ""
            else:
                out = str(step_out)
            return state.failed_step_id, out

    m = re.search(r"Step failed: \[([^\]]+)\].*?exit=\d+:?\s*(.*?)(?=\n\d{2}:\d{2}|\Z)",
                  executor_summary, re.DOTALL)
    if m:
        return m.group(1), m.group(2).strip()
    return None, ""


class HealLoopDetector:
    """Detect repeated non-converging heal hints for a given step."""

    def __init__(self, max_identical_hints: int = 3):
        self.max_identical_hints = max_identical_hints
        self._history: dict[str, list[str]] = defaultdict(list)

    def observe(self, step_id: str, hint: str) -> bool:
        """Return True when the latest hints indicate a heal loop.

        A loop is defined as ``max_identical_hints`` identical non-empty hints
        in a row for the same failed step.
        """
        normalized = (hint or "").strip()
        if not normalized:
            return False

        history = self._history[step_id]
        history.append(normalized)

        if len(history) < self.max_identical_hints:
            return False

        recent = history[-self.max_identical_hints :]
        return all(item == recent[0] for item in recent)


class HealRunner:
    """
    Wraps Executor with self-healing loop.

    Parameters
    ----------
    migration : Migration
        Planned migration object (from Planner.run()).
    spec_path : str | Path
        Path to the spec file (for patching on LLM fix).
    host : str
        SSH host string (e.g. "pi@192.168.188.109") for diagnostics.
    fix_hint : str
        Optional user-provided description of known issue (from --fix).
    max_retries : int
        Max self-healing attempts before giving up.
    dry_run : bool
    console : rich.Console
    version : str
        Current project version (for repair log).
    executor_kwargs : dict
        Extra kwargs forwarded to Executor.
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

        from rich.console import Console
        self.console = console or Console()

    def _make_executor(self, resume: bool = False):
        from .apply import Executor
        from pathlib import Path as _Path

        state_path = _Path(self._state_file) if self._state_file else None
        executor = Executor(
            self.migration,
            dry_run=self.dry_run,
            progress_yaml=self.executor_kwargs.get("progress_yaml", False),
            resume=resume,
            from_step=self.executor_kwargs.get("from_step", None),
            state_path=state_path if not self._no_state else None,
            spec_path=str(self.spec_path),
        )
        if self._no_state:
            executor._state = None
            executor._state_path = None
        return executor

    def _reload_migration(self) -> None:
        """Reload migration plan from patched spec file."""
        from .spec_loader import load_migration_spec
        from .plan import Planner

        spec = load_migration_spec(str(self.spec_path))
        planner = Planner.from_spec(spec)
        self.migration = planner.run()

    def run(self) -> bool:
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
            failed_step, step_output = parse_failed_step(executor.summary(), executor)

            if not failed_step:
                self.console.print("[yellow]heal: cannot identify failed step[/yellow]")
                break

            self.console.print(
                f"\n[bold yellow]heal {attempt}/{self.max_retries}:[/bold yellow] "
                f"step [cyan]`{failed_step}`[/cyan] failed"
            )

            # Diagnostics
            self.console.print(f"  [dim]collecting SSH diagnostics...[/dim]")
            diag = collect_diagnostics(self.host, failed_step)

            # Prepend fix_hint to diag context
            if self.fix_hint:
                diag = f"User-reported issue: {self.fix_hint}\n\n{diag}"

            diag_hint = next(
                (l.strip() for l in diag.splitlines()
                 if any(k in l.lower() for k in ["error", "fail", "no such", "cannot", "warn"])),
                diag.splitlines()[0] if diag else "",
            )

            # Ask LLM
            self.console.print(f"  [dim]asking LLM for fix...[/dim]")
            spec_text = self.spec_path.read_text()
            llm_response = ask_llm(failed_step, step_output, diag, spec_text, self.fix_hint)

            fixed = False
            summary = "manual"
            if llm_response and not llm_response.startswith("# LLM error"):
                self.console.print(
                    f"  [dim]LLM proposal:[/dim]\n"
                    + "\n".join(f"    {l}" for l in llm_response.splitlines()[:12])
                )
                fixed = apply_fix_to_spec(self.spec_path, failed_step, llm_response)
                if fixed:
                    desc_m = re.search(r'description:\s*"([^"]+)"', llm_response)
                    summary = desc_m.group(1) if desc_m else llm_response[:60].replace("\n", " ")
                    self.console.print(f"  [green]patched spec:[/green] `{failed_step}`")
                    self._reload_migration()
                else:
                    self.console.print(f"  [yellow]LLM fix not applicable[/yellow]")
            else:
                self.console.print(f"  [yellow]{llm_response or 'LLM unavailable'}[/yellow]")

            self.repairs.append({
                "step": failed_step,
                "attempt": attempt,
                "summary": summary,
                "diag_hint": diag_hint,
                "fixed": fixed,
            })
            write_repair_log(self.spec_path, self.version, self.repairs)

            loop_hint = f"{summary} | {diag_hint}".strip()
            if self._loop_detector.observe(failed_step, loop_hint):
                self.console.print(
                    "[yellow]heal: detected repeating non-converging hint pattern; "
                    "stopping auto-retry to avoid loop[/yellow]"
                )
                break

            # Retry
            executor = self._make_executor(resume=True)
            ok = executor.run()
            self.console.print(f"\n{executor.summary()}")
            if ok:
                write_repair_log(self.spec_path, self.version, self.repairs)
                return True

        write_repair_log(self.spec_path, self.version, self.repairs)
        return False

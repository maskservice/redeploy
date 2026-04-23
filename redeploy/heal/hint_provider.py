"""LLM hint generation and spec patching utilities."""
from __future__ import annotations

import datetime
import os
import re
import sys
import textwrap
from pathlib import Path
from typing import Optional

import yaml

from loguru import logger

# ---------------------------------------------------------------------------
# Diagnostics catalogue -- targeted SSH commands per failed step ID
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
    log_dir: Path | None = None,
) -> str:
    """Ask LiteLLM to propose a fixed YAML block for the failed step.

    Saves full prompt + response to *log_dir* (defaults to ``.redeploy/logs/``).
    Suppresses litellm stdout/stderr spam (e.g. repeated Provider List).
    """
    try:
        import litellm
    except ImportError:
        return ""

    model = os.getenv("LLM_MODEL", "openrouter/qwen/qwen3-coder-next")
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    api_base = "https://openrouter.ai/api/v1" if "openrouter" in model else None

    hint_section = f"\n## User-reported issue:\n{fix_hint}\n" if fix_hint else ""
    current_step_block = _extract_step_block(spec_text, failed_step)
    current_step_section = (
        f"\n### Current step block to fix (keep same id/action shape):\n```yaml\n{current_step_block}\n```\n"
        if current_step_block
        else ""
    )

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

                {current_step_section}

        {KNOWN_CONSTRAINTS}

        ## Task:
                Fix ONLY the step `{failed_step}`.
                Preserve the same `id` and keep the same `action` unless absolutely required.
                If the current step uses `command_ref`, keep `command_ref` style (do not rewrite to ad-hoc `command` unless strictly necessary).
                Return ONLY the corrected YAML step block:

        ```yaml
                - id: {failed_step}
                    ...
        ```

        Nothing else. No explanation outside the code block.
    """).strip()

    # Ensure log directory exists
    if log_dir is None:
        log_dir = Path.cwd() / ".redeploy" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"llm_{timestamp}_{failed_step}.md"

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

        # Suppress litellm stdout/stderr spam (Provider List, etc.)
        import contextlib
        import io
        _stdout, _stderr = sys.stdout, sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        try:
            resp = litellm.completion(**kwargs)
            content = resp.choices[0].message.content.strip()
        finally:
            _captured_out = sys.stdout.getvalue()
            _captured_err = sys.stderr.getvalue()
            sys.stdout, sys.stderr = _stdout, _stderr
            # Log any captured litellm noise for debugging
            if _captured_err.strip() and "Provider List" not in _captured_err:
                logger.debug("litellm stderr: {}", _captured_err[:500])

        # Write request/response log
        _write_llm_log(log_file, model, failed_step, prompt, content)
        return content
    except Exception as e:
        error_msg = f"# LLM error: {e}"
        _write_llm_log(log_file, model, failed_step, prompt, error_msg, error=str(e))
        return error_msg


def _write_llm_log(
    path: Path,
    model: str,
    failed_step: str,
    prompt: str,
    response: str,
    error: str = "",
) -> None:
    """Persist a single LLM call to a markdown file."""
    from loguru import logger as _logger
    lines = [
        f"# LLM call — {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **model**: `{model}`",
        f"- **step**: `{failed_step}`",
    ]
    if error:
        lines.append(f"- **error**: `{error}`")
    lines.extend([
        "",
        "## Prompt",
        "",
        "```",
        prompt,
        "```",
        "",
        "## Response",
        "",
        "```yaml",
        response,
        "```",
        "",
    ])
    try:
        path.write_text("\n".join(lines), encoding="utf-8")
        _logger.debug("LLM log written → {}", path)
    except Exception as exc:
        _logger.warning("Failed to write LLM log {}: {}", path, exc)


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

    old_block = match.group(1)
    old_step = _parse_step_block(old_block)
    new_step = _parse_step_block(new_block)

    if old_step and new_step:
        if str(new_step.get("id", "")) != failed_step:
            return False

        allow_action_change = os.getenv("REDEPLOY_HEAL_ALLOW_ACTION_CHANGE", "0") == "1"
        if not allow_action_change and old_step.get("action") and new_step.get("action") != old_step.get("action"):
            new_step["action"] = old_step["action"]

        allow_ref_drop = os.getenv("REDEPLOY_HEAL_ALLOW_COMMAND_REF_DROP", "0") == "1"
        if old_step.get("command_ref") and not new_step.get("command_ref") and not allow_ref_drop:
            new_step["command_ref"] = old_step.get("command_ref")
            if "command" in new_step:
                del new_step["command"]

        new_block = yaml.safe_dump([new_step], sort_keys=False, allow_unicode=True).strip()

    indented = "\n".join("  " + line if line else "" for line in new_block.splitlines())
    spec_path.write_text(text[: match.start()] + indented + "\n" + text[match.end():])
    return True


def _extract_step_block(spec_text: str, step_id: str) -> str:
    pattern = rf"(  - id: {re.escape(step_id)}\n(?:(?!  - id:).)*)"
    m = re.search(pattern, spec_text, re.DOTALL)
    return m.group(1).rstrip() if m else ""


def _parse_step_block(block: str) -> dict | None:
    try:
        data = yaml.safe_load(block)
    except Exception:
        return None
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    if isinstance(data, dict):
        return data
    return None


def parse_failed_step(executor_summary: str, executor=None) -> tuple[Optional[str], str]:
    """Extract (step_id, step_output) from executor state or summary string."""
    if executor is not None:
        state = getattr(executor, "state", None)
        if state and state.failed_step_id:
            results = getattr(executor, "_results", {})
            step_out = results.get(state.failed_step_id, {})
            if isinstance(step_out, dict):
                out = step_out.get("output") or step_out.get("error") or ""
            else:
                out = str(step_out)
            return state.failed_step_id, out

    m = re.search(
        r"Step failed: \[([^\]]+)\].*?exit=\d+:?\s*(.*?)(?=\n\d{{2}}:\d{{2}}|\Z)",
        executor_summary, re.DOTALL
    )
    if m:
        return m.group(1), m.group(2).strip()
    return None, ""

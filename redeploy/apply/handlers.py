"""Step action handlers for migration execution."""
from __future__ import annotations

import base64
import subprocess
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from ..models import MigrationStep, StepAction, StepStatus
from .exceptions import StepError

if TYPE_CHECKING:
    from ..detect.remote import RemoteProbe
    from ..models import MigrationPlan
    from .progress import ProgressEmitter


def run_ssh(step: MigrationStep, probe: RemoteProbe) -> None:
    """Execute SSH command on remote host."""
    cmd = step.command
    if not cmd:
        raise StepError(step, "No command specified")
    timeout = step.timeout or 300
    r = probe.run(cmd, timeout=timeout)
    step.result = r.out[:500]
    if not r.ok:
        raise StepError(step, f"exit={r.exit_code}: {r.stderr[:200]}")
    step.status = StepStatus.DONE


def run_scp(step: MigrationStep, probe: RemoteProbe, plan: MigrationPlan) -> None:
    """Copy file via SCP."""
    if not step.src or not step.dst:
        raise StepError(step, "scp requires src and dst")
    if probe.is_local and Path(step.src).resolve() == Path(step.dst).resolve():
        step.status = StepStatus.DONE
        step.result = "skipped (same file)"
        return
    if probe.is_local:
        cmd = ["cp", step.src, step.dst]
    else:
        cmd = ["scp", "-o", "StrictHostKeyChecking=no",
               step.src, f"{plan.host}:{step.dst}"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise StepError(step, f"scp failed: {result.stderr[:200]}")
    step.status = StepStatus.DONE
    step.result = "ok"


def run_rsync(step: MigrationStep, probe: RemoteProbe, plan: MigrationPlan) -> None:
    """Sync files via rsync."""
    if not step.src or not step.dst:
        raise StepError(step, "rsync requires src and dst")
    if probe.is_local:
        dst = step.dst
    else:
        dst = f"{plan.host}:{step.dst}"
    cmd = ["rsync", "-az", "--delete"]
    for exc in step.excludes:
        cmd += ["--exclude", exc]
    cmd += [step.src, dst]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise StepError(step, f"rsync failed: {result.stderr[:200]}")
    step.status = StepStatus.DONE
    step.result = "ok"


def run_docker_build(
    step: MigrationStep,
    probe: RemoteProbe,
    emitter: ProgressEmitter | None,
) -> None:
    """Run docker compose build on remote with periodic progress polling."""
    from .utils import run_container_build
    run_container_build(step, probe, emitter, engine="docker")


def run_podman_build(
    step: MigrationStep,
    probe: RemoteProbe,
    emitter: ProgressEmitter | None,
) -> None:
    """Run podman build on remote with periodic progress polling."""
    from .utils import run_container_build
    run_container_build(step, probe, emitter, engine="podman")


def run_docker_health_wait(
    step: MigrationStep,
    probe: RemoteProbe,
) -> None:
    """Wait until all containers reach 'healthy' or 'running' status."""
    cmd = step.command  # should be: "cd <dir> && docker compose -f ... ps --format json"
    if not cmd:
        raise StepError(step, "No command specified for docker_health_wait")

    timeout = step.timeout or 120
    poll_interval = 8
    elapsed = 0
    last_status = ""

    while elapsed < timeout:
        r = probe.run(cmd, timeout=20)
        if r.ok and r.out.strip():
            statuses = _parse_container_statuses(r.out)
            status_str = ", ".join(f"{n}:{s}" for n, s in statuses)

            if status_str != last_status:
                logger.debug(f"    [{elapsed}s] containers: {status_str}")
                last_status = status_str

            if _all_containers_healthy(statuses):
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


def _parse_container_statuses(output: str) -> list[tuple[str, str]]:
    """Parse docker compose ps output into (name, status) tuples."""
    lines = output.strip().splitlines()
    statuses = []
    for line in lines:
        if line.startswith("NAME") or not line.strip():
            continue
        parts = line.split(None, 1)
        name = parts[0] if parts else "?"
        status = parts[1].strip() if len(parts) > 1 else "?"
        statuses.append((name, status))
    return statuses


def _all_containers_healthy(statuses: list[tuple[str, str]]) -> bool:
    """Check if all containers are in a healthy/running state."""
    if not statuses:
        return False
    unhealthy = [
        n for n, s in statuses
        if not any(kw in s.lower() for kw in ("up", "running", "healthy"))
    ]
    return not unhealthy


def run_container_log_tail(step: MigrationStep, probe: RemoteProbe) -> None:
    """Fetch and log the last N lines from each container after start."""
    cmd = step.command
    if not cmd:
        raise StepError(step, "No command specified for container_log_tail")

    r = probe.run(cmd, timeout=30)
    if r.ok and r.out.strip():
        for line in r.out.strip().splitlines():
            logger.debug(f"    log: {line}")
        step.result = f"{len(r.out.splitlines())} log lines fetched"
    else:
        step.result = "no log output (containers may still be starting)"
    step.status = StepStatus.DONE


def run_http_check(
    step: MigrationStep,
    probe: RemoteProbe,
    retries: int = 5,
    delay: int = 8,
) -> None:
    """HTTP check via SSH curl on the remote host (avoids local network/firewall issues)."""
    if not step.url:
        raise StepError(step, "http_check requires url")
    last_err = ""
    for attempt in range(retries):
        if step.expect:
            cmd = f"curl -skf --max-time 10 '{step.url}' | grep -F '{step.expect}'"
        else:
            cmd = f"curl -skf --max-time 10 '{step.url}'"
        r = probe.run(cmd, timeout=20)
        if r.ok and (not step.expect or step.expect in r.out):
            step.status = StepStatus.DONE
            step.result = f"OK (expect='{step.expect}' found)" if step.expect else r.out[:200]
            return
        last_err = f"expected '{step.expect}' not found in: {r.out[:80]}" if r.ok else (r.stderr[:100] or f"curl exit={r.exit_code}")
        logger.debug(f"    retry {attempt + 1}/{retries}: {last_err}")
        time.sleep(delay)
    raise StepError(step, f"HTTP check failed after {retries} retries: {last_err}")


def run_version_check(step: MigrationStep, probe: RemoteProbe) -> None:
    """Version check via SSH curl on the remote host."""
    if not step.url or not step.expect:
        raise StepError(step, "version_check requires url and expect")
    cmd = f"curl -skf --max-time 10 '{step.url}'"
    r = probe.run(cmd, timeout=20)
    if not r.ok:
        raise StepError(step, f"curl failed: {r.stderr[:100]}")
    if step.expect not in r.out:
        raise StepError(step, f"version '{step.expect}' not found in response: {r.out[:100]}")
    step.status = StepStatus.DONE
    step.result = f"version {step.expect} confirmed"


def run_plugin(
    step: MigrationStep,
    probe: RemoteProbe,
    plan: MigrationPlan,
    emitter: ProgressEmitter | None,
    dry_run: bool,
) -> None:
    """Dispatch to a registered plugin handler."""
    from ..plugins import PluginContext, registry as _plugin_registry

    plugin_type = step.plugin_type
    if not plugin_type:
        raise StepError(step, "plugin action requires plugin_type field")
    handler = _plugin_registry.get(plugin_type)
    if not handler:
        available = ", ".join(_plugin_registry.names()) or "(none loaded)"
        raise StepError(step, f"unknown plugin_type '{plugin_type}'. Available: {available}")
    ctx = PluginContext(
        step=step,
        host=plan.host,
        probe=probe,
        emitter=emitter,
        params=step.plugin_params,
        dry_run=dry_run,
    )
    handler(ctx)


def run_wait(step: MigrationStep) -> None:
    """Wait for specified number of seconds."""
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


def run_inline_script(
    step: MigrationStep,
    probe: RemoteProbe,
    plan: MigrationPlan,
) -> None:
    """Execute multiline bash script via SSH using base64 encoding."""
    script = step.command

    # If command_ref is set, extract script from markdown file
    if step.command_ref:
        script = _resolve_command_ref(step.command_ref, step, plan)

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

    r = probe.run(cmd, timeout=timeout)
    step.result = r.out[:500] if r.out else "script executed"
    if not r.ok:
        raise StepError(step, f"script failed with exit={r.exit_code}: {r.stderr[:200]}")
    step.status = StepStatus.DONE


def _resolve_command_ref(command_ref: str, step: MigrationStep, plan: MigrationPlan) -> str:
    """Resolve command_ref to script content from markdown file.

    command_ref formats:
    - "./file.md#section-id" - script from section in specific file
    - "#section-id" - script from section in current spec file
    - "#kiosk-browser-configuration-script" - markpact:ref block
    """
    from ..markpact.parser import extract_script_from_markdown, extract_script_by_ref

    # Parse command_ref
    if "#" in command_ref:
        file_part, section_id = command_ref.split("#", 1)
        file_path = file_part if file_part else getattr(plan, 'spec_path', None)
    else:
        section_id = command_ref
        file_path = getattr(plan, 'spec_path', None)

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


# ── hardware-specific handlers ────────────────────────────────────────────────

def run_ensure_config_line(step: MigrationStep, probe: "RemoteProbe") -> None:
    """Idempotent add/replace a line in a remote config.txt."""
    from ..hardware.config_txt import ensure_line

    if not step.config_file or not step.config_line:
        raise StepError(step, "ensure_config_line requires config_file and config_line")

    config_path = step.config_file
    r = probe.run(f"sudo cat {config_path}", timeout=10)
    if not r.ok:
        raise StepError(step, f"Cannot read {config_path}: {r.stderr[:200]}")

    edit = ensure_line(
        r.out,
        step.config_line,
        section=step.config_section or "all",
        replaces_pattern=step.config_replaces_pattern,
    )

    if not edit.changed:
        step.status = StepStatus.DONE
        step.result = f"no-op: {edit.diff_summary}"
        return

    # Write atomically: base64-encode to avoid shell quoting issues
    encoded = base64.b64encode(edit.new_content.encode()).decode()
    tmp = f"/tmp/redeploy-cfg-{step.id}.txt"
    write_r = probe.run(
        f"echo '{encoded}' | base64 -d | sudo tee {tmp} > /dev/null && sudo mv {tmp} {config_path}",
        timeout=15,
    )
    if not write_r.ok:
        raise StepError(step, f"Cannot write {config_path}: {write_r.stderr[:200]}")

    step.status = StepStatus.DONE
    step.result = edit.diff_summary


def run_raspi_config(step: MigrationStep, probe: "RemoteProbe") -> None:
    """Run raspi-config nonint to enable/disable an interface."""
    from ..hardware.raspi_config import build_raspi_config_command

    if not step.raspi_interface or not step.raspi_state:
        raise StepError(step, "raspi_config requires raspi_interface and raspi_state")

    try:
        cmd = build_raspi_config_command(step.raspi_interface, step.raspi_state)
    except ValueError as exc:
        raise StepError(step, str(exc))

    r = probe.run(cmd, timeout=30)
    if not r.ok:
        raise StepError(step, f"raspi-config failed: {r.stderr[:200]}")

    step.status = StepStatus.DONE
    step.result = f"applied: {cmd}"

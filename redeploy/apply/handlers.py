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


# ── kiosk handlers ────────────────────────────────────────────────────────────

def run_ensure_kanshi_profile(step: MigrationStep, probe: "RemoteProbe") -> None:
    """Idempotently write or replace a named kanshi output profile.

    step.command   — the profile block to write (rendered kanshi syntax)
    step.config_file — kanshi config path (default: ~/.config/kanshi/config)
    """
    from ..hardware.kiosk.output_profiles import OutputProfile

    profile_block = step.command
    if not profile_block:
        raise StepError(step, "ensure_kanshi_profile requires step.command with profile block")

    config_path = step.config_file or "~/.config/kanshi/config"
    mkdir_cmd = f"mkdir -p $(dirname {config_path})"
    probe.run(mkdir_cmd, timeout=10)

    r = probe.run(f"cat {config_path} 2>/dev/null || echo ''", timeout=10)
    existing = r.out if r.ok else ""

    # Extract profile name from block (first line: "profile <name> {")
    first_line = profile_block.strip().splitlines()[0]
    import re
    m = re.match(r"profile\s+(\S+)\s*\{", first_line)
    if not m:
        raise StepError(step, f"Cannot parse profile name from block: {first_line!r}")
    profile_name = m.group(1)

    # Replace existing profile block or append
    pattern = re.compile(
        rf"^profile\s+{re.escape(profile_name)}\s*\{{[^}}]*\}}", re.MULTILINE | re.DOTALL
    )
    if pattern.search(existing):
        if profile_block.strip() in existing:
            step.status = StepStatus.DONE
            step.result = f"no-op: profile '{profile_name}' already correct"
            return
        new_content = pattern.sub(profile_block.strip(), existing)
        changed = True
    else:
        sep = "\n" if existing and not existing.endswith("\n") else ""
        new_content = existing + sep + profile_block.strip() + "\n"
        changed = True

    encoded = base64.b64encode(new_content.encode()).decode()
    tmp = f"/tmp/redeploy-kanshi-{step.id}.conf"
    write_r = probe.run(
        f"echo '{encoded}' | base64 -d | tee {tmp} > /dev/null && mv {tmp} {config_path}",
        timeout=15,
    )
    if not write_r.ok:
        raise StepError(step, f"Cannot write {config_path}: {write_r.stderr[:200]}")

    # Reload kanshi if running
    probe.run("pkill -SIGUSR1 kanshi 2>/dev/null || true", timeout=5)

    step.status = StepStatus.DONE
    step.result = f"profile '{profile_name}' written to {config_path}"


def run_ensure_autostart_entry(step: MigrationStep, probe: "RemoteProbe") -> None:
    """Idempotently add or replace a keyed entry in a compositor autostart file.

    step.config_file — path to autostart file
    step.config_line — the line to write (the entry body)
    step.config_section — used as the entry key for idempotent marker
    """
    from ..hardware.kiosk.autostart import AutostartEntry, ensure_autostart_entry

    if not step.config_file or not step.config_line:
        raise StepError(step, "ensure_autostart_entry requires config_file and config_line")

    key = step.config_section or "redeploy"
    entry = AutostartEntry(key=key, line=step.config_line)

    r = probe.run(f"cat {step.config_file} 2>/dev/null || echo ''", timeout=10)
    existing = r.out if r.ok else ""

    new_content, changed = ensure_autostart_entry(existing, entry)
    if not changed:
        step.status = StepStatus.DONE
        step.result = f"no-op: entry [{key}] already correct"
        return

    mkdir_cmd = f"mkdir -p $(dirname {step.config_file})"
    probe.run(mkdir_cmd, timeout=10)

    encoded = base64.b64encode(new_content.encode()).decode()
    tmp = f"/tmp/redeploy-autostart-{step.id}.txt"
    write_r = probe.run(
        f"echo '{encoded}' | base64 -d | tee {tmp} > /dev/null && mv {tmp} {step.config_file}",
        timeout=15,
    )
    if not write_r.ok:
        raise StepError(step, f"Cannot write {step.config_file}: {write_r.stderr[:200]}")

    step.status = StepStatus.DONE
    step.result = f"entry [{key}] written to {step.config_file}"


def run_ensure_browser_kiosk_script(step: MigrationStep, probe: "RemoteProbe") -> None:
    """Write a kiosk-launch.sh script to the remote device.

    step.command   — the full script content to write
    step.dst       — destination path (default: ~/kiosk-launch.sh)
    """
    script_content = step.command
    if not script_content:
        raise StepError(step, "ensure_browser_kiosk_script requires step.command with script body")

    dst = step.dst or "~/kiosk-launch.sh"

    r = probe.run(f"cat {dst} 2>/dev/null || echo ''", timeout=10)
    existing = r.out if r.ok else ""
    if existing.strip() == script_content.strip():
        step.status = StepStatus.DONE
        step.result = f"no-op: {dst} already correct"
        return

    encoded = base64.b64encode(script_content.encode()).decode()
    tmp = f"/tmp/redeploy-kiosk-{step.id}.sh"
    write_r = probe.run(
        f"echo '{encoded}' | base64 -d | tee {tmp} > /dev/null"
        f" && chmod +x {tmp} && mv {tmp} {dst}",
        timeout=15,
    )
    if not write_r.ok:
        raise StepError(step, f"Cannot write {dst}: {write_r.stderr[:200]}")

    step.status = StepStatus.DONE
    step.result = f"kiosk script written to {dst}"

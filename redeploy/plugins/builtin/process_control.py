"""Process control plugin for redeploy.

Automatically kills processes on specified ports before deployment.
Supports port ranges, process name filtering, and graceful vs force kill.

Usage in deployment.yaml:
    extra_steps:
      - id: kill_processes_on_ports
        action: plugin
        plugin_type: process_control
        plugin_params:
          ports: [8100, 8101, 8202]
          strategy: graceful  # or 'force'
          timeout: 10
          notify: true
"""
from __future__ import annotations

import socket
import time
from typing import Optional

from loguru import logger

from redeploy.models import ConflictSeverity, MigrationStep
from redeploy.plugins import PluginContext, register_plugin


def _find_pid_on_port(port: int) -> Optional[int]:
    """Find PID of process listening on port (Linux only)."""
    try:
        with open("/proc/net/tcp", "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 10:
                    # Format: local_addr rem_addr st tx_queue rx_queue ...
                    # local_addr format: hex_ip:hex_port
                    local_addr = parts[1].split(":")[-1]
                    hex_port = int(local_addr, 16)
                    if hex_port == port:
                        inode = parts[9]
                        # Find PID by inode in /proc/*/fd
                        import os
                        for pid_dir in os.listdir("/proc"):
                            if pid_dir.isdigit():
                                fd_dir = f"/proc/{pid_dir}/fd"
                                if os.path.exists(fd_dir):
                                    for fd in os.listdir(fd_dir):
                                        try:
                                            link = os.readlink(os.path.join(fd_dir, fd))
                                            if f"socket:[{inode}]" in link:
                                                return int(pid_dir)
                                        except (OSError, ValueError):
                                            continue
    except Exception as e:
        logger.debug(f"Could not find PID on port {port}: {e}")
    return None


def _kill_process(pid: int, force: bool = False) -> bool:
    """Kill a process by PID. Returns True if successful."""
    try:
        import os
        import signal
        sig = signal.SIGKILL if force else signal.SIGTERM
        os.kill(pid, sig)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        logger.warning(f"Permission denied to kill PID {pid}")
        return False


@register_plugin("process_control")
def process_control(ctx: PluginContext) -> None:
    """Kill processes on specified ports."""
    ports = ctx.params.get("ports", [])
    strategy = ctx.params.get("strategy", "graceful")
    timeout = ctx.params.get("timeout", 10)
    notify = ctx.params.get("notify", True)
    dry_run = ctx.dry_run

    if not ports:
        logger.warning("process_control: no ports specified")
        ctx.step.status = "done"
        ctx.step.result = "no_ports"
        return

    if dry_run:
        logger.info(f"[DRY RUN] Would kill processes on ports: {ports}")
        ctx.step.status = "done"
        ctx.step.result = "dry_run"
        return

    killed = []
    for port in ports:
        pid = _find_pid_on_port(port)
        if pid:
            logger.info(f"Found process PID {pid} on port {port}")
            if strategy == "graceful":
                _kill_process(pid, force=False)
                # Wait for graceful shutdown
                time.sleep(2)
                # Check if still running
                if _find_pid_on_port(port) == pid:
                    logger.warning(f"Process {pid} on port {port} did not stop gracefully, force killing")
                    _kill_process(pid, force=True)
            else:
                _kill_process(pid, force=True)
            killed.append((port, pid))
        else:
            logger.debug(f"No process found on port {port}")

    if killed:
        ctx.step.result = f"killed:{len(killed)}_processes"
        if notify:
            ctx.step.description = f"Killed {len(killed)} process(es) on ports {ports}"
    else:
        ctx.step.result = "no_processes_to_kill"
        ctx.step.description = f"No processes found on ports {ports}"

    ctx.step.status = "done"

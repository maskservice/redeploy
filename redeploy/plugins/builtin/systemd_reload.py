"""Built-in plugin: systemd_reload

Runs ``systemctl daemon-reload`` then restarts one or more systemd units.
Optionally waits for the service to reach ``active (running)`` state.

YAML example
------------
  steps:
    - id: reload_kiosk_svc
      action: plugin
      plugin_type: systemd_reload
      description: Reload systemd and restart kiosk service
      plugin_params:
        units:
          - c2004-services.service
        daemon_reload: true      # default: true
        wait_active: true        # wait until service is active (default: true)
        wait_timeout: 30         # seconds to wait (default: 30)

CSS DSL example (redeploy.css workflow step)
---------------------------------------------
  step-3: plugin systemd_reload units=c2004-services.service;
"""
from __future__ import annotations

import time

from loguru import logger

from redeploy.models import StepStatus
from redeploy.plugins import PluginContext, register_plugin


@register_plugin("systemd_reload")
def systemd_reload(ctx: PluginContext) -> None:
    units: list[str] = ctx.params.get("units", [])
    if isinstance(units, str):
        units = [u.strip() for u in units.split(",") if u.strip()]
    daemon_reload: bool = bool(ctx.params.get("daemon_reload", True))
    wait_active: bool = bool(ctx.params.get("wait_active", True))
    wait_timeout: int = int(ctx.params.get("wait_timeout", 30))

    if ctx.dry_run:
        ctx.step.result = f"dry-run: would reload {units}"
        ctx.step.status = StepStatus.DONE
        return

    from redeploy.apply.executor import StepError

    results: list[str] = []

    if daemon_reload:
        r = ctx.probe.run("systemctl daemon-reload", timeout=15)
        if not r.ok:
            raise StepError(ctx.step, f"daemon-reload failed: {r.stderr[:150]}")
        logger.debug("    systemctl daemon-reload OK")
        if ctx.emitter:
            ctx.emitter.progress(ctx.step.id, "daemon-reload OK")

    for unit in units:
        r = ctx.probe.run(f"systemctl restart {unit}", timeout=30)
        if not r.ok:
            raise StepError(ctx.step, f"restart {unit} failed: {r.stderr[:150]}")
        logger.debug(f"    restarted {unit}")
        if ctx.emitter:
            ctx.emitter.progress(ctx.step.id, f"restarted {unit}")

        if wait_active:
            _wait_for_active(ctx, unit, wait_timeout)

        results.append(unit)

    ctx.step.result = f"reloaded+restarted: {', '.join(results)}"
    ctx.step.status = StepStatus.DONE


def _wait_for_active(ctx: PluginContext, unit: str, timeout: int) -> None:
    """Poll ``systemctl is-active`` until active or timeout."""
    from redeploy.apply.executor import StepError

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = ctx.probe.run(f"systemctl is-active {unit}", timeout=5)
        state = r.out.strip()
        if state == "active":
            logger.debug(f"    {unit} is active")
            return
        if state in ("failed", "inactive"):
            # Grab journal tail for better error message
            j = ctx.probe.run(f"journalctl -u {unit} -n 20 --no-pager 2>/dev/null", timeout=8)
            raise StepError(ctx.step,
                            f"{unit} entered state '{state}' after restart.\n"
                            + (j.out[-400:] if j.ok else ""))
        if ctx.emitter:
            ctx.emitter.progress(ctx.step.id, f"{unit}: {state}…")
        time.sleep(2)

    raise StepError(ctx.step, f"{unit} did not become active within {timeout}s")

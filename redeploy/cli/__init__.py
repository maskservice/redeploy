"""redeploy CLI — detect | plan | apply | migrate."""
from __future__ import annotations

import sys

import click
from loguru import logger

from .. import __version__


def _setup_logging(verbose: bool) -> None:
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | {message}",
    )


@click.group()
@click.version_option(__version__)
@click.option("-v", "--verbose", is_flag=True)
@click.pass_context
def cli(ctx, verbose):
    """redeploy — Infrastructure migration toolkit: detect → plan → apply"""
    _setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


# Import all commands from submodules (not from package level)
from .commands.audit import audit
from .commands.detect import detect
from .commands.devices import devices, scan, device_add, device_rm
from .commands.diagnose import diagnose
from .commands.diff import diff
from .commands.export import export_cmd
from .commands.import_ import import_cmd
from .commands.inspect import inspect
from .commands.patterns import patterns
from .commands.plugin import plugin_cmd
from .commands.probe import probe
from .commands.target import target
from .commands.version import version_cmd
from .commands.workflow import workflow_cmd
from .commands.exec_ import exec_cmd, exec_multi_cmd
from .commands.plan_apply import plan, apply, migrate, run
from .commands.state import state_cmd
from .commands.hardware import hardware
from .commands.push import push
from .commands.device_map import device_map_cmd
from .commands.blueprint import blueprint_cmd
from .commands.init import init
from .commands.status import status

# Register commands
cli.add_command(audit)
cli.add_command(detect)
cli.add_command(devices)
cli.add_command(scan)
cli.add_command(device_add)
cli.add_command(device_rm)
cli.add_command(diagnose)
cli.add_command(diff)
cli.add_command(exec_cmd)
cli.add_command(exec_multi_cmd)
cli.add_command(export_cmd)
cli.add_command(import_cmd)
cli.add_command(hardware)
cli.add_command(push)
cli.add_command(device_map_cmd, name="device-map")
cli.add_command(blueprint_cmd, name="blueprint")
cli.add_command(init)
cli.add_command(inspect)
cli.add_command(patterns)
cli.add_command(plan)
cli.add_command(apply)
cli.add_command(migrate)
cli.add_command(run)
cli.add_command(plugin_cmd)
cli.add_command(probe)
cli.add_command(state_cmd)
cli.add_command(status)
cli.add_command(target)
cli.add_command(version_cmd)
cli.add_command(workflow_cmd)


# Backward compatibility: _resolve_device for tests
def _resolve_device(console, device_id: str) -> tuple:
    """Resolve device from registry or auto-probe. Returns (device, registry) or (None, None)."""
    from ..discovery import auto_probe
    from ..models import DeviceRegistry

    reg = DeviceRegistry.load()
    dev = reg.get(device_id)

    if not dev:
        console.print(f"[yellow]⚠ {device_id} not in registry — probing…[/yellow]")
        r = auto_probe(device_id, timeout=8, save=True)
        if r.reachable:
            reg = DeviceRegistry.load()
            dev = reg.get(r.host) or reg.get(r.ip)
            key_name = __import__('os').path.basename(r.ssh_key) if r.ssh_key else 'agent'
            console.print(f"  [green]✓[/green] auto-probe OK: {r.host}  strategy={r.strategy}  key={key_name}")
        else:
            console.print(f"  [red]✗ probe failed: {r.error}[/red]")
            console.print("[dim]  Add manually: redeploy device-add HOST --strategy STRATEGY[/dim]")

    return dev, reg


__all__ = ["cli", "_resolve_device"]

"""target command — Deploy spec to a specific registered device."""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

from ..core import (
    resolve_device,
    load_spec_with_manifest,
    overlay_device_onto_spec,
    run_detect_for_spec,
)
from ..display import print_plan_table


@click.command()
@click.argument("device_id")
@click.argument("spec_file", default=None, required=False, type=click.Path(), metavar="SPEC")
@click.option("--dry-run", is_flag=True)
@click.option("--plan-only", is_flag=True)
@click.option("--detect", "do_detect", is_flag=True)
@click.option("--plan-out", default=None, type=click.Path())
def target(device_id, spec_file, dry_run, plan_only, do_detect, plan_out):
    """Deploy a spec to a specific registered device.

    DEVICE_ID is looked up in ~/.config/redeploy/devices.yaml.
    Device's host, strategy, app, domain are overlaid onto the spec.

    \b
    Example:
        redeploy target pi@192.168.1.42
        redeploy target pi@192.168.1.42 migration.yaml --dry-run
        redeploy target kiosk-01 --detect --plan-only
    """
    console = Console()

    # Resolve device
    dev, reg = resolve_device(console, device_id)

    # Resolve spec
    spec, manifest = load_spec_with_manifest(console, spec_file, dev)

    # Overlay device values onto spec
    if dev:
        overlay_device_onto_spec(spec, dev, console)
    else:
        spec.source.host = device_id
        spec.target.host = device_id
        console.print(f"[bold]target[/bold]  {device_id}")

    # Run detect if requested and generate plan
    planner = run_detect_for_spec(console, spec, do_detect)

    console.print(f"\n[bold]plan[/bold]")
    migration = planner.run()
    print_plan_table(console, migration)

    if plan_out:
        planner.save(migration, Path(plan_out))
        console.print(f"  [dim]plan saved → {plan_out}[/dim]")

    if plan_only:
        console.print("\n[dim]--plan-only: stopping before apply[/dim]")
        return

    # Pass ssh_key from registry to executor
    from ...apply import Executor

    ssh_key = dev.ssh_key if dev else ""
    executor = Executor(migration, dry_run=dry_run, ssh_key=ssh_key or None)
    ok = executor.run()

    # Record deploy in registry
    if dev and not dry_run:
        from ...models import DeployRecord

        dev.record_deploy(
            DeployRecord(
                spec_name=spec.name,
                from_strategy=spec.source.strategy.value,
                to_strategy=spec.target.strategy.value,
                version=spec.target.version or "",
                ok=ok,
            )
        )
        dev.app = spec.target.app
        dev.strategy = spec.target.strategy.value
        reg.upsert(dev)
        reg.save()

    console.print(f"\n{executor.summary()}")

    if not ok:
        sys.exit(1)

"""push command — Apply a desired-state YAML/JSON file to a remote host.

Declarative workflow:
    redeploy hardware pi@host > device.yaml    # scan current state
    # edit device.yaml (e.g. set transform: '270')
    redeploy push pi@host device.yaml          # apply diff to device

redeploy push detects the file type automatically (hardware, infra, …)
and dispatches to the appropriate state reconciler.

Multiple files can be pushed in one call:
    redeploy push pi@host hardware.yaml infra.yaml
"""
from __future__ import annotations

import sys

import click
from rich.console import Console
from rich import box
from rich.table import Table


@click.command()
@click.argument("host")
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--dry-run", is_flag=True, help="Show what would be applied without changing anything")
@click.option("--ssh-key", default=None, type=click.Path(), help="SSH private key path")
def push(host, files, dry_run, ssh_key):
    """Apply desired-state YAML/JSON file(s) to a remote host.

    Reads each FILE, detects its schema (hardware, infra, …) and applies
    only the settings that differ from the current device state.

    \b
    Workflow:
        redeploy hardware pi@192.168.188.109 > pi109.yaml
        # edit pi109.yaml: change drm_outputs[0].transform to '270'
        redeploy push pi@192.168.188.109 pi109.yaml

    \b
    Multiple files:
        redeploy push pi@host hardware.yaml infra.yaml
    """
    import yaml
    import json as _json

    from ...detect.remote import RemoteProbe
    from ...apply.state_apply import apply_state

    console = Console()

    if dry_run:
        console.print("[yellow]dry-run mode — no changes will be made[/yellow]\n")

    p = RemoteProbe(host, ssh_key=ssh_key) if ssh_key else RemoteProbe(host)

    overall_ok = True

    for file_path in files:
        console.print(f"\n[bold cyan]── {file_path}[/bold cyan]")

        with open(file_path) as f:
            raw = f.read()
        try:
            data = yaml.safe_load(raw)
        except Exception:
            try:
                data = _json.loads(raw)
            except Exception as exc:
                console.print(f"[red]✗ cannot parse {file_path}: {exc}[/red]")
                overall_ok = False
                continue

        if not isinstance(data, dict):
            console.print(f"[red]✗ {file_path}: expected a mapping, got {type(data).__name__}[/red]")
            overall_ok = False
            continue

        if dry_run:
            from ...apply.state_apply import detect_handler
            handler = detect_handler(data)
            console.print(
                f"  handler: [cyan]{handler.name if handler else 'unknown'}[/cyan]\n"
                f"  keys: {list(data.keys())}"
            )
            continue

        result = apply_state(data, p, console)

        # Summary table
        console.print()
        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        t.add_column(style="dim", width=10)
        t.add_column()
        t.add_row("applied",  "\n".join(result.applied) or "—")
        t.add_row("skipped",  "\n".join(result.skipped) or "—")
        if result.errors:
            t.add_row("[red]errors[/red]", "\n".join(result.errors))
        console.print(t)

        if not result.ok:
            overall_ok = False

    if not dry_run:
        if overall_ok:
            console.print(f"\n[bold green]✓ push complete[/bold green]")
        else:
            console.print(f"\n[bold red]✗ push finished with errors[/bold red]")
            sys.exit(1)

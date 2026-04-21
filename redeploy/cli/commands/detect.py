"""detect command — Probe infrastructure and produce infra.yaml."""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ..core import run_detect_workflow
from ..display import (
    print_infrastructure_summary,
    print_docker_services,
    print_k3s_pods,
    print_conflicts,
)


@click.command()
@click.option("--host", default=None, help="SSH host (user@ip) or 'local'")
@click.option(
    "--app",
    default=None,
    show_default=True,
    help="Application name (default from redeploy.yaml)",
)
@click.option("--domain", default=None, help="Public domain for HTTP health checks")
@click.option(
    "-o",
    "--output",
    default="infra.yaml",
    show_default=True,
    type=click.Path(),
    help="Output file for InfraState",
)
@click.option(
    "--workflow",
    "run_workflow",
    is_flag=True,
    help="Run full multi-host workflow (detect + template scoring)",
)
@click.option(
    "--scan", "scan_subnet", default=None, help="Subnet to scan for devices (used with --workflow)"
)
@click.option(
    "--no-deep", is_flag=True, help="Workflow: skip deep SSH probe (faster, less accurate)"
)
@click.option(
    "--save-yaml",
    default=None,
    type=click.Path(),
    help="Workflow: save generated manifest to file",
)
@click.option(
    "--format",
    "output_fmt",
    default="yaml",
    type=click.Choice(["yaml", "css"]),
    help="Output format for generated manifest (yaml or css)",
)
@click.pass_context
def detect(
    ctx, host, app, domain, output, run_workflow, scan_subnet, no_deep, save_yaml, output_fmt
):
    """Probe infrastructure and produce infra.yaml.

    With --workflow: multi-host detection with template scoring.
    Reads hosts from redeploy.yaml / redeploy.css environments + registry + --scan.

    \b
    Examples:
        redeploy detect --host pi@192.168.188.108
        redeploy detect --workflow
        redeploy detect --workflow --format css --save-yaml redeploy.css
        redeploy detect --workflow --scan 192.168.188.0/24
        redeploy detect --workflow --no-deep
    """
    from ...models import ProjectManifest
    from ...detect import Detector

    console = Console()
    manifest = ProjectManifest.find_and_load(Path.cwd())
    app_name = app or (manifest.app if manifest else "app")

    if run_workflow or scan_subnet:
        run_detect_workflow(
            console,
            hosts=[host] if host else [],
            manifest=manifest,
            app=app_name,
            scan_subnet=scan_subnet,
            deep=not no_deep,
            save_yaml=save_yaml,
            fmt=output_fmt,
        )
        return

    if not host:
        console.print("[red]✗ --host required (or use --workflow)[/red]")
        sys.exit(1)

    out_path = Path(output)
    domain = domain or (manifest.domain if manifest else None)

    try:
        d = Detector(host=host, app=app_name, domain=domain)
        from ...integrations.op3_bridge import should_use_op3
        if should_use_op3():
            from ...integrations.op3_bridge import (
                make_scanner,
                make_ssh_context,
                snapshot_to_infra_state,
            )
            scanner = make_scanner(
                [
                    "runtime.container",
                    "service.containers",
                    "endpoint.http",
                    "business.health",
                ]
            )
            ctx = make_ssh_context(target=host)
            snapshot = scanner.scan(host, ctx.execute)
            state = snapshot_to_infra_state(snapshot, host=host)
        else:
            state = d.run()
        d.save(state, out_path)
    except ConnectionError as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)

    print_infrastructure_summary(console, state, host)
    print_docker_services(console, state)
    print_k3s_pods(console, state)
    print_conflicts(console, state)
    console.print(f"\n[dim]Saved to {out_path}[/dim]")

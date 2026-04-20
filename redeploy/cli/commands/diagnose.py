"""diagnose command — Compare a migration spec against the live target host."""
from __future__ import annotations

import sys

import click
import yaml
from rich.console import Console
from rich.table import Table


@click.command()
@click.argument("spec", type=click.Path(exists=True, dir_okay=False))
@click.option("--host", default=None, help="Override target host (default: spec.target.host)")
@click.option("--ssh-key", default=None, type=click.Path(), help="Path to SSH private key")
@click.option(
    "--format", "output_fmt", default="rich", type=click.Choice(["rich", "yaml", "json"]), help="Report format"
)
@click.option("--exit-on-fail", is_flag=True, help="Exit with non-zero status if any check fails")
@click.pass_context
def diagnose(ctx, spec, host, ssh_key, output_fmt, exit_on_fail):
    """Compare a migration spec against the live target host.

    Walks the spec (YAML or markpact .md), derives all expected facts
    (binaries, directories, ports, container images, systemd units,
    apt packages, env files, free disk) and probes the target read-only
    via SSH. Reports what is missing or out of spec — without applying
    any change.

    \b
    Examples:
        redeploy diagnose migration.podman-rpi5-resume.md
        redeploy diagnose migration.yaml --host pi@192.168.188.108
        redeploy diagnose migration.md --format yaml
    """
    from ...audit import audit_spec

    console = Console()
    try:
        report = audit_spec(spec, host=host, ssh_key=ssh_key)
    except Exception as exc:
        console.print(f"[red]✗ audit failed: {exc}[/red]")
        sys.exit(2)

    if output_fmt == "yaml":
        click.echo(yaml.safe_dump(report.to_dict(), sort_keys=False))
    elif output_fmt == "json":
        import json as _json

        click.echo(_json.dumps(report.to_dict(), indent=2))
    else:
        console.print(
            f"\n[bold]audit[/bold]  spec=[cyan]{report.spec_path}[/cyan]  "
            f"host=[cyan]{report.host}[/cyan]  "
            f"target=[cyan]{report.target_strategy}[/cyan]"
        )
        t = Table(show_header=True, box=None, padding=(0, 1))
        t.add_column("Status", width=6)
        t.add_column("Category", style="dim")
        t.add_column("Name")
        t.add_column("Detail", style="dim")
        t.add_column("Source", style="dim")
        icon = {
            "pass": "[green]✓[/green]",
            "fail": "[red]✗[/red]",
            "warn": "[yellow]![/yellow]",
            "skip": "[dim]·[/dim]",
        }
        for c in report.checks:
            t.add_row(
                icon.get(c.status, c.status),
                c.category,
                c.name,
                c.detail[:60],
                c.source_step,
            )
        console.print(t)

        if report.failed:
            console.print("\n[bold red]Missing / failing:[/bold red]")
            for c in report.failed:
                hint = f" — [dim]{c.fix_hint}[/dim]" if c.fix_hint else ""
                console.print(f"  [red]✗[/red] {c.category}/{c.name}{hint}")

        console.print(f"\n{report.summary()}")

    if exit_on_fail and not report.ok:
        sys.exit(1)

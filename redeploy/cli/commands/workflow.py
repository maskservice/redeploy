"""workflow command — Run named workflow from redeploy.css."""
from __future__ import annotations

import sys
import subprocess as _sp
from pathlib import Path

import click
from rich.console import Console


@click.command("workflow")
@click.argument("name", required=False, default=None)
@click.option(
    "--file", "css_file", default=None, type=click.Path(),
    help="redeploy.css file (auto-detected if omitted)"
)
@click.option("--dry-run", is_flag=True, help="Print steps without executing")
@click.option("--list", "list_only", is_flag=True, help="List all available workflows")
@click.pass_context
def workflow_cmd(ctx, name, css_file, dry_run, list_only):
    """Run a named workflow from redeploy.css.

    \b
    Examples:
        redeploy workflow --list
        redeploy workflow deploy:prod
        redeploy workflow deploy:rpi5 --dry-run
        redeploy workflow release
    """
    from ...models import ProjectManifest
    from ...dsl.loader import load_css

    console = Console()

    css_path = Path(css_file) if css_file else ProjectManifest.find_css(Path.cwd())
    if not css_path or not css_path.exists():
        console.print("[red]✗ No redeploy.css found. Create one or use --file.[/red]")
        sys.exit(1)

    result = load_css(css_path)

    if list_only or not name:
        _list_workflows(console, css_path, result)
        return

    wf = next((w for w in result.workflows if w.name == name), None)
    if not wf:
        available = [w.name for w in result.workflows]
        console.print(f"[red]✗ Workflow '{name}' not found.[/red]")
        console.print(f"  Available: {', '.join(available)}")
        sys.exit(1)

    _execute_workflow(console, wf, dry_run, css_path)


def _list_workflows(console, css_path, result) -> None:
    """List workflows from CSS."""
    console.print(f"[bold]Workflows in {css_path.name}:[/bold]")
    for wf in result.workflows:
        console.print(
            f"  [cyan]{wf.name}[/cyan]"
            + (f"  [dim]{wf.description}[/dim]" if wf.description else "")
        )
        for step in wf.steps:
            console.print(f"    step-{step.index}: [dim]{step.command[:70]}[/dim]")


def _execute_workflow(console, wf, dry_run, css_path) -> None:
    """Execute a workflow."""
    console.print(
        f"[bold]workflow[/bold] [cyan]{wf.name}[/cyan]"
        + (f"  [dim]{wf.description}[/dim]" if wf.description else "")
    )

    for step in wf.steps:
        console.print(f"\n  [dim]step-{step.index}[/dim]  {step.command}")
        if dry_run:
            continue
        ret = _sp.run(step.command, shell=True, cwd=str(css_path.parent))
        if ret.returncode != 0:
            console.print(f"  [red]✗ step-{step.index} failed (exit {ret.returncode})[/red]")
            sys.exit(ret.returncode)
        console.print(f"  [green]✓[/green]")

    if not dry_run:
        console.print(f"\n[green]✓ workflow '{wf.name}' complete[/green]")

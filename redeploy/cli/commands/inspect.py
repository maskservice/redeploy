"""inspect command — Show parsed content of redeploy.css."""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

from ..display import (
    print_inspect_app_metadata,
    print_inspect_environments,
    print_inspect_templates,
    print_inspect_workflows,
    print_inspect_devices,
    print_inspect_raw_nodes_summary,
)


def _find_css_path(css_file, console) -> Path | None:
    """Find CSS file path."""
    from ...models import ProjectManifest

    if css_file:
        return Path(css_file)
    css_path = ProjectManifest.find_css(Path.cwd())
    if css_path and css_path.exists():
        return css_path
    return None


@click.command()
@click.option(
    "--file", "css_file", default=None, type=click.Path(),
    help="redeploy.css / redeploy.less file (auto-detected if omitted)"
)
@click.pass_context
def inspect(ctx, css_file):
    """Show parsed content of redeploy.css — environments, templates, workflows.

    Transparent view of what redeploy reads from the DSL file.
    Useful for debugging and for LLMs to understand project configuration.

    \b
    Examples:
        redeploy inspect
        redeploy inspect --file redeploy.css
    """
    from ...models import ProjectManifest
    from ...dsl.loader import load_css

    console = Console()

    css_path = _find_css_path(css_file, console)

    if not css_path or not css_path.exists():
        console.print("[yellow]No redeploy.css found — falling back to redeploy.yaml[/yellow]")
        manifest = ProjectManifest.find_and_load(Path.cwd())
        if not manifest:
            console.print("[red]✗ No redeploy.css or redeploy.yaml found[/red]")
            sys.exit(1)
        console.print(f"  app={manifest.app}  envs={list(manifest.environments.keys())}")
        return

    result = load_css(css_path)
    console.print(f"\n[bold]redeploy inspect[/bold]  [dim]{css_path}[/dim]\n")

    print_inspect_app_metadata(console, result)
    print_inspect_environments(console, result)
    print_inspect_templates(console, result)
    print_inspect_workflows(console, result)
    print_inspect_devices(console, result)
    print_inspect_raw_nodes_summary(console, result)

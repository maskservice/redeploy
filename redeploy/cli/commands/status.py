"""status command — Show project manifest and spec summary."""
from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ..core import load_spec_or_exit, find_manifest_path


@click.command()
@click.argument("spec_file", default=None, required=False, type=click.Path(), metavar="SPEC")
def status(spec_file):
    """Show current project manifest and spec summary.

    \b
    Example:
        redeploy status
        redeploy status migration.yaml
    """
    from ...models import ProjectManifest

    console = Console()

    manifest = ProjectManifest.find_and_load(Path.cwd())
    if manifest:
        console.print(f"[bold]redeploy.yaml[/bold]  [dim]{find_manifest_path()}[/dim]")
        t = Table(show_header=False, box=None, padding=(0, 2))
        for k, v in manifest.model_dump().items():
            if v is not None and v != "" and v != 22:
                t.add_row(f"  [dim]{k}[/dim]", str(v))
        console.print(t)
    else:
        console.print("[dim]no redeploy.yaml found (run `redeploy init`)[/dim]")

    resolved = spec_file or (manifest.spec if manifest else "migration.yaml")
    spec_path = Path(resolved)
    if spec_path.exists():
        spec = load_spec_or_exit(console, spec_path)
        if manifest:
            manifest.apply_to_spec(spec)
        console.print(f"\n[bold]{spec_path}[/bold]  [dim]{spec.name}[/dim]")
        console.print(
            f"  {spec.source.strategy.value}  →  [cyan]{spec.target.strategy.value}[/cyan]"
        )
        console.print(f"  host={spec.source.host}  app={spec.source.app}")
        if spec.target.domain:
            console.print(f"  domain={spec.target.domain}")
        if spec.target.verify_url:
            console.print(f"  verify_url={spec.target.verify_url}")
    else:
        console.print(f"\n[yellow]⚠ spec not found: {resolved}[/yellow]")
        console.print("[dim]  Run `redeploy init` to create it.[/dim]")

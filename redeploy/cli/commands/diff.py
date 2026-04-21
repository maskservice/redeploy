"""diff command — Compare IaC file vs live host (drift detection). [Phase 3 — stub]"""
from __future__ import annotations

import click
from rich.console import Console


@click.command()
@click.option(
    "--ci", "ci_file", default=None, type=click.Path(exists=True),
    help="IaC/CI file to compare (docker-compose, GHA workflow, …)"
)
@click.option("--host", default=None, help="Live host to compare against (user@host)")
@click.option(
    "--from", "from_src", default=None, type=click.Path(exists=True),
    help="Left side: IaC file or directory"
)
@click.option(
    "--to", "to_src", default=None,
    help="Right side: IaC file/directory or SSH host"
)
def diff(ci_file, host, from_src, to_src):
    """Compare IaC file vs live host (drift detection).  [Phase 3 — coming soon]

    \b
    Examples:
        redeploy diff --ci docker-compose.yml --host root@prod
        redeploy diff --from docker-compose.yml --to root@prod
    """
    console = Console()
    console.print("[yellow]⚠ redeploy diff is not yet implemented (Phase 3).[/yellow]")
    console.print("  Planned: compare IaC file vs live SSH probe for drift detection.")
    console.print("  Use [bold]redeploy import[/bold] to parse IaC files for now.")

"""patterns command — List available deploy patterns or show detail for one."""
from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.table import Table


@click.command()
@click.argument("name", default=None, required=False)
def patterns(name):
    """List available deploy patterns or show detail for one.

    \b
    Examples:
        redeploy patterns
        redeploy patterns blue_green
        redeploy patterns canary
    """
    from ...patterns import (
        pattern_registry,
        BlueGreenPattern,
        CanaryPattern,
        RollbackOnFailurePattern,
    )

    console = Console()

    if name:
        cls = pattern_registry.get(name)
        if not cls:
            console.print(f"[red]Pattern '{name}' not found.[/red]")
            console.print(f"  Available: {', '.join(pattern_registry.keys())}")
            sys.exit(1)

        p_map = {
            "blue_green": BlueGreenPattern(
                app="myapp", remote_dir="~/myapp", verify_url="http://localhost:8080"
            ),
            "canary": CanaryPattern(
                app="myapp", remote_dir="~/myapp", verify_url="http://localhost:8080"
            ),
            "rollback_on_failure": RollbackOnFailurePattern(
                app="myapp", remote_dir="~/myapp", verify_url="http://localhost:8080"
            ),
        }
        instance = p_map.get(name)
        steps = instance.expand() if instance else []

        console.print(f"\n[bold]{name}[/bold] — {cls.description}")
        if steps:
            t = Table(show_header=True, box=None, padding=(0, 2))
            t.add_column("#", style="dim", width=3)
            t.add_column("ID")
            t.add_column("Action", style="cyan")
            t.add_column("Risk", style="dim")
            t.add_column("Rollback", style="dim")
            for i, s in enumerate(steps, 1):
                t.add_row(
                    str(i),
                    s.id,
                    s.action.value,
                    s.risk.value,
                    "✓" if s.rollback_command else "—",
                )
            console.print(t)

        console.print(f"\n  [dim]Usage in target config:[/dim]")
        console.print(f"    [cyan]pattern: {name}[/cyan]")
        console.print(f"    [cyan]pattern_config:[/cyan]")
        console.print(f"      [cyan]verify_url: http://your-app/health[/cyan]")
        return

    # List all patterns
    console.print("\n[bold]Available deploy patterns:[/bold]\n")
    t = Table(show_header=True, box=None, padding=(0, 2))
    t.add_column("Name", style="bold cyan")
    t.add_column("Description")
    t.add_column("Steps", style="dim")

    step_counts = {
        "blue_green": len(
            BlueGreenPattern(app="x", remote_dir="~/x", verify_url="http://x").expand()
        ),
        "canary": len(
            CanaryPattern(app="x", remote_dir="~/x", verify_url="http://x").expand()
        ),
        "rollback_on_failure": len(
            RollbackOnFailurePattern(
                app="x", remote_dir="~/x", verify_url="http://x"
            ).expand()
        ),
    }

    for pname, cls in pattern_registry.items():
        t.add_row(pname, cls.description, str(step_counts.get(pname, "?")))
    console.print(t)

    console.print(
        "\n  [dim]Use [bold]redeploy patterns <name>[/bold] for step details[/dim]"
    )
    console.print("  [dim]Set in target YAML:  pattern: blue_green[/dim]")

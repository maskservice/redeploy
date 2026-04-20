"""plugin command — List or inspect registered redeploy plugins."""
from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.table import Table


@click.command("plugin")
@click.argument(
    "subcommand", default="list", type=click.Choice(["list", "info"])
)
@click.argument("name", required=False, default=None)
@click.pass_context
def plugin_cmd(ctx, subcommand, name):
    """List or inspect registered redeploy plugins.

    \b
    Examples:
        redeploy plugin list
        redeploy plugin info browser_reload
        redeploy plugin info systemd_reload
    """
    from ...plugins import registry, load_user_plugins

    console = Console()
    load_user_plugins()
    # Trigger builtin load
    _ = registry.names()

    if subcommand == "list":
        names = registry.names()
        if not names:
            console.print("[yellow]No plugins registered.[/yellow]")
            return
        console.print(f"\n[bold]Registered plugins ({len(names)})[/bold]\n")
        t = Table(show_header=True, box=None, padding=(0, 2))
        t.add_column("Name", style="cyan")
        t.add_column("Module", style="dim")
        t.add_column("Summary")
        for pname in sorted(names):
            handler = registry._handlers.get(pname)
            module = getattr(handler, "__module__", "?") if handler else "?"
            doc = (
                (handler.__doc__ or "").strip().splitlines()[0][:60]
                if handler and handler.__doc__
                else "—"
            )
            t.add_row(
                pname, module.replace("redeploy.plugins.builtin.", "builtin/"), doc
            )
        console.print(t)
        console.print(
            f"\n[dim]User plugin dirs: ./redeploy_plugins/  ~/.redeploy/plugins/[/dim]"
        )

    elif subcommand == "info":
        if not name:
            console.print(
                "[red]✗ Provide plugin name: redeploy plugin info <name>[/red]"
            )
            sys.exit(1)
        handler = registry._handlers.get(name)
        if not handler:
            console.print(f"[red]✗ Plugin '{name}' not found.[/red]")
            console.print(f"  Available: {', '.join(sorted(registry.names()))}")
            sys.exit(1)
        console.print(
            f"\n[bold cyan]{name}[/bold cyan]  "
            f"[dim]{getattr(handler, '__module__', '?')}[/dim]"
        )
        # Print full docstring of the module
        import importlib

        mod = importlib.import_module(handler.__module__)
        doc = (mod.__doc__ or handler.__doc__ or "No documentation.").strip()
        console.print(f"\n{doc}")

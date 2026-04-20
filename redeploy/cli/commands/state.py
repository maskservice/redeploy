"""state command — Inspect or clear resume checkpoints."""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table


def _get_state_path(spec_file, host, state_file, console) -> Path:
    """Get state path from spec or explicit state file."""
    from ...apply.state import default_state_path
    from ..core import load_spec_or_exit

    if state_file:
        return Path(state_file)
    if not spec_file:
        console.print("[red]✗ provide SPEC or --state-file[/red]")
        sys.exit(2)
    spec = load_spec_or_exit(console, spec_file)
    target_host = host or spec.source.host or "local"
    return default_state_path(spec_file, target_host)


def _list_checkpoints(console) -> None:
    """List all checkpoints."""
    from ...apply.state import DEFAULT_STATE_DIR, ResumeState

    base = DEFAULT_STATE_DIR
    if not base.exists():
        console.print(f"[dim]no checkpoints under {base}/[/dim]")
        return
    files = sorted(base.glob("*.yaml"))
    if not files:
        console.print(f"[dim]no checkpoints under {base}/[/dim]")
        return
    t = Table(show_header=True, box=None, padding=(0, 2))
    t.add_column("File", style="bold")
    t.add_column("Spec")
    t.add_column("Host", style="cyan")
    t.add_column("Done")
    t.add_column("Failed", style="red")
    t.add_column("Updated", style="dim")
    for f in files:
        try:
            st = ResumeState.load(f)
            t.add_row(
                f.name,
                st.spec_path or "?",
                st.host,
                f"{st.completed_count}/{st.total_steps}",
                st.failed_step_id or "—",
                st.updated_at,
            )
        except Exception as e:
            t.add_row(f.name, "[red]parse error[/red]", "—", "—", "—", str(e)[:40])
    console.print(t)


def _show_checkpoint(console, path) -> None:
    """Show checkpoint details."""
    from ...apply.state import ResumeState

    st = ResumeState.load(path)
    console.print(f"[bold]checkpoint[/bold] {path}")
    console.print(f"  spec:        {st.spec_path}")
    console.print(f"  host:        {st.host}")
    console.print(
        f"  progress:    {st.completed_count}/{st.total_steps} "
        f"({st.remaining} pending)"
    )
    console.print(f"  started:     {st.started_at}")
    console.print(f"  updated:     {st.updated_at}")
    if st.failed_step_id:
        console.print(f"  [red]failed:      {st.failed_step_id}[/red]")
        if st.failed_error:
            console.print(f"  [red]error:       {st.failed_error[:200]}[/red]")
    if st.completed_step_ids:
        console.print(f"  done:        {', '.join(st.completed_step_ids)}")


@click.command("state")
@click.argument("action", type=click.Choice(["show", "clear", "ls"]), default="show")
@click.argument("spec_file", default=None, required=False, type=click.Path())
@click.option("--host", default=None, help="Override host (default: from spec)")
@click.option("--state-file", default=None, type=click.Path(), help="Explicit checkpoint path")
@click.pass_context
def state_cmd(ctx, action, spec_file, host, state_file):
    """Inspect or clear resume checkpoints.

    \b
    Examples:
        redeploy state show migration.yaml      # current checkpoint
        redeploy state clear migration.yaml     # delete checkpoint
        redeploy state ls                       # list all checkpoints in CWD
    """
    console = Console()

    if action == "ls":
        _list_checkpoints(console)
        return

    # show / clear need a path
    path = _get_state_path(spec_file, host, state_file, console)

    if not path.exists():
        console.print(f"[dim]no checkpoint at {path}[/dim]")
        return

    if action == "clear":
        path.unlink()
        console.print(f"[green]✓ removed {path}[/green]")
        return

    # show
    _show_checkpoint(console, path)

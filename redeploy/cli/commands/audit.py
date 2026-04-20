"""audit command — Show deploy audit log."""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table


@click.command()
@click.option(
    "-n", "--last", default=20, show_default=True,
    help="Number of most-recent entries to show"
)
@click.option("--host", default=None, help="Filter by host (substring match)")
@click.option("--app", default=None, help="Filter by app name")
@click.option("--failed", "only_failed", is_flag=True, help="Show only failed deployments")
@click.option("--ok", "only_ok", is_flag=True, help="Show only successful deployments")
@click.option("--log", default=None, type=click.Path(), help="Custom audit log path")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSONL")
@click.option(
    "--report", "show_report", default=None,
    help="Show full DeployReport for entry N (1-based)"
)
@click.option("--clear", "do_clear", is_flag=True, help="Truncate audit log (irreversible)")
def audit(last, host, app, only_failed, only_ok, log, as_json, show_report, do_clear):
    """Show deploy audit log from ~/.config/redeploy/audit.jsonl.

    \b
    Examples:
        redeploy audit
        redeploy audit --last 50 --failed
        redeploy audit --app myapp --host prod
        redeploy audit --report 1
        redeploy audit --clear
    """
    import json as _json
    from ...observe import DeployAuditLog, DeployReport

    console = Console()
    log_path = Path(log) if log else None
    audit_log = DeployAuditLog(path=log_path)

    if do_clear:
        if not audit_log.path.exists():
            console.print("[dim]Audit log is already empty.[/dim]")
            return
        click.confirm(f"Truncate {audit_log.path}?", abort=True)
        audit_log.clear()
        console.print(f"[green]✓[/green] Audit log cleared: {audit_log.path}")
        return

    ok_filter = None
    if only_failed:
        ok_filter = False
    elif only_ok:
        ok_filter = True

    entries = audit_log.filter(host=host, app=app, ok=ok_filter)
    entries = entries[-last:]

    if not entries:
        console.print("[dim]No audit entries found.[/dim]")
        console.print(f"  Log: {audit_log.path}")
        return

    if show_report:
        try:
            idx = int(show_report) - 1
            entry = entries[idx]
        except (ValueError, IndexError):
            console.print(
                f"[red]Entry {show_report} not found (1–{len(entries)} available)[/red]"
            )
            sys.exit(1)
        console.print(DeployReport(entry).text())
        return

    if as_json:
        for e in entries:
            print(_json.dumps(e.to_dict(), ensure_ascii=False))
        return

    t = Table(show_header=True, box=None, padding=(0, 2))
    t.add_column("#", style="dim", width=3)
    t.add_column("Time", style="dim")
    t.add_column("Host")
    t.add_column("App", style="bold")
    t.add_column("Strategy", style="cyan")
    t.add_column("Result")
    t.add_column("Steps", style="dim")
    t.add_column("Elapsed", style="dim")

    for i, e in enumerate(entries, 1):
        ts = e.ts[11:16] if len(e.ts) >= 16 else e.ts
        date = e.ts[:10] if len(e.ts) >= 10 else ""
        strategy = f"{e.from_strategy}→{e.to_strategy}"
        if e.ok:
            result = "[green]ok[/green]"
        else:
            result = "[red]FAIL[/red]"
        if e.dry_run:
            result += " [dim](dry)[/dim]"
        steps_str = f"{e.steps_ok}/{e.steps_total}"
        if e.steps_failed:
            steps_str += f" [red]✗{e.steps_failed}[/red]"
        elapsed = f"{e.elapsed_s:.1f}s"
        t.add_row(
            str(i),
            f"{date} {ts}",
            e.host,
            e.app,
            strategy,
            result,
            steps_str,
            elapsed,
        )

    console.print(t)
    console.print(
        f"\n  [dim]{len(entries)} entr{'y' if len(entries) == 1 else 'ies'}"
        f"  •  {audit_log.path}[/dim]"
    )
    console.print("  [dim]Tip: --report N  for full step breakdown[/dim]")

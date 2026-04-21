"""device-map command — Generate a full standardized device snapshot.

Probes a remote host and produces a DeviceMap in YAML/JSON format:
  - identity (host, tags, name)
  - hardware (DRM, DSI, backlight, I2C, config.txt overlays)
  - infra (runtime, services, ports, containers)
  - diagnostics (merged issues with fix suggestions)

The format is analogous to InfraState/source/target — persists to
~/.config/redeploy/device-maps/<device>.yaml and can be loaded later
for diff, audit or sharing.

Examples::

    redeploy device-map pi@192.168.188.109
    redeploy device-map pi@192.168.188.109 --save
    redeploy device-map pi@192.168.188.109 --save --out rpi5.yaml
    redeploy device-map pi@192.168.188.109 --format json
    redeploy device-map pi@192.168.188.109 --name "kiosk-rpi5" --tag kiosk --tag rpi5
    redeploy device-map --list
    redeploy device-map --diff rpi5.yaml rpi5-new.yaml
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import click
from rich import box
from rich.console import Console
from rich.table import Table


@click.command("device-map")
@click.argument("host", required=False, default=None)
@click.option("--name", default="", help="Human-friendly device label")
@click.option("--tag", "tags", multiple=True, help="Tag(s) to attach (repeatable)")
@click.option("--save", is_flag=True, help="Persist map to ~/.config/redeploy/device-maps/")
@click.option("--out", "out_path", default=None, type=click.Path(), help="Save to specific file")
@click.option("--format", "output_fmt", default="yaml",
              type=click.Choice(["yaml", "json"]), help="Output format (default: yaml)")
@click.option("--no-infra", is_flag=True, help="Skip infra probe (faster — hardware only)")
@click.option("--list", "list_saved", is_flag=True, help="List saved device maps")
@click.option("--show", "show_file", default=None, type=click.Path(exists=True),
              help="Load and display a saved device-map file")
@click.option("--diff", "diff_files", nargs=2, type=click.Path(exists=True),
              help="Diff two saved device-map files")
@click.option("--apply-config", "apply_config", default=None,
              type=click.Path(exists=True, dir_okay=False),
              help="Apply hardware/infra settings from YAML config file to the remote host")
@click.option(
    "--query", "query_expr",
    default=None,
    metavar="EXPR",
    help="Extract specific values using JMESPath query (e.g. 'hardware.drm_outputs[0].transform', 'host')",
)
@click.option("--ssh-key", default=None, type=click.Path(), help="SSH private key path")
def device_map_cmd(
    host, name, tags, save, out_path, output_fmt,
    no_infra, list_saved, show_file, diff_files, ssh_key, apply_config, query_expr,
):
    """Generate a full standardized device snapshot (hardware + infra + diagnostics).

    The DeviceMap is a portable, persisted YAML file that captures the complete
    state of a device — analogous to InfraState/source/target but richer.

    \b
    Examples:
        redeploy device-map pi@192.168.188.109
        redeploy device-map pi@192.168.188.109 --save --name "kiosk-lab"
        redeploy device-map --list
        redeploy device-map --show ~/.config/redeploy/device-maps/pi_at_192.168.188.109.yaml

    \b
    Config-file workflow (scan → edit → apply):
        redeploy device-map pi@192.168.188.109 > device-map.yaml
        # edit device-map.yaml: set hardware.drm_outputs[0].transform: '270'
        redeploy device-map pi@192.168.188.109 --apply-config device-map.yaml

    \b
    Query examples (JMESPath):
        redeploy device-map pi@192.168.188.109 --query "hardware.drm_outputs[0].transform"
        redeploy device-map pi@192.168.188.109 --query "host"
        redeploy device-map pi@192.168.188.109 --query "tags" --format json
    """
    from ...models import DeviceMap

    console = Console()

    # ── --list ────────────────────────────────────────────────────────────────
    if list_saved:
        _print_list(console)
        return

    # ── --show ────────────────────────────────────────────────────────────────
    if show_file:
        dm = DeviceMap.load(Path(show_file))
        click.echo(dm.to_yaml())
        return

    # ── --diff ────────────────────────────────────────────────────────────────
    if diff_files:
        a = DeviceMap.load(Path(diff_files[0]))
        b = DeviceMap.load(Path(diff_files[1]))
        _diff(console, a, b)
        return

    if not host:
        console.print("[red]✗ HOST required (or use --list / --show / --diff)[/red]")
        sys.exit(1)

    # ── --apply-config ─────────────────────────────────────────────────────────
    if apply_config:
        from ...config_apply import apply_config_file
        apply_config_file(apply_config, ssh_key=ssh_key, console=console)
        return

    # ── probe ─────────────────────────────────────────────────────────────────
    from ...detect.hardware import probe_hardware
    from ...detect.remote import RemoteProbe

    p = RemoteProbe(host, ssh_key=ssh_key) if ssh_key else RemoteProbe(host)

    hw_info = None
    infra_state = None

    with console.status(f"[cyan]Probing hardware on {host}…[/cyan]"):
        try:
            hw_info = probe_hardware(p)
        except ConnectionError as exc:
            console.print(f"[red]✗ {exc}[/red]")
            sys.exit(2)

    if not no_infra:
        with console.status(f"[cyan]Probing infra on {host}…[/cyan]"):
            try:
                from ...detect import Detector
                det = Detector(host)
                infra_state = det.run()
            except Exception as exc:
                console.print(f"[yellow]⚠ infra probe failed (continuing): {exc}[/yellow]")

    # Merge diagnostics into issues list
    issues: list[dict] = []
    if hw_info:
        for d in hw_info.diagnostics:
            issues.append({
                "source": "hardware",
                "component": d.component,
                "severity": d.severity,
                "message": d.message,
                "fix": d.fix,
            })
    if infra_state:
        for c in infra_state.conflicts:
            issues.append({
                "source": "infra",
                "component": "service",
                "severity": c.severity.value,
                "message": f"{c.type}: {c.description}",
                "fix": c.fix_hint,
            })

    dm = DeviceMap(
        id=host,
        host=host,
        name=name,
        tags=list(tags),
        scanned_at=datetime.now(timezone.utc),
        hardware=hw_info,
        infra=infra_state,
        issues=issues,
    )

    # ── --query: extract specific values with JMESPath ─────────────────────────
    if query_expr:
        _execute_query_device_map(console, dm, query_expr, output_fmt)
        return

    # ── output ────────────────────────────────────────────────────────────────
    if output_fmt == "json":
        import json as _json
        click.echo(_json.dumps(dm.model_dump(mode="json"), indent=2))
    else:
        click.echo(dm.to_yaml())

    # ── save ──────────────────────────────────────────────────────────────────
    if save or out_path:
        path = Path(out_path) if out_path else None
        saved_path = dm.save(path)
        console.print(f"\n[green]✓ saved:[/green] {saved_path}")

    if dm.has_errors:
        sys.exit(1)


def _execute_query_device_map(console, dm, query_expr, output_fmt):
    """Execute JMESPath query on DeviceMap model and output result."""
    import jmespath
    import json as _json

    data = dm.model_dump(mode="json")

    try:
        result = jmespath.search(query_expr, data)
    except jmespath.exceptions.JMESPathError as e:
        console.print(f"[red]✗ JMESPath error:[/red] {e}")
        sys.exit(1)

    if result is None:
        console.print("[dim]No match found for query[/dim]")
        return

    if output_fmt == "json":
        click.echo(_json.dumps(result, indent=2, default=str))
    else:
        import yaml
        click.echo(yaml.safe_dump(result, sort_keys=False, default_flow_style=False))


# ── rendering helpers ─────────────────────────────────────────────────────────


def _render(console: Console, dm: "DeviceMap", fmt: str) -> None:
    """Dispatch to the appropriate renderer for *fmt*."""
    from .device_map_renderers import render_json, render_rich, render_yaml

    if fmt == "yaml":
        render_yaml(dm)
    elif fmt == "json":
        render_json(dm)
    else:
        render_rich(console, dm)


def _print_list(console: Console) -> None:
    from ...models import DeviceMap

    maps = DeviceMap.list_saved()
    if not maps:
        console.print("[dim]No saved device maps. Run:[/dim]  redeploy device-map HOST --save")
        return

    t = Table(show_header=True, box=box.SIMPLE, padding=(0, 2))
    t.add_column("File", style="bold")
    t.add_column("Host", style="cyan")
    t.add_column("Board")
    t.add_column("Display")
    t.add_column("Issues")
    t.add_column("Scanned", style="dim")

    for p in maps:
        try:
            dm = DeviceMap.load(p)
            board = dm.hardware.board if dm.hardware else "?"
            disp = dm.display_summary
            errors = sum(1 for i in dm.issues if i.get("severity") in ("error", "critical"))
            warn = sum(1 for i in dm.issues if i.get("severity") == "warning")
            issues_str = (
                f"[red]{errors}E[/red] " if errors else ""
            ) + (f"[yellow]{warn}W[/yellow]" if warn else "") or "[green]OK[/green]"
            t.add_row(
                p.name,
                dm.host,
                board or "?",
                disp,
                issues_str,
                dm.scanned_at.strftime("%Y-%m-%d %H:%M"),
            )
        except Exception as exc:
            t.add_row(p.name, "[red]parse error[/red]", str(exc)[:40], "", "", "")

    console.print(t)


def _diff(console: Console, a: "DeviceMap", b: "DeviceMap") -> None:
    import yaml

    console.print(f"\n[bold]diff[/bold]  [cyan]{a.id}[/cyan] ({a.scanned_at.strftime('%m-%d %H:%M')})"
                  f"  →  [cyan]{b.id}[/cyan] ({b.scanned_at.strftime('%m-%d %H:%M')})\n")

    def _flat(obj, prefix="") -> dict:
        """Flatten a dict to dot-separated keys."""
        out = {}
        if isinstance(obj, dict):
            for k, v in obj.items():
                out.update(_flat(v, f"{prefix}.{k}" if prefix else k))
        elif isinstance(obj, list):
            out[prefix] = str(obj)
        else:
            out[prefix] = str(obj)
        return out

    fa = _flat(a.model_dump(mode="json"))
    fb = _flat(b.model_dump(mode="json"))

    all_keys = sorted(set(fa) | set(fb))
    changed = [(k, fa.get(k), fb.get(k)) for k in all_keys if fa.get(k) != fb.get(k)]

    # Filter noisy/timestamp keys
    skip = {"scanned_at", "id"}
    changed = [(k, oa, nb) for k, oa, nb in changed if not any(s in k for s in skip)]

    if not changed:
        console.print("[green]✓ No differences[/green]")
        return

    t = Table(show_header=True, box=box.SIMPLE, padding=(0, 1))
    t.add_column("Key")
    t.add_column(f"A: {a.id[:20]}", style="red")
    t.add_column(f"B: {b.id[:20]}", style="green")
    for k, oa, nb in changed[:50]:  # cap at 50 rows
        t.add_row(k, str(oa or "—")[:60], str(nb or "—")[:60])
    console.print(t)
    if len(changed) > 50:
        console.print(f"[dim]... and {len(changed) - 50} more differences[/dim]")

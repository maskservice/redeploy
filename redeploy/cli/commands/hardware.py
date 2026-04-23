"""hardware command — Probe and diagnose hardware on a remote host.

Detects DSI displays, DRM connectors, backlight, I2C buses,
GPIO, config.txt overlays and reports problems with fix suggestions.

Examples::

    redeploy hardware pi@192.168.188.109
    redeploy hardware pi@192.168.188.109 --format json
    redeploy hardware pi@192.168.188.109 --fix        # print all fix commands
    redeploy hardware pi@192.168.188.109 --apply-fix dsi  # run fix for component
"""
from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box


_SEVERITY_COLOR = {
    "info":     "green",
    "warning":  "yellow",
    "error":    "red",
    "critical": "bold red",
}

_SEVERITY_ICON = {
    "info":     "✓",
    "warning":  "⚠",
    "error":    "✗",
    "critical": "✗✗",
}


def _probe_hardware(host, ssh_key, console):
    """Probe hardware on remote host via op3 scanner.

    Delegates to :func:`redeploy.detect.hardware.probe_hardware`, which
    wraps op3's :class:`LinearScanner` (physical.display + os.kernel +
    os.config layers) and attaches diagnostics from the op3 rule engine.
    """
    from ...detect.hardware import probe_hardware
    from ...detect.remote import RemoteProbe

    p = RemoteProbe(host)
    if ssh_key:
        p.key = ssh_key

    with console.status(f"[cyan]Probing hardware on {host}…[/cyan]"):
        try:
            hw = probe_hardware(p)
        except ConnectionError as exc:
            console.print(f"[red]✗ {exc}[/red]")
            sys.exit(2)
        except Exception as exc:
            console.print(f"[red]✗ hardware probe failed: {exc}[/red]")
            raise

    return hw, p


def _format_output(hw, output_fmt):
    """Format output as yaml/json, return True if formatted."""
    if output_fmt == "yaml":
        import yaml
        click.echo(yaml.safe_dump(hw.model_dump(mode="json"), sort_keys=False))
        return True

    if output_fmt == "json":
        import json as _json
        click.echo(_json.dumps(hw.model_dump(mode="json"), indent=2))
        return True

    return False


def _print_drm_connectors(console, hw):
    """Print DRM connectors table."""
    if not hw.drm_outputs:
        return

    t = Table(title="DRM Connectors", show_header=True, box=box.SIMPLE, padding=(0, 1))
    t.add_column("Connector")
    t.add_column("Status")
    t.add_column("Enabled")
    t.add_column("Mode")
    t.add_column("Transform")
    for o in hw.drm_outputs:
        status_color = "green" if o.status == "connected" else "red"
        mode = o.modes[0] if o.modes else "—"
        t.add_row(
            o.connector,
            f"[{status_color}]{o.status}[/{status_color}]",
            o.enabled,
            mode,
            o.transform,
        )
    console.print(t)


def _print_backlights(console, hw):
    """Print backlights table."""
    if not hw.backlights:
        return

    t = Table(title="Backlight", show_header=True, box=box.SIMPLE, padding=(0, 1))
    t.add_column("Device")
    t.add_column("Brightness")
    t.add_column("Max")
    t.add_column("Power")
    t.add_column("Display")
    for b in hw.backlights:
        pw_color = "green" if b.bl_power == 0 else "red"
        br_color = "green" if b.brightness > 0 else "red"
        t.add_row(
            b.name,
            f"[{br_color}]{b.brightness}[/{br_color}]",
            str(b.max_brightness),
            f"[{pw_color}]{'ON' if b.bl_power == 0 else 'OFF'}[/{pw_color}]",
            b.display_name or "—",
        )
    console.print(t)


def _print_dsi_overlays(console, hw):
    """Print DSI overlays."""
    if hw.dsi_overlays:
        console.print(f"[dim]DSI overlays:[/dim]  {', '.join(hw.dsi_overlays)}")
    else:
        console.print("[red]DSI overlays: none found[/red]")


def _print_i2c_buses(console, hw):
    """Print I2C buses summary."""
    if not hw.i2c_buses:
        return

    bus_summary = ", ".join(
        f"i2c-{b.bus}" + (f" [{','.join(b.devices)}]" if b.devices else "")
        for b in hw.i2c_buses
    )
    console.print(f"[dim]I2C buses:[/dim]  {bus_summary}")


def _print_diagnostics(console, hw, show_fix):
    """Print diagnostics table and fix suggestions."""
    if not hw.diagnostics:
        console.print("[green]✓ No hardware issues detected[/green]")
        return

    t = Table(title="Diagnostics", show_header=True, box=box.SIMPLE, padding=(0, 1))
    t.add_column("", width=3)
    t.add_column("Component", style="bold")
    t.add_column("Message")

    for d in hw.diagnostics:
        color = _SEVERITY_COLOR.get(d.severity, "white")
        icon = _SEVERITY_ICON.get(d.severity, "?")
        t.add_row(
            f"[{color}]{icon}[/{color}]",
            f"[{color}]{d.component}[/{color}]",
            d.message,
        )
    console.print(t)

    # Fix hints
    fixable = [d for d in hw.diagnostics if d.fix]
    if fixable and show_fix:
        console.print()
        console.print("[bold]Fix suggestions:[/bold]")
        for d in fixable:
            color = _SEVERITY_COLOR.get(d.severity, "white")
            console.print(
                f"\n  [{color}][{d.component}][/{color}] {d.message}\n"
                + "\n".join(f"    [dim]{line}[/dim]" for line in (d.fix or "").splitlines())
            )
    elif fixable and not show_fix:
        console.print(
            f"\n[dim]  {len(fixable)} fix suggestion(s) available — rerun with --fix[/dim]"
        )


def _apply_transform(console, p, hw, transform):
    """Apply display transform via wlr-randr and persist in kanshi config."""
    dsi = next((o for o in hw.drm_outputs if "DSI" in o.name), None)
    if not dsi:
        console.print("[red]✗ No DSI output found on this host[/red]")
        sys.exit(1)

    from ...config_apply.handlers.display import apply_display_transform
    apply_display_transform(console, p, dsi.connector, transform)


def _execute_query(hw, query_expr, output_fmt):
    """Execute JMESPath query on hardware model and output result."""
    from ...cli.query import execute_query
    execute_query(hw, query_expr, output_fmt, echo=lambda msg: click.echo(msg, err=True))


def _apply_fix(console, p, hw, apply_fix_component, panel_id=None):
    """Apply fix for a specific component using fix plan generator."""
    from ...hardware.fixes import generate_fix_plan
    from ...hardware.panels import get

    # Get panel if specified
    panel = get(panel_id) if panel_id else None

    # Generate fix plan
    steps = generate_fix_plan(hw, apply_fix_component, panel)
    if not steps:
        console.print(f"[yellow]No fix available for component: {apply_fix_component}[/yellow]")
        if panel_id:
            console.print(f"[dim]Panel: {panel_id}[/dim]")
        sys.exit(1)

    console.print(f"[bold]Fix plan for {apply_fix_component}[/bold]")
    if panel:
        console.print(f"  Panel: {panel.name}")

    # Execute steps via handlers directly
    from ...apply.handlers import run_ssh, run_ensure_config_line, run_raspi_config, run_wait
    from ...models import StepAction

    _handler_map = {
        StepAction.SSH_CMD: lambda s: run_ssh(s, p),
        StepAction.ENSURE_CONFIG_LINE: lambda s: run_ensure_config_line(s, p),
        StepAction.RASPI_CONFIG: lambda s: run_raspi_config(s, p),
        StepAction.WAIT: lambda s: run_wait(s),
    }

    for step in steps:
        console.print(f"[cyan]→ {step.description}[/cyan]")
        handler = _handler_map.get(step.action)
        if handler is None:
            console.print(f"[yellow]  ? skip (no handler for {step.action})[/yellow]")
            continue
        try:
            handler(step)
            console.print(f"[green]  ✓ done[/green]")
        except Exception as exc:
            console.print(f"[red]  ✗ failed: {exc}[/red]")
            sys.exit(1)


@click.command()
@click.argument("host", required=False, default=None)
@click.option(
    "--format", "output_fmt", default="yaml",
    type=click.Choice(["yaml", "json"]),
    help="Output format (default: yaml)"
)
@click.option(
    "--fix", "show_fix",
    is_flag=True,
    help="Print fix commands for all issues found",
)
@click.option(
    "--apply-fix", "apply_fix_component",
    default=None,
    metavar="COMPONENT",
    help=(
        "Run the fix for a specific component via SSH "
        "(e.g. 'backlight', 'overlay'). Requires sudo on target."
    ),
)
@click.option(
    "--panel", "panel_id",
    default=None,
    metavar="PANEL_ID",
    help="Specify panel ID explicitly (use --list-panels to see available)",
)
@click.option(
    "--list-panels",
    is_flag=True,
    help="List available panel definitions and exit",
)
@click.option(
    "--set-transform", "set_transform",
    default=None,
    metavar="TRANSFORM",
    type=click.Choice(["normal", "90", "180", "270", "flipped", "flipped-90", "flipped-180", "flipped-270"]),
    help="Set display rotation for DSI output (e.g. 270 = -90°). Applies immediately via wlr-randr and saves to kanshi config.",
)
@click.option(
    "--apply-config", "apply_config",
    default=None,
    metavar="FILE",
    type=click.Path(exists=True, dir_okay=False),
    help="Apply display settings (transform, backlight) from a YAML/JSON hardware config file to the remote host.",
)
@click.option(
    "--query", "query_expr",
    default=None,
    metavar="EXPR",
    help="Extract specific values using JMESPath query (e.g. 'drm_outputs[0].transform', 'backlights[?name==`11-0045`].brightness')",
)
@click.option("--ssh-key", default=None, type=click.Path(), help="SSH private key path")
def hardware(host, output_fmt, show_fix, apply_fix_component, panel_id, list_panels, ssh_key, set_transform, apply_config, query_expr):
    """Probe and diagnose hardware on a remote host.

    Checks DSI display, DRM connectors, backlight controller, I2C buses,
    config.txt overlays and Wayland compositor — then reports issues with
    actionable fix suggestions.

    \b
    Examples:
        redeploy hardware pi@192.168.188.109
        redeploy hardware pi@192.168.188.109 --fix
        redeploy hardware --list-panels

    \b
    Config-file workflow (scan → edit → apply):
        redeploy hardware pi@192.168.188.109 > hardware.yaml
        # edit hardware.yaml: set drm_outputs[0].transform: '270'
        redeploy hardware pi@192.168.188.109 --apply-config hardware.yaml

    \b
    Query examples (JMESPath):
        redeploy hardware pi@192.168.188.109 --query "drm_outputs[0].transform"
        redeploy hardware pi@192.168.188.109 --query "backlights[?name==`11-0045`].brightness"
        redeploy hardware pi@192.168.188.109 --query "kernel" --format json
    """
    console = Console()

    # Handle --list-panels
    if list_panels:
        from ...hardware.panels import all_panels
        panels = all_panels()
        t = Table(show_header=True, box=box.ROUNDED)
        t.add_column("ID", style="cyan")
        t.add_column("Name", style="bold")
        t.add_column("Vendor", style="dim")
        t.add_column("Resolution", style="dim")
        t.add_column("Overlay", style="dim")
        for p in panels:
            res = f"{p.resolution[0]}×{p.resolution[1]}" if p.resolution else "—"
            t.add_row(p.id, p.name, p.vendor, res, p.overlay)
        console.print(t)
        return

    if not host:
        raise click.UsageError("HOST argument is required unless --list-panels is used.")

    hw, p = _probe_hardware(host, ssh_key, console)

    # --apply-config: load YAML/JSON file and push settings to device
    if apply_config is not None:
        from ...config_apply import apply_config_file
        apply_config_file(apply_config, host=host, ssh_key=ssh_key, console=console)
        return

    # --set-transform: apply rotation immediately and update kanshi config
    if set_transform is not None:
        _apply_transform(console, p, hw, set_transform)
        return

    # --query: extract specific values with JMESPath
    if query_expr is not None:
        _execute_query(hw, query_expr, output_fmt)
        return

    if output_fmt == "json":
        import json as _json
        click.echo(_json.dumps(hw.model_dump(mode="json"), indent=2))
    else:
        import yaml
        click.echo(yaml.safe_dump(hw.model_dump(mode="json"), sort_keys=False))
    return

    console.print()
    console.print(Panel(
        f"[bold]hardware probe[/bold]  [cyan]{host}[/cyan]\n"
        f"Board: [white]{hw.board or 'unknown'}[/white]  "
        f"Kernel: [white]{hw.kernel or 'unknown'}[/white]",
        box=box.ROUNDED,
        expand=False,
    ))

    _print_drm_connectors(console, hw)
    _print_backlights(console, hw)
    _print_dsi_overlays(console, hw)
    _print_i2c_buses(console, hw)

    console.print()

    _print_diagnostics(console, hw, show_fix)

    if apply_fix_component:
        _apply_fix(console, p, hw, apply_fix_component, panel_id)

    # Exit code based on errors
    errors = hw.errors
    if errors:
        sys.exit(1)

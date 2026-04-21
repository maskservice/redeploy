"""Device-map renderers — one function per output format.

Extracted from :func:`redeploy.cli.commands.device_map._render` to keep
each renderer below CC 8 and testable in isolation.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

if TYPE_CHECKING:
    from ...models import DeviceMap


def render_yaml(dm: "DeviceMap") -> None:
    """Emit *dm* as YAML to stdout."""
    click.echo(dm.to_yaml())


def render_json(dm: "DeviceMap") -> None:
    """Emit *dm* as indented JSON to stdout."""
    click.echo(json.dumps(dm.model_dump(mode="json"), indent=2))


_SEV_COLOR = {"info": "green", "warning": "yellow", "error": "red", "critical": "bold red"}
_SEV_ICON = {"info": "✓", "warning": "⚠", "error": "✗", "critical": "✗✗"}


def _build_header_panel(dm: "DeviceMap") -> Panel:
    """Rich Panel with host, name, tags and scan timestamp."""
    tags_str = " ".join(f"[dim cyan]{t}[/dim cyan]" for t in dm.tags) or "[dim]-[/dim]"
    return Panel(
        f"[bold]device-map[/bold]  [cyan]{dm.host}[/cyan]\n"
        f"Name: [white]{dm.name or '—'}[/white]   "
        f"Tags: {tags_str}   "
        f"Scanned: [dim]{dm.scanned_at.strftime('%Y-%m-%d %H:%M UTC')}[/dim]",
        box=box.ROUNDED,
        expand=False,
    )


def _build_drm_table(dm: "DeviceMap") -> Table | None:
    """Table of DRM outputs + backlight info."""
    hw = dm.hardware
    if not hw or not hw.drm_outputs:
        return None
    t = Table(title="Display (DRM)", show_header=True, box=box.SIMPLE, padding=(0, 1))
    t.add_column("Connector")
    t.add_column("Status")
    t.add_column("Mode")
    t.add_column("Transform")
    t.add_column("Backlight")
    for o in hw.drm_outputs:
        sc = "green" if o.status == "connected" else "dim"
        bl = next((b for b in hw.backlights if b.display_name == o.connector), None)
        bl_str = f"{bl.brightness}/{bl.max_brightness}" if bl else "—"
        t.add_row(
            o.connector,
            f"[{sc}]{o.status}[/{sc}]",
            o.modes[0] if o.modes else "—",
            o.transform,
            bl_str,
        )
    return t


def _build_services_table(dm: "DeviceMap") -> Table | None:
    """Table of running services (podman + systemd)."""
    infra = dm.infra
    if not infra:
        return None
    podman_svcs = infra.services.get("podman", [])
    systemd_svcs = infra.services.get("systemd", [])
    all_svcs = podman_svcs + systemd_svcs
    if not all_svcs:
        return None
    t = Table(title="Services", show_header=True, box=box.SIMPLE, padding=(0, 1))
    t.add_column("Name")
    t.add_column("Status")
    t.add_column("Type")
    for s in all_svcs:
        sc = "green" if "running" in s.status.lower() or "active" in s.status.lower() else "red"
        kind = "podman" if s in podman_svcs else "systemd"
        t.add_row(s.name, f"[{sc}]{s.status}[/{sc}]", kind)
    return t


def _build_issues_table(dm: "DeviceMap") -> Table | None:
    """Table of diagnostic issues."""
    if not dm.issues:
        return None
    t = Table(title="Issues", show_header=True, box=box.SIMPLE, padding=(0, 1))
    t.add_column("", width=3)
    t.add_column("Source", style="dim")
    t.add_column("Component")
    t.add_column("Message")
    for issue in dm.issues:
        sev = issue.get("severity", "info")
        color = _SEV_COLOR.get(sev, "white")
        icon = _SEV_ICON.get(sev, "?")
        t.add_row(
            f"[{color}]{icon}[/{color}]",
            issue.get("source", ""),
            f"[{color}]{issue.get('component', '')}[/{color}]",
            issue.get("message", ""),
        )
    return t


def render_rich(console: Console, dm: "DeviceMap") -> None:
    """Full rich console report with hardware, infra and issues tables."""
    console.print()
    console.print(_build_header_panel(dm))

    # Hardware section
    hw = dm.hardware
    if hw:
        console.print(f"\n[bold]Board[/bold]  {hw.board or '?'}   Kernel: {hw.kernel or '?'}")

        drm_table = _build_drm_table(dm)
        if drm_table:
            console.print(drm_table)

        if hw.dsi_overlays:
            console.print(f"[dim]Overlays:[/dim]  {', '.join(hw.dsi_overlays)}")
        if hw.i2c_buses:
            buses = ", ".join(
                f"i2c-{b.bus}" + (f"[{','.join(b.devices)}]" if b.devices else "")
                for b in hw.i2c_buses
            )
            console.print(f"[dim]I2C:[/dim]  {buses}")

    # Infra section
    infra = dm.infra
    if infra:
        rt = infra.runtime
        runtimes = [
            f"podman {rt.podman}" if rt.podman else None,
            f"docker {rt.docker}" if rt.docker else None,
            f"k3s {rt.k3s}" if rt.k3s else None,
        ]
        rt_str = "  ".join(r for r in runtimes if r) or "—"
        console.print(
            f"\n[bold]Infra[/bold]  strategy=[cyan]{infra.detected_strategy}[/cyan]"
            f"  version={infra.current_version or '?'}  {rt_str}"
        )

        svc_table = _build_services_table(dm)
        if svc_table:
            console.print(svc_table)

    # Issues
    console.print()
    issues_table = _build_issues_table(dm)
    if issues_table:
        console.print(issues_table)
        fixes = [i for i in dm.issues if i.get("fix")]
        if fixes:
            console.print(
                f"[dim]  {len(fixes)} fix suggestion(s) — rerun with:[/dim]  "
                f"[cyan]redeploy hardware {dm.host} --fix[/cyan]"
            )
    else:
        console.print("[green]✓ No issues detected[/green]")

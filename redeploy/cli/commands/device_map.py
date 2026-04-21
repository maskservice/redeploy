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
from rich.panel import Panel
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
        _apply_config_from_file(console, apply_config, ssh_key)
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


def _apply_config_from_file(console, config_path, ssh_key):
    """Apply hardware/infra settings from YAML/JSON config file to the remote host.

    Reads DeviceMap YAML/JSON and applies:
    - Display transforms via wlr-randr + kanshi
    - Backlight settings
    - Other configurable hardware parameters
    """
    import yaml
    import json as _json

    from ...detect.remote import RemoteProbe

    with open(config_path) as f:
        raw = f.read()

    try:
        cfg = yaml.safe_load(raw)
    except Exception:
        cfg = _json.loads(raw)

    # Extract host from config or prompt
    host = cfg.get("host")
    if not host:
        console.print("[red]✗ No 'host' field in config file[/red]")
        sys.exit(1)

    console.print(f"[cyan]→ Applying config from {config_path} to {host}[/cyan]")

    # Connect to remote
    p = RemoteProbe(host, ssh_key=ssh_key)

    applied = 0

    # ── display transforms ────────────────────────────────────────────────────
    hardware = cfg.get("hardware", {})
    for output in hardware.get("drm_outputs", []):
        connector = output.get("connector", "")
        transform = output.get("transform", "normal")
        if not connector or not ("DSI" in connector or "HDMI" in connector):
            continue

        if transform == "normal":
            console.print(f"[dim]  skip {connector}: transform=normal (default)[/dim]")
            continue

        console.print(f"[cyan]→ {connector}: transform={transform}[/cyan]")

        # Apply via wlr-randr
        wlr_cmd = (
            f"WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/$(id -u) "
            f"wlr-randr --output {connector} --transform {transform} 2>&1"
        )
        r = p.run(wlr_cmd)
        if r.ok:
            console.print(f"[green]  ✓ wlr-randr applied[/green]")
            applied += 1
        else:
            console.print(f"[yellow]  ⚠ wlr-randr: {r.out.strip() or 'no output'}[/yellow]")

    # ── persist DSI transforms in kanshi ─────────────────────────────────────────
    dsi_outputs = [
        o for o in hardware.get("drm_outputs", [])
        if "DSI" in o.get("connector", "")
    ]
    if dsi_outputs:
        _update_kanshi_from_cfg(console, p, dsi_outputs)

    # ── backlight ─────────────────────────────────────────────────────────────
    for bl in hardware.get("backlights", []):
        name = bl.get("name", "")
        brightness = bl.get("brightness")
        bl_power = bl.get("bl_power")
        if not name:
            continue

        if brightness is not None:
            r = p.run(f"echo {brightness} | sudo tee /sys/class/backlight/{name}/brightness > /dev/null")
            if r.ok:
                console.print(f"[green]  ✓ backlight {name}: brightness={brightness}[/green]")
                applied += 1

        if bl_power is not None:
            r = p.run(f"echo {bl_power} | sudo tee /sys/class/backlight/{name}/bl_power > /dev/null")
            if r.ok:
                console.print(f"[green]  ✓ backlight {name}: bl_power={bl_power}[/green]")
                applied += 1

    if applied == 0:
        console.print("[yellow]Nothing to apply — no relevant settings found in config[/yellow]")
    else:
        console.print(f"\n[bold green]✓ Config applied from {config_path}[/bold green]")


def _update_kanshi_from_cfg(console, p, dsi_outputs: list):
    """Rebuild kanshi profile from drm_outputs list and write to ~/.config/kanshi/config."""
    import re as _re

    kanshi_cfg_path = "~/.config/kanshi/config"
    read_r = p.run(f"cat {kanshi_cfg_path} 2>/dev/null")
    current = read_r.out if read_r.ok else ""

    for output in dsi_outputs:
        connector = output.get("connector", "")
        transform = output.get("transform", "normal")

        output_line_pat = _re.compile(
            rf'(\s*output\s+{_re.escape(connector)}\s+enable)(\s+transform\s+\S+)?'
        )
        if _re.search(output_line_pat, current):
            if transform == "normal":
                current = _re.sub(output_line_pat, r'\1', current)
            else:
                current = _re.sub(output_line_pat, rf'\1 transform {transform}', current)
        elif current.strip():
            current = _re.sub(
                rf'(\s*output\s+{_re.escape(connector)}\b)',
                rf'\1 transform {transform}' if transform != "normal" else r'\1',
                current,
            )
        else:
            current = (
                f"profile waveshare-only {{\n"
                f"    output {connector} enable"
                + (f" transform {transform}" if transform != "normal" else "")
                + "\n"
                + "    output HDMI-A-2 disable\n"
                + "}\n"
            )

    escaped = current.replace("'", "'\\''")
    write_r = p.run(f"mkdir -p ~/.config/kanshi && printf '%s' '{escaped}' > {kanshi_cfg_path}")
    if write_r.ok:
        console.print(f"[green]  ✓ kanshi config updated ({kanshi_cfg_path})[/green]")
    p.run("pkill -SIGUSR1 kanshi 2>/dev/null || true")


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


_SEV_COLOR = {"info": "green", "warning": "yellow", "error": "red", "critical": "bold red"}
_SEV_ICON = {"info": "✓", "warning": "⚠", "error": "✗", "critical": "✗✗"}


def _render(console: Console, dm: "DeviceMap", fmt: str) -> None:
    from ...models import DeviceMap

    if fmt == "yaml":
        click.echo(dm.to_yaml())
        return
    if fmt == "json":
        import json as _json
        click.echo(_json.dumps(dm.model_dump(mode="json"), indent=2))
        return

    # Rich
    console.print()
    tags_str = " ".join(f"[dim cyan]{t}[/dim cyan]" for t in dm.tags) or "[dim]-[/dim]"
    console.print(Panel(
        f"[bold]device-map[/bold]  [cyan]{dm.host}[/cyan]\n"
        f"Name: [white]{dm.name or '—'}[/white]   "
        f"Tags: {tags_str}   "
        f"Scanned: [dim]{dm.scanned_at.strftime('%Y-%m-%d %H:%M UTC')}[/dim]",
        box=box.ROUNDED,
        expand=False,
    ))

    # Hardware section
    hw = dm.hardware
    if hw:
        console.print(f"\n[bold]Board[/bold]  {hw.board or '?'}   Kernel: {hw.kernel or '?'}")

        if hw.drm_outputs:
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
            console.print(t)

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
        console.print(f"\n[bold]Infra[/bold]  strategy=[cyan]{infra.detected_strategy.value}[/cyan]"
                      f"  version={infra.current_version or '?'}  {rt_str}")

        # Running services
        podman_svcs = infra.services.get("podman", [])
        systemd_svcs = infra.services.get("systemd", [])
        all_svcs = podman_svcs + systemd_svcs
        if all_svcs:
            t = Table(title="Services", show_header=True, box=box.SIMPLE, padding=(0, 1))
            t.add_column("Name")
            t.add_column("Status")
            t.add_column("Type")
            for s in all_svcs:
                sc = "green" if "running" in s.status.lower() or "active" in s.status.lower() else "red"
                kind = "podman" if s in podman_svcs else "systemd"
                t.add_row(s.name, f"[{sc}]{s.status}[/{sc}]", kind)
            console.print(t)

    # Issues
    console.print()
    if not dm.issues:
        console.print("[green]✓ No issues detected[/green]")
    else:
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
        console.print(t)

        fixes = [i for i in dm.issues if i.get("fix")]
        if fixes:
            console.print(f"[dim]  {len(fixes)} fix suggestion(s) — rerun with:[/dim]  "
                          f"[cyan]redeploy hardware {dm.host} --fix[/cyan]")


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

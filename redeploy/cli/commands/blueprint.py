"""blueprint command — extract, generate and apply DeviceBlueprints.

A DeviceBlueprint is a portable, self-contained deployment recipe derived
from one or more definition sources:

  • Running device snapshot (DeviceMap / live SSH probe)
  • docker-compose YAML files
  • migration.yaml
  • markpact markdown files

From a blueprint you can generate:

  • **twin**    — docker-compose for a local digital twin (cross-platform)
  • **deploy**  — migration.yaml targeting a new physical device

Sub-commands::

    redeploy blueprint capture HOST [--save] [--from-compose FILE ...] [--from-migration FILE]
    redeploy blueprint twin   BLUEPRINT [--out FILE] [--platform linux/amd64] [--port-offset N]
    redeploy blueprint deploy BLUEPRINT TARGET_HOST [--out FILE] [--no-transfer]
    redeploy blueprint show   BLUEPRINT
    redeploy blueprint list
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


@click.group("blueprint")
def blueprint_cmd():
    """Extract, generate and apply DeviceBlueprints (portable deploy recipes)."""


# ── capture ───────────────────────────────────────────────────────────────────

@blueprint_cmd.command("capture")
@click.argument("host")
@click.option("--name", default="", help="Blueprint name (default: derived from host)")
@click.option("--from-compose", "compose_files", multiple=True, type=click.Path(exists=True),
              help="Local docker-compose file(s) to include")
@click.option("--from-migration", "migration_file", default=None, type=click.Path(exists=True),
              help="Local migration.yaml to extract version/strategy from")
@click.option("--from-device-map", "device_map_file", default=None, type=click.Path(exists=True),
              help="Previously saved device-map YAML (skips live hardware probe)")
@click.option("--live/--no-live", default=True, help="Probe host for live InfraState (default: yes)")
@click.option("--save", is_flag=True, help="Save to ~/.config/redeploy/blueprints/")
@click.option("--out", "out_path", default=None, type=click.Path(),
              help="Save to specific file instead")
@click.option("--format", "fmt", default="yaml", type=click.Choice(["yaml", "json"]))
@click.option("--tag", "tags", multiple=True)
def capture(host, name, compose_files, migration_file, device_map_file,
            live, save, out_path, fmt, tags):
    """Probe HOST and extract a DeviceBlueprint from all available sources."""
    from ...blueprint import extract_blueprint
    from ...models import DeviceBlueprint, DeviceMap

    console = Console()

    _name = name or host.split("@")[-1].replace(".", "-")

    device_map = None
    if device_map_file:
        device_map = DeviceMap.load(Path(device_map_file))
    else:
        # Try loading a previously saved map
        device_map = DeviceMap.load_for(host)

    with console.status(f"[cyan]Extracting blueprint from {host}…[/cyan]"):
        bp = extract_blueprint(
            name=_name,
            device_map=device_map,
            compose_files=[Path(f) for f in compose_files],
            migration_file=Path(migration_file) if migration_file else None,
            tags=list(tags),
            detect_live=live,
            host=host,
        )

    if fmt == "json":
        import json as _json
        click.echo(_json.dumps(bp.model_dump(mode="json"), indent=2))
    else:
        click.echo(bp.to_yaml())

    if save or out_path:
        path = Path(out_path) if out_path else None
        saved = bp.save(path)
        console.print(f"\n[green]✓ saved:[/green] {saved}")


def _apply_blueprint_config(bp, config_path):
    """Apply blueprint settings from YAML config file to the remote host.

    Reads blueprint YAML/JSON and applies hardware settings (transforms, backlight, etc.).
    """
    import yaml
    import json as _json

    from ...remote import Remote

    with open(config_path) as f:
        raw = f.read()

    try:
        cfg = yaml.safe_load(raw)
    except Exception:
        cfg = _json.loads(raw)

    host = cfg.get("host") or getattr(bp, "host", None)
    if not host:
        print("[red]✗ No 'host' field in config file[/red]")
        return

    print(f"[cyan]→ Applying blueprint config from {config_path} to {host}[/cyan]")

    p = Remote(host)

    # Apply hardware settings (reuse logic from device-map)
    hardware = cfg.get("hardware", {})
    applied = 0

    for output in hardware.get("drm_outputs", []):
        connector = output.get("connector", "")
        transform = output.get("transform", "normal")
        if not connector or not ("DSI" in connector or "HDMI" in connector):
            continue

        if transform != "normal":
            wlr_cmd = (
                f"WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/$(id -u) "
                f"wlr-randr --output {connector} --transform {transform} 2>&1"
            )
            r = p.run(wlr_cmd)
            if r.ok:
                print(f"[green]  ✓ {connector}: transform={transform}[/green]")
                applied += 1

    for bl in hardware.get("backlights", []):
        name = bl.get("name", "")
        brightness = bl.get("brightness")
        if name and brightness is not None:
            r = p.run(f"echo {brightness} | sudo tee /sys/class/backlight/{name}/brightness > /dev/null")
            if r.ok:
                print(f"[green]  ✓ backlight {name}: brightness={brightness}[/green]")
                applied += 1

    if applied > 0:
        print(f"[bold green]✓ Blueprint config applied from {config_path}[/bold green]")
    else:
        print("[yellow]Nothing to apply[/yellow]")


# ── twin ──────────────────────────────────────────────────────────────────────

@blueprint_cmd.command("twin")
@click.argument("blueprint_file", type=click.Path(exists=True))
@click.option("--out", "out_path", default="docker-compose.twin.yml",
              help="Output compose file (default: docker-compose.twin.yml)")
@click.option("--platform", default="linux/amd64",
              help="Target platform for the twin (default: linux/amd64)")
@click.option("--port-offset", default=0, type=int,
              help="Add N to all host ports to avoid collisions")
@click.option("--no-mock-display", is_flag=True,
              help="Skip injecting a headless display stub")
@click.option("--print/--no-print", "print_output", default=True,
              help="Print compose YAML to stdout")
def twin(blueprint_file, out_path, platform, port_offset, no_mock_display, print_output):
    """Generate a docker-compose.twin.yml from BLUEPRINT_FILE for local testing."""
    from ...blueprint.generators.docker_compose import generate_twin
    from ...models import DeviceBlueprint

    console = Console()
    bp = DeviceBlueprint.load(Path(blueprint_file))

    with console.status("[cyan]Generating digital twin compose…[/cyan]"):
        compose_yaml = generate_twin(
            bp,
            local_platform=platform,
            port_offset=port_offset,
            add_mock_display=not no_mock_display,
        )

    out = Path(out_path)
    out.write_text(compose_yaml)
    console.print(f"[green]✓ written:[/green] {out}")

    if print_output:
        click.echo(compose_yaml)


# ── deploy ────────────────────────────────────────────────────────────────────

@blueprint_cmd.command("deploy")
@click.argument("blueprint_file", type=click.Path(exists=True))
@click.argument("target_host")
@click.option("--out", "out_path", default="migration.gen.yaml",
              help="Output migration file (default: migration.gen.yaml)")
@click.option("--remote-dir", default="/home/pi/apps", show_default=True)
@click.option("--no-transfer", is_flag=True,
              help="Skip image transfer steps (assume images already on target)")
@click.option("--strategy", default=None,
              help="Override deploy strategy (podman_quadlet | docker_compose)")
@click.option("--run", "run_migration", is_flag=True,
              help="Run the generated migration immediately via redeploy run")
@click.option("--print/--no-print", "print_output", default=True)
def deploy(blueprint_file, target_host, out_path, remote_dir, no_transfer,
           strategy, run_migration, print_output):
    """Generate (and optionally run) a migration.yaml for TARGET_HOST from BLUEPRINT_FILE."""
    from ...blueprint.generators.migration import generate_migration
    from ...models import DeviceBlueprint

    console = Console()
    bp = DeviceBlueprint.load(Path(blueprint_file))

    with console.status(f"[cyan]Generating migration for {target_host}…[/cyan]"):
        migration_yaml = generate_migration(
            bp,
            target_host=target_host,
            strategy=strategy,
            remote_dir=remote_dir,
            skip_image_transfer=no_transfer,
        )

    out = Path(out_path)
    out.write_text(migration_yaml)
    console.print(f"[green]✓ written:[/green] {out}")

    if print_output:
        click.echo(migration_yaml)

    if run_migration:
        import subprocess
        console.print(f"\n[cyan]Running migration:[/cyan] redeploy run {out}")
        result = subprocess.run(["redeploy", "run", str(out), "--progress-yaml"])
        sys.exit(result.returncode)


# ── show ──────────────────────────────────────────────────────────────────────

@blueprint_cmd.command("show")
@click.argument("blueprint_file", type=click.Path(exists=True))
@click.option("--format", "fmt", default="yaml", type=click.Choice(["yaml", "json"]))
@click.option("--apply-config", "apply_config", default=None,
              type=click.Path(exists=True, dir_okay=False),
              help="Apply blueprint settings from YAML config file to the remote host")
def show(blueprint_file, fmt, apply_config):
    """Display a saved DeviceBlueprint.

    \b
    Config-file workflow (scan → edit → apply):
        redeploy blueprint capture pi@192.168.188.109 > blueprint.yaml
        # edit blueprint.yaml: set hardware.drm_outputs[0].transform: '270'
        redeploy blueprint show blueprint.yaml --apply-config blueprint.yaml
    """
    from ...models import DeviceBlueprint

    bp = DeviceBlueprint.load(Path(blueprint_file))
    if fmt == "json":
        import json as _json
        click.echo(_json.dumps(bp.model_dump(mode="json"), indent=2))
    else:
        click.echo(bp.to_yaml())

    if apply_config:
        _apply_blueprint_config(bp, apply_config)


# ── list ──────────────────────────────────────────────────────────────────────

@blueprint_cmd.command("list")
def list_blueprints():
    """List all saved DeviceBlueprints."""
    from ...models import DeviceBlueprint

    console = Console()
    paths = DeviceBlueprint.list_saved()
    if not paths:
        console.print("[dim]No saved blueprints. Run:[/dim]  redeploy blueprint capture HOST --save")
        return

    t = Table(show_header=True, box=box.SIMPLE, padding=(0, 2))
    t.add_column("File", style="bold")
    t.add_column("Name", style="cyan")
    t.add_column("Version")
    t.add_column("Services", justify="right")
    t.add_column("Strategy")
    t.add_column("Platform")
    t.add_column("Created", style="dim")

    for p in paths:
        try:
            bp = DeviceBlueprint.load(p)
            t.add_row(
                p.name,
                bp.name,
                bp.version,
                str(len(bp.services)),
                bp.deploy_strategy,
                bp.hardware.arch or "?",
                bp.created_at.strftime("%Y-%m-%d %H:%M"),
            )
        except Exception as exc:
            t.add_row(p.name, "[red]parse error[/red]", str(exc)[:40], "", "", "", "")

    console.print(t)


# ── rendering ─────────────────────────────────────────────────────────────────

def _print_blueprint(console: Console, bp, fmt: str) -> None:
    import json as _json

    if fmt == "yaml":
        click.echo(bp.to_yaml())
        return
    if fmt == "json":
        click.echo(_json.dumps(bp.model_dump(mode="json"), indent=2))
        return

    # Rich
    console.print()
    tags_str = " ".join(f"[dim cyan]{t}[/dim cyan]" for t in bp.tags) or "[dim]—[/dim]"
    console.print(Panel(
        f"[bold]{bp.name}[/bold]  v[cyan]{bp.version}[/cyan]  "
        f"strategy=[yellow]{bp.deploy_strategy}[/yellow]  {tags_str}\n"
        f"[dim]{bp.description or 'No description'}[/dim]",
        box=box.ROUNDED, expand=False, title="DeviceBlueprint",
    ))

    # Hardware requirements
    hw = bp.hardware
    hw_parts = [f"arch=[cyan]{hw.arch or '?'}[/cyan]"]
    if hw.display_type:
        hw_parts.append(f"display={hw.display_type}/{hw.display_resolution or '?'}")
    if hw.i2c_required:
        hw_parts.append("i2c=required")
    if hw.features:
        hw_parts.append(f"features={','.join(hw.features)}")
    console.print(f"\n[bold]Hardware[/bold]  " + "  ".join(hw_parts))

    # Services table
    if bp.services:
        t = Table(title="Services", show_header=True, box=box.SIMPLE, padding=(0, 1))
        t.add_column("Name", style="bold")
        t.add_column("Image")
        t.add_column("Ports")
        t.add_column("Volumes", justify="right")
        t.add_column("Env vars", justify="right")
        t.add_column("Source", style="dim")
        for svc in bp.services:
            ports_str = ",".join(f"{p.host}→{p.container}" for p in svc.ports) or "—"
            t.add_row(
                svc.name,
                svc.image or "[dim]unknown[/dim]",
                ports_str,
                str(len(svc.volumes)),
                str(len(svc.env)),
                (svc.source_ref or "")[:30],
            )
        console.print(t)
    else:
        console.print("[dim]No services captured yet.[/dim]")

    # Source
    src = bp.source
    console.print(
        f"\n[dim]Captured from:[/dim] {src.device_id or '—'}  "
        f"[dim]at[/dim] {src.extracted_at.strftime('%Y-%m-%d %H:%M')}"
    )
    if src.compose_files:
        console.print(f"[dim]Compose files:[/dim] {', '.join(src.compose_files)}")
    if src.migration_file:
        console.print(f"[dim]Migration:[/dim]    {src.migration_file}")
    console.print()

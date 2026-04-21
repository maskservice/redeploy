"""devices, scan, device-add, device-rm commands — Device management."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table


@click.command()
@click.option("--tag", default=None, help="Filter by tag")
@click.option("--strategy", default=None, help="Filter by strategy")
@click.option("--rpi", is_flag=True, help="Show only Raspberry Pi devices")
@click.option("--reachable", is_flag=True, help="Show only recently-seen devices")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def devices(tag, strategy, rpi, reachable, as_json):
    """List known devices from ~/.config/redeploy/devices.yaml.

    \b
    Example:
        redeploy devices
        redeploy devices --tag kiosk
        redeploy devices --reachable
    """
    import json as _json
    from ...models import DeviceRegistry

    console = Console()
    reg = DeviceRegistry.load()
    devs = reg.devices

    if tag:
        devs = [d for d in devs if tag in d.tags]
    if strategy:
        devs = [d for d in devs if d.strategy == strategy]
    if rpi:
        devs = [d for d in devs if "raspberry-pi" in d.tags]
    if reachable:
        devs = [d for d in devs if d.is_reachable]

    if as_json:
        print(
            _json.dumps(
                [d.model_dump(mode="json") for d in devs],
                indent=2,
                default=str,
            )
        )
        return

    if not devs:
        console.print("[dim]No devices found. Run:[/dim]  redeploy scan")
        return

    t = Table(show_header=True, box=None, padding=(0, 2))
    t.add_column("ID", style="bold")
    t.add_column("Host")
    t.add_column("Strategy", style="cyan")
    t.add_column("App")
    t.add_column("Tags", style="dim")
    t.add_column("Last seen", style="dim")
    t.add_column("SSH", style="dim")

    for d in devs:
        seen = d.last_seen.strftime("%m-%d %H:%M") if d.last_seen else "never"
        ssh = "[green]✓[/green]" if d.last_ssh_ok else "[red]✗[/red]"
        tags_str = ",".join(d.tags) or "—"
        # Highlight raspberry-pi tag
        if "raspberry-pi" in d.tags:
            tags_str = tags_str.replace("raspberry-pi", "[bold magenta]raspberry-pi[/bold magenta]")
        t.add_row(
            d.id,
            d.host,
            d.strategy,
            d.app or "—",
            tags_str,
            seen,
            ssh,
        )
    console.print(t)
    console.print(
        f"\n  [dim]{len(devs)} device(s)  •  registry: {DeviceRegistry.default_path()}[/dim]"
    )


@click.command()
@click.option(
    "--subnet", default=None,
    help="CIDR to scan, e.g. 192.168.1.0/24 (auto-detect if omitted)"
)
@click.option(
    "--user", "ssh_users", multiple=True, default=None,
    help="SSH user(s) to try (repeatable). Default: current user + root + pi + ubuntu"
)
@click.option("--port", "ssh_port", default=22, show_default=True, help="SSH port")
@click.option("--ping", is_flag=True, help="Active ICMP ping sweep (sends packets)")
@click.option("--no-mdns", is_flag=True, help="Disable mDNS discovery")
@click.option(
    "--timeout", default=5, show_default=True, help="Per-host SSH timeout (seconds)"
)
@click.option("--no-save", is_flag=True, help="Do not save results to registry")
def scan(subnet, ssh_users, ssh_port, ping, no_mdns, timeout, no_save):
    """Discover SSH-accessible devices on the local network.

    Sources (passive by default, zero packets unless --ping):
      known_hosts  — parse ~/.ssh/known_hosts
      arp          — read ARP/neighbor cache
      mdns         — query _ssh._tcp via avahi-browse
      ping sweep   — ICMP /24 sweep (--ping flag required)

    Results are saved to ~/.config/redeploy/devices.yaml (chmod 600).

    \b
    Example:
        redeploy scan
        redeploy scan --ping --subnet 192.168.1.0/24
        redeploy scan --user pi --user ubuntu --timeout 8
    """
    from ...discovery import discover, update_registry
    from ...models import DeviceRegistry

    console = Console()
    console.print("[bold]redeploy scan[/bold]  discovering devices...")

    users = list(ssh_users) if ssh_users else None
    found = discover(
        subnet=subnet,
        ssh_users=users,
        ssh_port=ssh_port,
        ping=ping,
        mdns=not no_mdns,
        probe_ssh=True,
        timeout=timeout,
    )

    ssh_ok = [h for h in found if h.ssh_ok]
    rpi_count = sum(1 for h in found if h.is_raspberry_pi)
    console.print(f"  found {len(found)} host(s), {len(ssh_ok)} SSH-accessible, {rpi_count} Raspberry Pi\n")

    t = Table(show_header=True, box=None, padding=(0, 2))
    t.add_column("IP")
    t.add_column("Hostname", style="dim")
    t.add_column("MAC", style="dim")
    t.add_column("SSH user", style="cyan")
    t.add_column("RPi", style="bold magenta")
    t.add_column("Source", style="dim")
    for h in found:
        ssh_col = f"[green]{h.ssh_user}[/green]" if h.ssh_ok else "[red]✗[/red]"
        rpi_col = "🍓" if h.is_raspberry_pi else "—"
        t.add_row(h.ip, h.hostname or "—", h.mac or "—", ssh_col, rpi_col, h.source)
    console.print(t)

    if not no_save and ssh_ok:
        reg = update_registry(found, save=True)
        console.print(
            f"\n  [dim]registry updated → {DeviceRegistry.default_path()}[/dim]"
        )
        console.print(f"  [dim]{len(reg.devices)} device(s) total[/dim]")
    elif not ssh_ok:
        console.print("\n  [dim]No SSH-accessible devices — nothing saved.[/dim]")


@click.command("device-add")
@click.argument("host")
@click.option("--id", "device_id", default=None, help="Device ID (default: host)")
@click.option("--name", default="", help="Human-friendly label")
@click.option("--tag", "tags", multiple=True, help="Tag (repeatable)")
@click.option(
    "--strategy", default="docker_full", show_default=True,
    type=click.Choice(["docker_full", "podman_quadlet", "native_kiosk", "docker_kiosk", "k3s", "systemd"]),
    help="Deploy strategy"
)
@click.option("--app", default="", help="Application name")
@click.option("--port", "ssh_port", default=22, show_default=True)
@click.option("--key", "ssh_key", default=None, help="Path to SSH private key")
def device_add(host, device_id, name, tags, strategy, app, ssh_port, ssh_key):
    """Add or update a device in the registry.

    \b
    Example:
        redeploy device-add pi@192.168.1.42 --tag kiosk --strategy native_kiosk --app kiosk-app
        redeploy device-add root@10.0.0.5 --tag prod --strategy docker_full --app myapp
    """
    from ...models import DeviceRegistry, KnownDevice

    console = Console()
    reg = DeviceRegistry.load()

    did = device_id or host
    dev = reg.get(did) or KnownDevice(id=did, host=host)
    dev.host = host
    if name:
        dev.name = name
    if tags:
        dev.tags = list(tags)
    dev.strategy = strategy
    if app:
        dev.app = app
    dev.ssh_port = ssh_port
    if ssh_key:
        dev.ssh_key = ssh_key
    dev.source = "manual"

    reg.upsert(dev)
    reg.save()
    console.print(
        f"[green]✓[/green] device [bold]{did}[/bold] saved → {DeviceRegistry.default_path()}"
    )


@click.command("device-rm")
@click.argument("device_id")
def device_rm(device_id):
    """Remove a device from the registry."""
    from ...models import DeviceRegistry

    console = Console()
    reg = DeviceRegistry.load()
    if reg.remove(device_id):
        reg.save()
        console.print(f"[green]✓[/green] removed {device_id}")
    else:
        console.print(f"[yellow]⚠ not found: {device_id}[/yellow]")

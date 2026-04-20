"""probe command — Autonomous device discovery + registry."""
from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table


@click.command()
@click.argument("hosts", nargs=-1, required=False)
@click.option(
    "--subnet", default=None,
    help="Scan subnet for new devices first (e.g. 192.168.1.0/24)"
)
@click.option(
    "--user", "users", multiple=True,
    help="SSH user(s) to try (in addition to defaults)"
)
@click.option("--port", "ssh_port", default=22, show_default=True)
@click.option("--app", "app_hint", default="", help="App name hint (stored in registry)")
@click.option(
    "--timeout", default=6, show_default=True,
    help="SSH timeout per attempt (seconds)"
)
@click.option("--no-save", is_flag=True, help="Do not persist results to registry")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def probe(hosts, subnet, users, ssh_port, app_hint, timeout, no_save, as_json):
    """Autonomously probe one or more hosts — detect SSH credentials, strategy, app.

    Tries all available SSH keys (~/.ssh/) and common usernames.
    Detects deployment strategy (docker_full / systemd / podman_quadlet / native_kiosk).
    Saves results to ~/.config/redeploy/devices.yaml automatically.

    \b
    Examples:
        # Probe a specific IP (tries pi/ubuntu/root/... + all keys)
        redeploy probe 192.168.188.108

        # Probe with user hint
        redeploy probe pi@192.168.188.108

        # Probe several hosts
        redeploy probe 192.168.1.10 192.168.1.11 192.168.1.12

        # Scan subnet first then probe found hosts
        redeploy probe --subnet 192.168.1.0/24

        # All-in-one: scan + probe + save, then list
        redeploy probe --subnet 192.168.188.0/24 && redeploy devices
    """
    import json as _json
    from ...discovery import auto_probe, discover, update_registry
    from ...models import DeviceRegistry

    console = Console()
    all_ips: list[str] = list(hosts)

    # Optional subnet scan
    if subnet:
        console.print(f"[bold]scan[/bold]  {subnet}  (ARP+ping sweep)...")
        found = discover(subnet=subnet, ping=True, mdns=False, probe_ssh=False, timeout=3)
        new_ips = [h.ip for h in found if h.ip not in all_ips]
        if new_ips:
            console.print(
                f"  found {len(new_ips)} host(s) on {subnet}: "
                + ", ".join(new_ips[:6]) + ("…" if len(new_ips) > 6 else "")
            )
            all_ips.extend(new_ips)

    if not all_ips:
        console.print(
            "[yellow]No hosts specified. Use: redeploy probe IP [IP...] or --subnet CIDR[/yellow]"
        )
        return

    extra_users = list(users) if users else []
    results: list = []

    console.print(
        f"[bold]probe[/bold]  {len(all_ips)} host(s)  "
        f"(keys: {Path.home() / '.ssh'}  timeout: {timeout}s)"
    )

    for ip in all_ips:
        label = ip if "@" in ip else f"[dim]{ip}[/dim]"
        console.print(f"  → {label}", end="  ")
        r = auto_probe(
            ip,
            users=extra_users or None,
            port=ssh_port,
            timeout=timeout,
            app_hint=app_hint,
            save=not no_save,
        )
        if r.reachable:
            key_label = Path(r.ssh_key).name if r.ssh_key else "agent"
            console.print(
                f"[green]✓[/green] {r.ssh_user}  "
                f"[dim]{key_label}[/dim]  "
                f"[cyan]{r.strategy}[/cyan]"
                + (f"  app={r.app}" if r.app else "")
                + (f"  arch={r.arch}" if r.arch else "")
            )
        else:
            console.print(f"[red]✗[/red]  {r.error}")
        results.append(r)

    ok = [r for r in results if r.reachable]
    console.print(f"\n  {len(ok)}/{len(results)} reachable")

    if as_json:
        import dataclasses

        print(_json.dumps([dataclasses.asdict(r) for r in results], indent=2, default=str))
        return

    if ok and not no_save:
        console.print(
            f"  [dim]registry updated → {Path.home() / '.config/redeploy/devices.yaml'}[/dim]"
        )
        # Print table of saved devices
        reg = DeviceRegistry.load()
        t = Table(show_header=True, box=None, padding=(0, 2))
        t.add_column("ID", style="bold")
        t.add_column("Strategy", style="cyan")
        t.add_column("App")
        t.add_column("Arch", style="dim")
        t.add_column("OS", style="dim")
        t.add_column("Key", style="dim")
        for r in ok:
            key_label = Path(r.ssh_key).name if r.ssh_key else "agent"
            t.add_row(
                r.host,
                r.strategy,
                r.app or "—",
                r.arch or "—",
                r.os_info[:30] if r.os_info else "—",
                key_label,
            )
        console.print()
        console.print(t)
        console.print(f"\n  Use [bold]redeploy target {ok[0].host}[/bold] to deploy.")

"""Apply display / kanshi configuration changes on the remote host."""
from __future__ import annotations

import re
import sys

from rich.console import Console

from ...detect.remote import RemoteProbe
from ...hardware.kiosk.compositors import DSI_OUTPUT_NAME


def apply_display_transform(
    console: Console,
    probe: RemoteProbe,
    output_name: str,
    transform: str,
) -> None:
    """Apply *transform* to *output_name* via wlr-randr and persist in kanshi config.

    Parameters
    ----------
    console:
        Rich console for progress output.
    probe:
        Active SSH probe to the target host.
    output_name:
        DRM connector name (e.g. ``DSI-2``).
    transform:
        One of the wlr-randr transforms (``normal``, ``90``, ``180``, ``270``,
        ``flipped``, …).
    """
    console.print(f"[cyan]→ Setting transform {transform} on {output_name}[/cyan]")

    # 1. Apply immediately via wlr-randr
    wlr_cmd = (
        f"WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/$(id -u) "
        f"wlr-randr --output {output_name} --transform {transform} 2>&1"
    )
    r = probe.run(wlr_cmd)
    if r.ok:
        console.print(f"[green]  ✓ wlr-randr transform applied[/green]")
    else:
        console.print(
            f"[yellow]  ⚠ wlr-randr failed (compositor may not be running): "
            f"{r.out.strip()}[/yellow]"
        )

    # 2. Persist in kanshi config — update or create transform line
    kanshi_cfg_path = "~/.config/kanshi/config"
    read_r = probe.run(f"cat {kanshi_cfg_path} 2>/dev/null")

    if read_r.ok and read_r.out.strip():
        current = read_r.out
        output_line_pat = re.compile(
            rf'(\s*output\s+{re.escape(output_name)}\s+enable)(\s+transform\s+\S+)?'
        )
        if re.search(output_line_pat, current):
            new_cfg = re.sub(
                output_line_pat,
                rf'\1 transform {transform}',
                current,
            )
        else:
            new_cfg = re.sub(
                rf'(\s*output\s+{re.escape(output_name)}\b)',
                rf'\1 transform {transform}',
                current,
            )
    else:
        new_cfg = (
            f"profile waveshare-only {{\n"
            f"    output {output_name} enable transform {transform}\n"
            f"}}\n"
        )

    # Write updated config
    escaped = new_cfg.replace("'", "'\\''")
    write_r = probe.run(
        f"mkdir -p ~/.config/kanshi && printf '%s' '{escaped}' > {kanshi_cfg_path}"
    )
    if write_r.ok:
        console.print(f"[green]  ✓ kanshi config updated ({kanshi_cfg_path})[/green]")
    else:
        console.print(f"[red]  ✗ failed to write kanshi config: {write_r.out}[/red]")
        sys.exit(1)

    # 3. Reload kanshi if running
    pkill_r = probe.run(
        "pkill -SIGUSR1 kanshi 2>/dev/null || pkill kanshi 2>/dev/null; sleep 1; "
        "WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/$(id -u) kanshi &"
    )
    if pkill_r.ok:
        console.print("[green]  ✓ kanshi reloaded[/green]")

    console.print(
        f"\n[bold green]✓ Transform {transform} applied to {output_name}[/bold green]\n"
        f"  [dim]Persistent: {kanshi_cfg_path}[/dim]"
    )

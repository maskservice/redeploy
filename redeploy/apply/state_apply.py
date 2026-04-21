"""Declarative state apply — push a desired-state YAML/JSON to a remote host.

Pattern:
    redeploy hardware pi@host > device.yaml   # scan
    # edit device.yaml                        # declare desired state
    redeploy push pi@host device.yaml         # apply diff

The module is extensible: register a new :class:`StateHandler` for every new
file schema.  Each handler says whether it can handle a given dict (``accept``)
and then applies the desired state (``apply``).
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from rich.console import Console

from ..detect.remote import RemoteProbe


# ── handler base ──────────────────────────────────────────────────────────────


@dataclass
class ApplyResult:
    handler: str
    applied: list[str]
    skipped: list[str]
    errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


class StateHandler(ABC):
    """Base class for a declarative state applier."""

    name: str = "base"

    @abstractmethod
    def accept(self, data: dict) -> bool:
        """Return True if this handler knows how to apply *data*."""

    @abstractmethod
    def apply(self, data: dict, p: RemoteProbe, console: Console) -> ApplyResult:
        """Apply *data* to the host behind *p*."""


# ── hardware handler ──────────────────────────────────────────────────────────


class HardwareStateHandler(StateHandler):
    """Applies HardwareInfo-shaped YAML: display transforms, backlight, etc."""

    name = "hardware"

    def accept(self, data: dict) -> bool:
        # HardwareInfo always has drm_outputs or backlights
        return "drm_outputs" in data or "backlights" in data

    def apply(self, data: dict, p: RemoteProbe, console: Console) -> ApplyResult:
        applied: list[str] = []
        skipped: list[str] = []
        errors: list[str] = []

        # ── display transforms ────────────────────────────────────────────────
        for output in data.get("drm_outputs", []):
            connector = output.get("connector", "")
            transform = output.get("transform", "normal")
            enabled = output.get("enabled", "enabled")

            if not connector or ("DSI" not in connector and "HDMI" not in connector):
                continue

            # Apply via wlr-randr
            on_off = "--on" if enabled == "enabled" else "--off"
            transform_arg = f"--transform {transform}" if transform != "normal" else ""
            wlr_cmd = (
                f"WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/$(id -u) "
                f"wlr-randr --output {connector} {on_off} {transform_arg} 2>&1"
            ).strip()
            r = p.run(wlr_cmd)
            if r.ok:
                applied.append(f"display/{connector}: transform={transform} enabled={enabled}")
                console.print(f"[green]  ✓ {connector}: transform={transform}[/green]")
            else:
                msg = r.out.strip()
                # wlr-randr unavailable (no compositor) — not fatal
                if msg:
                    console.print(f"[yellow]  ⚠ {connector} wlr-randr: {msg}[/yellow]")
                skipped.append(f"display/{connector}: wlr-randr unavailable")

        # ── persist DSI transform in kanshi ──────────────────────────────────
        dsi_outputs = [o for o in data.get("drm_outputs", []) if "DSI" in o.get("connector", "")]
        if dsi_outputs:
            _update_kanshi(dsi_outputs, p, console, applied, errors)

        # ── backlight ─────────────────────────────────────────────────────────
        for bl in data.get("backlights", []):
            name = bl.get("name", "")
            if not name:
                continue
            brightness = bl.get("brightness")
            bl_power = bl.get("bl_power")
            if brightness is not None:
                r = p.run(
                    f"echo {brightness} | sudo tee /sys/class/backlight/{name}/brightness > /dev/null"
                )
                if r.ok:
                    applied.append(f"backlight/{name}: brightness={brightness}")
                    console.print(f"[green]  ✓ backlight/{name}: brightness={brightness}[/green]")
                else:
                    errors.append(f"backlight/{name}: brightness set failed")
            if bl_power is not None:
                r = p.run(
                    f"echo {bl_power} | sudo tee /sys/class/backlight/{name}/bl_power > /dev/null"
                )
                if r.ok:
                    applied.append(f"backlight/{name}: bl_power={bl_power}")
                    console.print(f"[green]  ✓ backlight/{name}: bl_power={bl_power}[/green]")
                else:
                    errors.append(f"backlight/{name}: bl_power set failed")

        return ApplyResult(handler=self.name, applied=applied, skipped=skipped, errors=errors)


def _update_kanshi(dsi_outputs: list, p: RemoteProbe, console: Console,
                   applied: list, errors: list) -> None:
    """Rewrite ~/.config/kanshi/config from desired dsi_outputs state."""
    kanshi_cfg_path = "~/.config/kanshi/config"
    read_r = p.run(f"cat {kanshi_cfg_path} 2>/dev/null")
    current = read_r.out if read_r.ok else ""

    for output in dsi_outputs:
        connector = output.get("connector", "")
        transform = output.get("transform", "normal")

        line_pat = re.compile(
            rf'(\s*output\s+{re.escape(connector)}\s+enable)(\s+transform\s+\S+)?'
        )
        if re.search(line_pat, current):
            if transform == "normal":
                current = re.sub(line_pat, r'\1', current)
            else:
                current = re.sub(line_pat, rf'\1 transform {transform}', current)
        elif current.strip():
            current = re.sub(
                rf'(\s*output\s+{re.escape(connector)}\b)',
                (rf'\1 transform {transform}' if transform != "normal" else r'\1'),
                current,
            )
        else:
            current = (
                f"profile waveshare-only {{\n"
                f"    output {connector} enable"
                + (f" transform {transform}" if transform != "normal" else "")
                + "\n    output HDMI-A-2 disable\n}\n"
            )

    escaped = current.replace("'", "'\\''")
    write_r = p.run(
        f"mkdir -p ~/.config/kanshi && printf '%s' '{escaped}' > {kanshi_cfg_path}"
    )
    if write_r.ok:
        applied.append(f"kanshi: config updated")
        console.print(f"[green]  ✓ kanshi config saved ({kanshi_cfg_path})[/green]")
    else:
        errors.append("kanshi: config write failed")

    # Reload kanshi if running — SIGUSR1 = reload profiles
    p.run("pkill -SIGUSR1 kanshi 2>/dev/null || true")


# ── future handlers registered here ──────────────────────────────────────────


class InfraStateHandler(StateHandler):
    """Placeholder — applies InfraState-shaped YAML (services, ports, etc.)."""

    name = "infra"

    def accept(self, data: dict) -> bool:
        return "runtime" in data and "services" in data

    def apply(self, data: dict, p: RemoteProbe, console: Console) -> ApplyResult:
        # TODO: implement service-level desired state reconciliation
        console.print("[yellow]  infra state apply not yet implemented[/yellow]")
        return ApplyResult(handler=self.name, applied=[], skipped=["not implemented"], errors=[])


# ── registry ──────────────────────────────────────────────────────────────────

_HANDLERS: list[StateHandler] = [
    HardwareStateHandler(),
    InfraStateHandler(),
]


def detect_handler(data: dict) -> StateHandler | None:
    """Return the first handler that accepts *data*, or None."""
    for h in _HANDLERS:
        if h.accept(data):
            return h
    return None


def apply_state(data: dict, p: RemoteProbe, console: Console) -> ApplyResult:
    """Auto-detect file type and apply desired state."""
    handler = detect_handler(data)
    if handler is None:
        return ApplyResult(
            handler="unknown",
            applied=[],
            skipped=[],
            errors=["No handler found for this file format"],
        )
    console.print(f"[dim]handler: {handler.name}[/dim]")
    return handler.apply(data, p, console)

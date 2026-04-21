"""Core CLI utilities shared across commands."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from rich.console import Console
    from ..models import MigrationSpec, DeviceRegistry, KnownDevice


def load_spec_or_exit(console: "Console", path: str | Path) -> "MigrationSpec":
    """Load a migration spec or exit with error."""
    from ..spec_loader import SpecLoaderError, load_migration_spec

    try:
        return load_migration_spec(path)
    except SpecLoaderError as exc:
        console.print(f"[red]✗ {exc}[/red]")
        sys.exit(1)


def find_manifest_path() -> str:
    """Find redeploy.yaml manifest in current or parent directories."""
    for d in [Path.cwd()] + list(Path.cwd().parents):
        c = d / "redeploy.yaml"
        if c.exists():
            return str(c)
    return "redeploy.yaml"


def resolve_device(
    console: "Console", device_id: str
) -> tuple["KnownDevice | None", "DeviceRegistry"]:
    """Resolve device from registry or auto-probe."""
    from ..discovery import auto_probe
    from ..models import DeviceRegistry

    reg = DeviceRegistry.load()
    dev = reg.get(device_id)

    if not dev:
        console.print(f"[yellow]⚠ {device_id} not in registry — probing…[/yellow]")
        r = auto_probe(device_id, timeout=8, save=True)
        if r.reachable:
            reg = DeviceRegistry.load()  # reload after probe saved
            dev = reg.get(r.host) or reg.get(r.ip)
            key_name = __import__("os").path.basename(r.ssh_key) if r.ssh_key else "agent"
            console.print(
                f"  [green]✓[/green] auto-probe OK: {r.host}  "
                f"strategy={r.strategy}  key={key_name}"
            )
        else:
            console.print(f"  [red]✗ probe failed: {r.error}[/red]")
            console.print(
                "[dim]  Add manually: redeploy device-add HOST --strategy STRATEGY[/dim]"
            )

    return dev, reg


def load_spec_with_manifest(
    console: "Console", spec_file: str | None, dev: "KnownDevice | None"
) -> tuple["MigrationSpec", "ProjectManifest | None"]:
    """Load spec and apply manifest/device overlays."""
    from ..models import ProjectManifest

    manifest = ProjectManifest.find_and_load(Path.cwd())
    resolved_spec = spec_file or (manifest.spec if manifest else "migration.yaml")
    if not Path(resolved_spec).exists():
        console.print(f"[red]✗ spec not found: {resolved_spec}[/red]")
        sys.exit(1)

    spec = load_spec_or_exit(console, resolved_spec)
    if manifest:
        manifest.apply_to_spec(spec)

    return spec, manifest


def overlay_device_onto_spec(
    spec: "MigrationSpec", dev: "KnownDevice | None", console: "Console"
) -> None:
    """Overlay device values onto spec target configuration."""
    if not dev:
        return

    spec.source.host = dev.host
    spec.target.host = dev.host

    if dev.strategy:
        from ..models import DeployStrategy as DS

        try:
            spec.target.strategy = DS(dev.strategy)
        except ValueError:
            pass

    if dev.app and not spec.target.app:
        spec.target.app = dev.app
    if dev.domain and not spec.target.domain:
        spec.target.domain = dev.domain
    if dev.remote_dir and not spec.target.remote_dir:
        spec.target.remote_dir = dev.remote_dir

    console.print(
        f"[bold]target[/bold]  [cyan]{dev.id}[/cyan]  "
        f"{spec.source.strategy.value} → {spec.target.strategy.value}"
    )


def run_detect_for_spec(
    console: "Console", spec: "MigrationSpec", do_detect: bool
) -> "Planner":
    """Run detect if requested and return planner."""
    from ..detect import Detector
    from ..plan import Planner

    if not do_detect:
        return Planner.from_spec(spec)

    console.print(f"\n[bold]detect[/bold]  (live probe of {spec.source.host})")
    d = Detector(host=spec.source.host, app=spec.source.app, domain=spec.source.domain)
    state = d.run()
    console.print(
        f"  detected: {state.detected_strategy}  "
        f"version={state.current_version or '?'}  "
        f"conflicts={len(state.conflicts)}"
    )
    planner = Planner(state, spec.to_target_config())
    planner._spec = spec
    return planner


def run_detect_workflow(
    console: "Console",
    hosts: list[str],
    manifest: "ProjectManifest | None",
    app: str,
    scan_subnet: str | None,
    deep: bool,
    save_yaml: str | None,
    fmt: str = "yaml",
) -> None:
    """Run DetectionWorkflow and print rich report."""
    from ..detect.workflow import DetectionWorkflow
    from ..models import DeviceRegistry
    from ..display import (
        print_workflow_summary_table,
        print_workflow_host_details,
        generate_workflow_output_css,
        generate_workflow_output_yaml,
    )

    console.print(
        f"[bold]detect --workflow[/bold]  app={app}"
        + (f"  scan={scan_subnet}" if scan_subnet else "")
    )

    wf = DetectionWorkflow(deep=deep, timeout=8)
    result = wf.run(
        hosts=hosts,
        manifest=manifest,
        registry=DeviceRegistry.load(),
        scan_subnet=scan_subnet,
        app=app,
    )

    print_workflow_summary_table(console, result)
    print_workflow_host_details(console, result)

    if result.reachable:
        if fmt == "css":
            generate_workflow_output_css(console, result, app, save_yaml)
        else:
            generate_workflow_output_yaml(console, result, save_yaml)

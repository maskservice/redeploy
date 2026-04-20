"""redeploy CLI — detect | plan | apply | migrate."""
from __future__ import annotations

import sys
from pathlib import Path

import click
import yaml
from loguru import logger

from . import __version__
from .models import DeployStrategy, TargetConfig


def _print_plan_table(console, migration) -> None:
    from rich.table import Table

    t = Table(show_header=True, box=None, padding=(0, 2))
    t.add_column("#", style="dim", width=3)
    t.add_column("ID")
    t.add_column("Action", style="cyan")
    t.add_column("Description")
    t.add_column("Risk", style="dim")
    for i, step in enumerate(migration.steps, 1):
        t.add_row(str(i), step.id, step.action.value, step.description, step.risk.value)
    console.print(t)
    console.print(f"  risk={migration.risk.value}  downtime={migration.estimated_downtime}")
    for note in (migration.notes or []):
        console.print(f"  [yellow]⚠ {note}[/yellow]")


def _run_apply(console, migration, dry_run, output, ssh_key: str = "",
               progress_yaml: bool = False) -> bool:
    from .apply import Executor

    prefix = "[DRY RUN] " if dry_run else ""
    console.print(f"\n[bold]{prefix}apply[/bold]")
    executor = Executor(migration, dry_run=dry_run, ssh_key=ssh_key or None,
                        progress_yaml=progress_yaml)
    ok = executor.run()
    console.print(f"\n{executor.summary()}")
    if output:
        executor.save_results(Path(output))
    return ok


def _setup_logging(verbose: bool) -> None:
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(sys.stderr, level=level,
               format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | {message}")


@click.group()
@click.version_option(__version__)
@click.option("-v", "--verbose", is_flag=True)
@click.pass_context
def cli(ctx, verbose):
    """redeploy — Infrastructure migration toolkit: detect → plan → apply"""
    _setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


def _run_detect_workflow(console, hosts, manifest, app, scan_subnet, deep, save_yaml):
    """Run DetectionWorkflow and print rich report."""
    from rich.table import Table
    from .detect.workflow import DetectionWorkflow
    from .models import DeviceRegistry

    console.print(f"[bold]detect --workflow[/bold]  app={app}"
                  + (f"  scan={scan_subnet}" if scan_subnet else ""))

    wf = DetectionWorkflow(deep=deep, timeout=8)
    result = wf.run(
        hosts=hosts,
        manifest=manifest,
        registry=DeviceRegistry.load(),
        scan_subnet=scan_subnet,
        app=app,
    )

    # ── Summary table ─────────────────────────────────────────────────────────
    console.print()
    t = Table(show_header=True, box=None, padding=(0, 2))
    t.add_column("Host", style="bold")
    t.add_column("Env", style="cyan")
    t.add_column("Strategy")
    t.add_column("Template")
    t.add_column("Conf", style="dim")
    t.add_column("Arch", style="dim")
    t.add_column("Conflicts", style="yellow")

    for h in result.hosts:
        if h.reachable:
            conf_color = {"high": "green", "medium": "yellow", "low": "red"}.get(h.confidence, "dim")
            conflicts = str(len(h.state.conflicts)) if h.state else "—"
            t.add_row(
                h.host, h.environment, h.strategy.value,
                h.template_name[:30],
                f"[{conf_color}]{h.confidence}[/{conf_color}]",
                h.arch or "—",
                conflicts,
            )
        else:
            t.add_row(h.host, "—", "—", f"[red]✗ {h.error[:30]}[/red]", "—", "—", "—")
    console.print(t)

    console.print(f"\n  {len(result.reachable)}/{len(result.hosts)} reachable")

    # ── Per-host details ──────────────────────────────────────────────────────
    for h in result.reachable:
        if not h.template_result:
            continue
        best = h.template_result.best
        console.print(f"\n[bold]── {h.host} ──[/bold]  [cyan]{h.environment}[/cyan]  {h.strategy.value}")
        console.print(f"  Template:   {best.template.name}")
        console.print(f"  Confidence: {best.score:.1f}/{best.max_score:.1f}  ({best.confidence_label})")
        if best.matched_conditions:
            console.print(f"  [green]✓[/green] " + "  ".join(best.matched_conditions[:5]))
        if best.failed_conditions:
            console.print(f"  [dim]✗ " + "  ".join(best.failed_conditions[:4]) + "[/dim]")
        if h.template_result.best.template.notes:
            for note in h.template_result.best.template.notes[:2]:
                console.print(f"  [dim]→ {note}[/dim]")

        # Top 3 alternatives
        alts = [m for m in h.template_result.ranked[1:4] if m.score > 0]
        if alts:
            console.print(f"  [dim]alternatives: "
                          + " | ".join(f"{m.template.id} ({m.score:.1f})" for m in alts)
                          + "[/dim]")

    # ── Generated redeploy.yaml ───────────────────────────────────────────────
    if result.reachable:
        console.print(f"\n[bold]generated redeploy.yaml:[/bold]")
        yaml_out = result.generated_redeploy_yaml()
        console.print(yaml_out)

        if save_yaml:
            Path(save_yaml).write_text(yaml_out)
            console.print(f"  [dim]saved → {save_yaml}[/dim]")


# ── detect ────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--host", default=None, help="SSH host (user@ip) or 'local'")
@click.option("--app", default=None, show_default=True, help="Application name (default from redeploy.yaml)")
@click.option("--domain", default=None, help="Public domain for HTTP health checks")
@click.option("-o", "--output", default="infra.yaml", show_default=True,
              type=click.Path(), help="Output file for InfraState")
@click.option("--workflow", "run_workflow", is_flag=True,
              help="Run full multi-host workflow (detect + template scoring)")
@click.option("--scan", "scan_subnet", default=None,
              help="Subnet to scan for devices (used with --workflow)")
@click.option("--no-deep", is_flag=True,
              help="Workflow: skip deep SSH probe (faster, less accurate)")
@click.option("--save-yaml", default=None, type=click.Path(),
              help="Workflow: save generated redeploy.yaml to file")
@click.pass_context
def detect(ctx, host, app, domain, output, run_workflow, scan_subnet, no_deep, save_yaml):
    """Probe infrastructure and produce infra.yaml.

    With --workflow: multi-host detection with template scoring.
    Reads hosts from redeploy.yaml environments + device registry + --scan subnet.

    \b
    Examples:
        redeploy detect --host pi@192.168.188.108
        redeploy detect --workflow
        redeploy detect --workflow --scan 192.168.188.0/24
        redeploy detect --workflow --host 192.168.188.108 --host 87.106.87.183
        redeploy detect --workflow --save-yaml redeploy.yaml
    """
    from rich.console import Console
    from .models import ProjectManifest

    console = Console()
    manifest = ProjectManifest.find_and_load(Path.cwd())
    app_name = app or (manifest.app if manifest else "app")

    if run_workflow or scan_subnet:
        _run_detect_workflow(
            console,
            hosts=[host] if host else [],
            manifest=manifest,
            app=app_name,
            scan_subnet=scan_subnet,
            deep=not no_deep,
            save_yaml=save_yaml,
        )
        return

    if not host:
        console.print("[red]✗ --host required (or use --workflow)[/red]")
        sys.exit(1)
    from rich.table import Table
    from .detect import Detector

    out_path = Path(output)
    domain = domain or (manifest.domain if manifest else None)

    try:
        d = Detector(host=host, app=app_name, domain=domain)
        state = d.run()
        d.save(state, out_path)
    except ConnectionError as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)

    # Print summary
    console.print(f"\n[bold]Infrastructure: {host}[/bold]")

    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column("key", style="dim")
    t.add_column("value")
    t.add_row("App", state.app)
    t.add_row("Strategy (detected)", state.detected_strategy.value)
    t.add_row("Version", state.current_version or "unknown")
    t.add_row("Docker", state.runtime.docker or "—")
    t.add_row("k3s", state.runtime.k3s or "—")
    t.add_row("Podman", state.runtime.podman or "—")
    t.add_row("Open ports", ", ".join(str(p) for p in sorted(state.ports.keys())))
    console.print(t)

    # Docker services
    if state.services.get("docker"):
        console.print("\n[bold]Docker containers:[/bold]")
        for s in state.services["docker"]:
            icon = "✅" if s.status == "healthy" else "⚪"
            console.print(f"  {icon} {s.name}  ({s.status})")

    # k3s pods
    if state.services.get("k3s"):
        console.print(f"\n[bold]k3s pods ({len(state.services['k3s'])}):[/bold]")
        for s in state.services["k3s"]:
            icon = "✅" if s.status == "running" else "⚪"
            console.print(f"  {icon} {s.namespace}/{s.name}  ({s.status})")

    # Conflicts
    if state.conflicts:
        console.print(f"\n[bold yellow]Conflicts ({len(state.conflicts)}):[/bold yellow]")
        for c in state.conflicts:
            color = {"critical": "red", "high": "yellow", "medium": "blue", "low": "dim"}[c.severity.value]
            console.print(f"  [{color}][{c.severity.upper()}][/{color}] {c.type}: {c.description}")
            if c.fix_hint:
                console.print(f"    [dim]hint: {c.fix_hint}[/dim]")
    else:
        console.print("\n[green]No conflicts detected.[/green]")

    console.print(f"\n[dim]Saved to {out_path}[/dim]")


# ── plan ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--infra", default="infra.yaml", show_default=True,
              type=click.Path(exists=True), help="InfraState file (from detect)")
@click.option("--target", default=None, type=click.Path(),
              help="Target config YAML (desired state)")
@click.option("--strategy", default=None,
              type=click.Choice([s.value for s in DeployStrategy]),
              help="Override target strategy")
@click.option("--domain", default=None, help="Public domain for verify step")
@click.option("--version", "target_version", default=None, help="Target version to verify")
@click.option("--compose", multiple=True, help="Compose file(s) for docker_full strategy")
@click.option("--env-file", default=None, help="Env file path")
@click.option("-o", "--output", default="migration-plan.yaml", show_default=True,
              type=click.Path(), help="Output migration plan file")
@click.pass_context
def plan(ctx, infra, target, strategy, domain, target_version, compose, env_file, output):
    """Generate migration-plan.yaml from infra.yaml + target config."""
    from rich.console import Console
    from rich.table import Table
    from .plan import Planner

    console = Console()
    out_path = Path(output)
    infra_path = Path(infra)
    target_path = Path(target) if target else None

    planner = Planner.from_files(infra_path, target_path)

    # CLI overrides
    if strategy:
        planner.target.strategy = DeployStrategy(strategy)
    if domain:
        planner.target.domain = domain
    if target_version:
        planner.target.verify_version = target_version
    if compose:
        planner.target.compose_files = list(compose)
    if env_file:
        planner.target.env_file = env_file

    migration = planner.run()
    planner.save(migration, out_path)

    console.print(f"\n[bold]Migration plan: {migration.from_strategy.value} → {migration.to_strategy.value}[/bold]")
    console.print(f"  Risk:             {migration.risk.value}")
    console.print(f"  Estimated downtime: {migration.estimated_downtime}")
    console.print(f"  Steps:            {len(migration.steps)}")

    if migration.steps:
        console.print("\n[bold]Steps:[/bold]")
        t = Table(show_header=True, box=None, padding=(0, 2))
        t.add_column("#", style="dim", width=3)
        t.add_column("ID")
        t.add_column("Action", style="cyan")
        t.add_column("Description")
        t.add_column("Risk", style="dim")
        for i, step in enumerate(migration.steps, 1):
            t.add_row(str(i), step.id, step.action.value, step.description, step.risk.value)
        console.print(t)

    if migration.notes:
        console.print("\n[bold yellow]Notes:[/bold yellow]")
        for note in migration.notes:
            console.print(f"  • {note}")

    console.print(f"\n[dim]Saved to {out_path}[/dim]")


# ── apply ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--plan", "plan_file", default="migration-plan.yaml", show_default=True,
              type=click.Path(exists=True), help="Migration plan file")
@click.option("--dry-run", is_flag=True, help="Show steps without executing")
@click.option("--step", default=None, help="Run only a specific step by ID")
@click.option("-o", "--output", default=None, type=click.Path(),
              help="Save results to file after apply")
@click.pass_context
def apply(ctx, plan_file, dry_run, step, output):
    """Execute a migration plan."""
    from rich.console import Console
    from .apply import Executor

    console = Console()
    executor = Executor.from_file(Path(plan_file))

    if step:
        # Filter to single step
        matched = [s for s in executor.plan.steps if s.id == step]
        if not matched:
            console.print(f"[red]Step '{step}' not found in plan[/red]")
            ids = ", ".join(s.id for s in executor.plan.steps)
            console.print(f"Available: {ids}")
            sys.exit(1)
        executor.plan.steps = matched

    executor.dry_run = dry_run

    prefix = "[DRY RUN] " if dry_run else ""
    console.print(f"\n{prefix}[bold]Applying: {executor.plan.from_strategy.value}"
                  f" → {executor.plan.to_strategy.value}[/bold]  "
                  f"({len(executor.plan.steps)} steps)")

    ok = executor.run()
    console.print(f"\n{executor.summary()}")

    if output:
        executor.save_results(Path(output))

    if not ok:
        sys.exit(1)


# ── migrate (detect + plan + apply) ──────────────────────────────────────────

@cli.command()
@click.option("--host", required=True, help="SSH host (user@ip) or 'local'")
@click.option("--app", default=None, show_default=True, help="Application name (default from redeploy.yaml)")
@click.option("--domain", default=None)
@click.option("--target", default=None, type=click.Path(), help="Target config YAML")
@click.option("--strategy", default="docker_full", show_default=True,
              type=click.Choice([s.value for s in DeployStrategy]))
@click.option("--version", "target_version", default=None)
@click.option("--compose", multiple=True)
@click.option("--env-file", default=None)
@click.option("--dry-run", is_flag=True)
@click.option("--infra-out", default="infra.yaml", show_default=True, type=click.Path())
@click.option("--plan-out", default="migration-plan.yaml", show_default=True, type=click.Path())
@click.pass_context
def migrate(ctx, host, app, domain, target, strategy, target_version,
            compose, env_file, dry_run, infra_out, plan_out):
    """Full pipeline: detect → plan → apply."""
    from rich.console import Console
    from .detect import Detector
    from .plan import Planner
    from .apply import Executor
    from .models import ProjectManifest, TargetConfig

    console = Console()

    manifest = ProjectManifest.find_and_load(Path.cwd())
    app = app or (manifest.app if manifest else "c2004")
    domain = domain or (manifest.domain if manifest else None)

    # 1. detect
    console.print(f"\n[bold]Step 1/3 — detect[/bold]")
    d = Detector(host=host, app=app, domain=domain)
    state = d.run()
    d.save(state, Path(infra_out))
    console.print(f"  Strategy: {state.detected_strategy.value}  "
                  f"  Version: {state.current_version or '?'}  "
                  f"  Conflicts: {len(state.conflicts)}")

    # 2. plan
    console.print(f"\n[bold]Step 2/3 — plan[/bold]")
    target_path = Path(target) if target else None
    planner = Planner.from_files(Path(infra_out), target_path)
    planner.target.strategy = DeployStrategy(strategy)
    if domain:
        planner.target.domain = domain
    if target_version:
        planner.target.verify_version = target_version
    if compose:
        planner.target.compose_files = list(compose)
    if env_file:
        planner.target.env_file = env_file

    migration = planner.run()
    planner.save(migration, Path(plan_out))
    console.print(f"  Steps: {len(migration.steps)}  Risk: {migration.risk.value}  "
                  f"Downtime: {migration.estimated_downtime}")

    # 3. apply
    console.print(f"\n[bold]Step 3/3 — apply{'  (dry-run)' if dry_run else ''}[/bold]")
    executor = Executor(migration, dry_run=dry_run)
    ok = executor.run()
    console.print(f"\n{executor.summary()}")

    if not ok:
        sys.exit(1)


# ── run (single migration.yaml: source + target) ─────────────────────────────

@cli.command()
@click.argument("spec_file", default=None, required=False,
                type=click.Path(), metavar="SPEC")
@click.option("--dry-run", is_flag=True, help="Show steps without executing")
@click.option("--plan-only", is_flag=True, help="Generate plan but do not apply")
@click.option("--detect", "do_detect", is_flag=True,
              help="Run live detect first (overrides source state from spec)")
@click.option("--plan-out", default=None, type=click.Path(),
              help="Save generated plan to file")
@click.option("-o", "--output", default=None, type=click.Path(),
              help="Save apply results to file")
@click.option("--env", "env_name", default="",
              help="Named environment from redeploy.yaml (e.g. prod, dev, rpi5)")
@click.option("--progress-yaml", is_flag=True,
              help="Emit machine-readable YAML progress events to stdout")
@click.pass_context
def run(ctx, spec_file, dry_run, plan_only, do_detect, plan_out, output, env_name, progress_yaml):
    """Execute migration from a single YAML spec (source + target in one file).

    SPEC defaults to migration.yaml (or value from redeploy.yaml manifest).

    \b
    Example:
        redeploy run                        # uses redeploy.yaml + migration.yaml
        redeploy run --env prod             # use prod environment from redeploy.yaml
        redeploy run --env rpi5 --detect    # deploy to rpi5 env with live probe
        redeploy run migration.yaml --dry-run
        redeploy run migration.yaml --detect --plan-out plan.yaml
    """
    from rich.console import Console
    from .models import MigrationSpec, ProjectManifest
    from .plan import Planner

    console = Console()

    # ── load project manifest (redeploy.yaml) if present ─────────────────────
    manifest = ProjectManifest.find_and_load(Path.cwd())

    # resolve spec file: arg > manifest.spec > "migration.yaml"
    resolved_spec = spec_file or (manifest.spec if manifest else "migration.yaml")
    if not Path(resolved_spec).exists():
        console.print(f"[red]✗ spec file not found: {resolved_spec}[/red]")
        console.print("[dim]  Create one with: redeploy init[/dim]")
        sys.exit(1)

    spec = MigrationSpec.from_file(resolved_spec)

    # overlay manifest values — env-specific or global
    if manifest:
        if env_name and env_name not in manifest.environments:
            console.print(f"[yellow]⚠ env '{env_name}' not in redeploy.yaml — known: "
                          f"{', '.join(manifest.environments) or 'none'}[/yellow]")
        manifest.apply_to_spec(spec, env_name=env_name)
        env_label = f" [cyan][env: {env_name}][/cyan]" if env_name else ""
        console.print(f"[dim]manifest: {_find_manifest_path()}{env_label}[/dim]")
    elif not env_name:
        # Fallback: read DEPLOY_* from .env if no redeploy.yaml
        dotenv_manifest = ProjectManifest.from_dotenv(Path.cwd())
        if dotenv_manifest:
            dotenv_manifest.apply_to_spec(spec)
            console.print("[dim]manifest: .env (DEPLOY_* vars)[/dim]")

    console.print(f"\n[bold]{spec.name}[/bold]"
                  + (f"  [dim]{spec.description}[/dim]" if spec.description else ""))
    console.print(f"  [dim]{spec.source.strategy.value}[/dim]  →  "
                  f"[bold]{spec.target.strategy.value}[/bold]"
                  f"  ({spec.source.host})")

    # ── optional live detect (overrides source in spec) ──────────────────────
    if do_detect:
        from .detect import Detector
        console.print(f"\n[bold]detect[/bold]  (live probe of {spec.source.host})")
        d = Detector(
            host=spec.source.host,
            app=spec.source.app,
            domain=spec.source.domain,
        )
        state = d.run()
        console.print(f"  detected: {state.detected_strategy.value}  "
                      f"version={state.current_version or '?'}  "
                      f"conflicts={len(state.conflicts)}")
        planner = Planner(state, spec.to_target_config())
        planner._spec = spec
    else:
        planner = Planner.from_spec(spec)

    # ── plan ─────────────────────────────────────────────────────────────────
    console.print(f"\n[bold]plan[/bold]")
    migration = planner.run()

    if plan_out:
        planner.save(migration, Path(plan_out))
        console.print(f"  [dim]plan saved → {plan_out}[/dim]")

    _print_plan_table(console, migration)

    if plan_only:
        console.print("\n[dim]--plan-only: stopping before apply[/dim]")
        return

    if not _run_apply(console, migration, dry_run, output, progress_yaml=progress_yaml):
        sys.exit(1)


# ── helper ────────────────────────────────────────────────────────────────────

def _find_manifest_path() -> str:
    for d in [Path.cwd()] + list(Path.cwd().parents):
        c = d / "redeploy.yaml"
        if c.exists():
            return str(c)
    return "redeploy.yaml"


def _resolve_device(console, device_id: str) -> tuple:
    """Resolve device from registry or auto-probe. Returns (device, registry) or (None, None)."""
    from .discovery import auto_probe
    from .models import DeviceRegistry

    reg = DeviceRegistry.load()
    dev = reg.get(device_id)

    if not dev:
        # Unknown device — try autonomous probe first
        console.print(f"[yellow]⚠ {device_id} not in registry — probing…[/yellow]")
        r = auto_probe(device_id, timeout=8, save=True)
        if r.reachable:
            reg = DeviceRegistry.load()  # reload after probe saved
            dev = reg.get(r.host) or reg.get(r.ip)
            key_name = __import__('os').path.basename(r.ssh_key) if r.ssh_key else 'agent'
            console.print(f"  [green]✓[/green] auto-probe OK: {r.host}  "
                          f"strategy={r.strategy}  key={key_name}")
        else:
            console.print(f"  [red]✗ probe failed: {r.error}[/red]")
            console.print("[dim]  Add manually: redeploy device-add HOST --strategy STRATEGY[/dim]")

    return dev, reg


def _load_spec_with_manifest(console, spec_file: str | None, dev) -> "MigrationSpec":
    """Load spec and apply manifest/device overlays."""
    from .models import MigrationSpec, ProjectManifest

    manifest = ProjectManifest.find_and_load(Path.cwd())
    resolved_spec = spec_file or (manifest.spec if manifest else "migration.yaml")
    if not Path(resolved_spec).exists():
        console.print(f"[red]✗ spec not found: {resolved_spec}[/red]")
        sys.exit(1)

    spec = MigrationSpec.from_file(resolved_spec)
    if manifest:
        manifest.apply_to_spec(spec)

    return spec, manifest


def _overlay_device_onto_spec(spec, dev, console) -> None:
    """Overlay device values onto spec target configuration."""
    if not dev:
        return

    spec.source.host = dev.host
    spec.target.host = dev.host

    if dev.strategy:
        from .models import DeployStrategy as DS
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


def _run_detect_for_spec(console, spec, do_detect: bool) -> "Planner":
    """Run detect if requested and return planner."""
    from .detect import Detector
    from .plan import Planner

    if not do_detect:
        return Planner.from_spec(spec)

    console.print(f"\n[bold]detect[/bold]  (live probe of {spec.source.host})")
    d = Detector(host=spec.source.host, app=spec.source.app, domain=spec.source.domain)
    state = d.run()
    console.print(f"  detected: {state.detected_strategy.value}  "
                  f"version={state.current_version or '?'}  "
                  f"conflicts={len(state.conflicts)}")
    planner = Planner(state, spec.to_target_config())
    planner._spec = spec
    return planner


# ── init (generate migration.yaml + redeploy.yaml) ────────────────────────────

@cli.command()
@click.option("--host", default=None, help="Remote host (user@ip or 'local')")
@click.option("--app", default=None, help="Application name")
@click.option("--domain", default=None, help="Public domain")
@click.option("--strategy", default="docker_full",
              type=click.Choice(["docker_full", "podman_quadlet", "k3s", "systemd"]),
              help="Target deployment strategy")
@click.option("--force", is_flag=True, help="Overwrite existing files")
def init(host, app, domain, strategy, force):
    """Scaffold migration.yaml + redeploy.yaml for this project.

    \b
    Example:
        redeploy init --host root@1.2.3.4 --app myapp --domain myapp.example.com
        redeploy init --strategy podman_quadlet
    """
    from rich.console import Console
    console = Console()

    # ── infer defaults from cwd ───────────────────────────────────────────────
    app = app or Path.cwd().name
    host = host or "local"
    domain = domain or f"{app}.example.com"

    # ── redeploy.yaml ─────────────────────────────────────────────────────────
    manifest_path = Path.cwd() / "redeploy.yaml"
    if manifest_path.exists() and not force:
        console.print(f"[yellow]⚠ {manifest_path} exists — skipping (use --force)[/yellow]")
    else:
        manifest_content = f"""\
# redeploy project manifest — auto-generated by `redeploy init`
# Run `redeploy run` (no args) to use these defaults.
spec: migration.yaml
local_spec: migration-local.yaml
host: {host}
app: {app}
domain: {domain}
ssh_port: 22
env_file: .env
"""
        manifest_path.write_text(manifest_content)
        console.print(f"[green]✓[/green] {manifest_path}")

    # ── migration.yaml ────────────────────────────────────────────────────────
    spec_path = Path.cwd() / "migration.yaml"
    if spec_path.exists() and not force:
        console.print(f"[yellow]⚠ {spec_path} exists — skipping (use --force)[/yellow]")
    else:
        spec_content = f"""\
name: {app}
description: "Deploy {app} to {host}"

source:
  strategy: docker_full
  host: local
  app: {app}
  version: "0.1.0"

target:
  strategy: {strategy}
  host: {host}
  app: {app}
  version: "0.1.0"
  remote_dir: ~/{app}
  domain: {domain}
  verify_url: http://localhost:8000/health
  env_file: .env
"""
        spec_path.write_text(spec_content)
        console.print(f"[green]✓[/green] {spec_path}")

    # ── migration-local.yaml ──────────────────────────────────────────────────
    local_spec_path = Path.cwd() / "migration-local.yaml"
    if local_spec_path.exists() and not force:
        console.print(f"[yellow]⚠ {local_spec_path} exists — skipping (use --force)[/yellow]")
    else:
        local_content = f"""\
name: {app}-local-refresh
description: "Local docker-compose refresh"

source:
  strategy: docker_full
  host: local
  app: {app}

target:
  strategy: docker_full
  host: local
  app: {app}
  remote_dir: .
  verify_url: http://localhost:8000/health
  env_file: .env
"""
        local_spec_path.write_text(local_content)
        console.print(f"[green]✓[/green] {local_spec_path}")

    console.print(f"\n[bold]Next steps:[/bold]")
    console.print(f"  1. Edit [cyan]migration.yaml[/cyan] — set versions, verify_url, compose_files")
    console.print(f"  2. [cyan]redeploy run --plan-only[/cyan]   # preview steps")
    console.print(f"  3. [cyan]redeploy run --dry-run[/cyan]     # dry run")
    console.print(f"  4. [cyan]redeploy run[/cyan]               # deploy!")


# ── status (show project + manifest summary) ──────────────────────────────────

@cli.command()
@click.argument("spec_file", default=None, required=False, type=click.Path(), metavar="SPEC")
def status(spec_file):
    """Show current project manifest and spec summary.

    \b
    Example:
        redeploy status
        redeploy status migration.yaml
    """
    from rich.console import Console
    from rich.table import Table
    from .models import MigrationSpec, ProjectManifest

    console = Console()

    manifest = ProjectManifest.find_and_load(Path.cwd())
    if manifest:
        console.print(f"[bold]redeploy.yaml[/bold]  [dim]{_find_manifest_path()}[/dim]")
        t = Table(show_header=False, box=None, padding=(0, 2))
        for k, v in manifest.model_dump().items():
            if v is not None and v != "" and v != 22:
                t.add_row(f"  [dim]{k}[/dim]", str(v))
        console.print(t)
    else:
        console.print("[dim]no redeploy.yaml found (run `redeploy init`)[/dim]")

    resolved = spec_file or (manifest.spec if manifest else "migration.yaml")
    spec_path = Path(resolved)
    if spec_path.exists():
        spec = MigrationSpec.from_file(str(spec_path))
        if manifest:
            manifest.apply_to_spec(spec)
        console.print(f"\n[bold]{spec_path}[/bold]  [dim]{spec.name}[/dim]")
        console.print(f"  {spec.source.strategy.value}  →  [cyan]{spec.target.strategy.value}[/cyan]")
        console.print(f"  host={spec.source.host}  app={spec.source.app}")
        if spec.target.domain:
            console.print(f"  domain={spec.target.domain}")
        if spec.target.verify_url:
            console.print(f"  verify_url={spec.target.verify_url}")
    else:
        console.print(f"\n[yellow]⚠ spec not found: {resolved}[/yellow]")
        console.print("[dim]  Run `redeploy init` to create it.[/dim]")


# ── devices (list known devices) ──────────────────────────────────────────────

@cli.command()
@click.option("--tag", default=None, help="Filter by tag")
@click.option("--strategy", default=None, help="Filter by strategy")
@click.option("--reachable", is_flag=True, help="Show only recently-seen devices")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def devices(tag, strategy, reachable, as_json):
    """List known devices from ~/.config/redeploy/devices.yaml.

    \b
    Example:
        redeploy devices
        redeploy devices --tag kiosk
        redeploy devices --reachable
    """
    import json as _json
    from rich.console import Console
    from rich.table import Table
    from .models import DeviceRegistry

    console = Console()
    reg = DeviceRegistry.load()
    devs = reg.devices

    if tag:
        devs = [d for d in devs if tag in d.tags]
    if strategy:
        devs = [d for d in devs if d.strategy == strategy]
    if reachable:
        devs = [d for d in devs if d.is_reachable]

    if as_json:
        print(_json.dumps([d.model_dump(mode="json") for d in devs], indent=2, default=str))
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
        t.add_row(
            d.id, d.host, d.strategy, d.app or "—",
            ",".join(d.tags) or "—", seen, ssh,
        )
    console.print(t)
    console.print(f"\n  [dim]{len(devs)} device(s)  •  registry: {DeviceRegistry.default_path()}[/dim]")


# ── scan (discover devices on local network) ──────────────────────────────────

@cli.command()
@click.option("--subnet", default=None, help="CIDR to scan, e.g. 192.168.1.0/24 (auto-detect if omitted)")
@click.option("--user", "ssh_users", multiple=True, default=None,
              help="SSH user(s) to try (repeatable). Default: current user + root + pi + ubuntu")
@click.option("--port", "ssh_port", default=22, show_default=True, help="SSH port")
@click.option("--ping", is_flag=True, help="Active ICMP ping sweep (sends packets)")
@click.option("--no-mdns", is_flag=True, help="Disable mDNS discovery")
@click.option("--timeout", default=5, show_default=True, help="Per-host SSH timeout (seconds)")
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
    from rich.console import Console
    from rich.table import Table
    from .discovery import discover, update_registry
    from .models import DeviceRegistry

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
    console.print(f"  found {len(found)} host(s), {len(ssh_ok)} SSH-accessible\n")

    t = Table(show_header=True, box=None, padding=(0, 2))
    t.add_column("IP")
    t.add_column("Hostname", style="dim")
    t.add_column("MAC", style="dim")
    t.add_column("SSH user", style="cyan")
    t.add_column("Source", style="dim")
    for h in found:
        ssh_col = f"[green]{h.ssh_user}[/green]" if h.ssh_ok else "[red]✗[/red]"
        t.add_row(h.ip, h.hostname or "—", h.mac or "—", ssh_col, h.source)
    console.print(t)

    if not no_save and ssh_ok:
        reg = update_registry(found, save=True)
        console.print(f"\n  [dim]registry updated → {DeviceRegistry.default_path()}[/dim]")
        console.print(f"  [dim]{len(reg.devices)} device(s) total[/dim]")
    elif not ssh_ok:
        console.print("\n  [dim]No SSH-accessible devices — nothing saved.[/dim]")


# ── device add/remove ─────────────────────────────────────────────────────────

@cli.command("device-add")
@click.argument("host")
@click.option("--id", "device_id", default=None, help="Device ID (default: host)")
@click.option("--name", default="", help="Human-friendly label")
@click.option("--tag", "tags", multiple=True, help="Tag (repeatable)")
@click.option("--strategy", default="docker_full", show_default=True,
              type=click.Choice(["docker_full", "podman_quadlet", "native_kiosk",
                                 "docker_kiosk", "k3s", "systemd"]),
              help="Deploy strategy")
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
    from rich.console import Console
    from datetime import datetime
    from .models import DeviceRegistry, KnownDevice

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
    console.print(f"[green]✓[/green] device [bold]{did}[/bold] saved → {DeviceRegistry.default_path()}")


@cli.command("device-rm")
@click.argument("device_id")
def device_rm(device_id):
    """Remove a device from the registry."""
    from rich.console import Console
    from .models import DeviceRegistry

    console = Console()
    reg = DeviceRegistry.load()
    if reg.remove(device_id):
        reg.save()
        console.print(f"[green]✓[/green] removed {device_id}")
    else:
        console.print(f"[yellow]⚠ not found: {device_id}[/yellow]")


# ── target (deploy spec to a specific registered device) ─────────────────────

@cli.command()
@click.argument("device_id")
@click.argument("spec_file", default=None, required=False, type=click.Path(), metavar="SPEC")
@click.option("--dry-run", is_flag=True)
@click.option("--plan-only", is_flag=True)
@click.option("--detect", "do_detect", is_flag=True)
@click.option("--plan-out", default=None, type=click.Path())
def target(device_id, spec_file, dry_run, plan_only, do_detect, plan_out):
    """Deploy a spec to a specific registered device.

    DEVICE_ID is looked up in ~/.config/redeploy/devices.yaml.
    Device's host, strategy, app, domain are overlaid onto the spec.

    \b
    Example:
        redeploy target pi@192.168.1.42
        redeploy target pi@192.168.1.42 migration.yaml --dry-run
        redeploy target kiosk-01 --detect --plan-only
    """
    from rich.console import Console

    console = Console()

    # Resolve device
    dev, reg = _resolve_device(console, device_id)

    # Resolve spec
    spec, manifest = _load_spec_with_manifest(console, spec_file, dev)

    # Overlay device values onto spec
    if dev:
        _overlay_device_onto_spec(spec, dev, console)
    else:
        spec.source.host = device_id
        spec.target.host = device_id
        console.print(f"[bold]target[/bold]  {device_id}")

    # Run detect if requested and generate plan
    planner = _run_detect_for_spec(console, spec, do_detect)

    console.print(f"\n[bold]plan[/bold]")
    migration = planner.run()
    _print_plan_table(console, migration)

    if plan_out:
        planner.save(migration, Path(plan_out))
        console.print(f"  [dim]plan saved → {plan_out}[/dim]")

    if plan_only:
        console.print("\n[dim]--plan-only: stopping before apply[/dim]")
        return

    # Pass ssh_key from registry to executor
    ssh_key = dev.ssh_key if dev else ""
    ok = _run_apply(console, migration, dry_run, output=None, ssh_key=ssh_key or "")

    # Record deploy in registry
    if dev and not dry_run:
        from .models import DeployRecord
        dev.record_deploy(DeployRecord(
            spec_name=spec.name,
            from_strategy=spec.source.strategy.value,
            to_strategy=spec.target.strategy.value,
            version=spec.target.version or "",
            ok=ok,
        ))
        dev.app = spec.target.app
        dev.strategy = spec.target.strategy.value
        reg.upsert(dev)
        reg.save()

    if not ok:
        sys.exit(1)


# ── probe (autonomous device discovery + registry) ────────────────────────────

@cli.command()
@click.argument("hosts", nargs=-1, required=False)
@click.option("--subnet", default=None,
              help="Scan subnet for new devices first (e.g. 192.168.1.0/24)")
@click.option("--user", "users", multiple=True,
              help="SSH user(s) to try (in addition to defaults)")
@click.option("--port", "ssh_port", default=22, show_default=True)
@click.option("--app", "app_hint", default="", help="App name hint (stored in registry)")
@click.option("--timeout", default=6, show_default=True,
              help="SSH timeout per attempt (seconds)")
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
    from rich.console import Console
    from rich.table import Table
    from .discovery import auto_probe, ProbeResult, discover, update_registry

    console = Console()
    all_ips: list[str] = list(hosts)

    # Optional subnet scan to find more hosts
    if subnet:
        console.print(f"[bold]scan[/bold]  {subnet}  (ARP+ping sweep)...")
        found = discover(subnet=subnet, ping=True, mdns=False, probe_ssh=False, timeout=3)
        new_ips = [h.ip for h in found if h.ip not in all_ips]
        if new_ips:
            console.print(f"  found {len(new_ips)} host(s) on {subnet}: "
                          + ", ".join(new_ips[:6]) + ("…" if len(new_ips) > 6 else ""))
            all_ips.extend(new_ips)

    if not all_ips:
        console.print("[yellow]No hosts specified. Use: redeploy probe IP [IP...] or --subnet CIDR[/yellow]")
        return

    extra_users = list(users) if users else []
    results: list[ProbeResult] = []

    console.print(f"[bold]probe[/bold]  {len(all_ips)} host(s)  "
                  f"(keys: {__import__('pathlib').Path.home() / '.ssh'}  "
                  f"timeout: {timeout}s)")

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
            key_label = __import__("os").path.basename(r.ssh_key) if r.ssh_key else "agent"
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
        console.print(f"  [dim]registry updated → {__import__('pathlib').Path.home() / '.config/redeploy/devices.yaml'}[/dim]")
        # Print table of saved devices
        from .models import DeviceRegistry
        reg = DeviceRegistry.load()
        t = Table(show_header=True, box=None, padding=(0, 2))
        t.add_column("ID", style="bold")
        t.add_column("Strategy", style="cyan")
        t.add_column("App")
        t.add_column("Arch", style="dim")
        t.add_column("OS", style="dim")
        t.add_column("Key", style="dim")
        for r in ok:
            dev = reg.get(r.host) or reg.get(r.ip)
            key_label = __import__("os").path.basename(r.ssh_key) if r.ssh_key else "agent"
            t.add_row(
                r.host, r.strategy, r.app or "—",
                r.arch or "—", r.os_info[:30] if r.os_info else "—",
                key_label,
            )
        console.print()
        console.print(t)
        console.print(f"\n  Use [bold]redeploy target {ok[0].host}[/bold] to deploy.")


# ── import ────────────────────────────────────────────────────────────────────

@cli.command(name="import")
@click.argument("source", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, type=click.Path(),
              help="Output migration.yaml path (default: <source-stem>.migration.yaml)")
@click.option("--target-host", default=None,
              help="Target SSH host (user@host) to embed in migration.yaml")
@click.option("--target-strategy", default=None,
              help="Override detected strategy (e.g. docker_full, podman_quadlet)")
@click.option("--dry-run", is_flag=True,
              help="Parse and display result without writing output file")
@click.option("--format", "out_format", default="yaml",
              type=click.Choice(["yaml", "json", "summary"]), show_default=True,
              help="Output format")
@click.option("--parser", default=None,
              help="Force specific parser (e.g. docker_compose). Default: auto-detect")
def import_cmd(source, output, target_host, target_strategy, dry_run, out_format, parser):
    """Parse an IaC/CI-CD file and produce a migration.yaml scaffold.

    Auto-detects format from filename. Supports docker-compose.yml (Tier 1).
    GitHub Actions, Kubernetes, GitLab CI, Ansible coming in Tier 1–2.

    \b
    Examples:
        redeploy import docker-compose.yml
        redeploy import docker-compose.yml -o migration.yaml
        redeploy import docker-compose.yml --target-host root@vps.example.com
        redeploy import . --dry-run               # parse whole directory
        redeploy import docker-compose.yml --format summary
    """
    import json as _json
    from rich.console import Console
    from rich.table import Table
    from .iac import parse_file, parse_dir, parser_registry

    console = Console()
    src_path = Path(source)

    # ── parse ─────────────────────────────────────────────────────────────────
    if parser:
        p = next((p for p in parser_registry._parsers if p.name == parser), None)
        if not p:
            console.print(f"[red]✗ Unknown parser '{parser}'. "
                          f"Known: {parser_registry.registered}[/red]")
            sys.exit(1)
        specs = [p.parse(src_path)]
    elif src_path.is_dir():
        specs = parse_dir(src_path)
        if not specs:
            console.print(f"[yellow]No recognised IaC files found in {source}[/yellow]")
            console.print(f"  Registered parsers: {parser_registry.registered}")
            return
    else:
        try:
            specs = [parse_file(src_path)]
        except ValueError as e:
            console.print(f"[red]✗ {e}[/red]")
            console.print(f"  Registered parsers: {parser_registry.registered}")
            sys.exit(1)

    console.print(f"[bold]import[/bold]  {source}  "
                  f"({len(specs)} file(s) parsed)")

    # ── display ───────────────────────────────────────────────────────────────
    for spec in specs:
        _print_import_spec(console, spec)

    if dry_run:
        console.print("\n[dim][DRY RUN] No file written.[/dim]")
        return

    if out_format == "summary":
        return

    # ── convert + write ───────────────────────────────────────────────────────
    for spec in specs:
        out_path = Path(output) if output else _default_output(src_path, spec)
        try:
            migration_data = _spec_to_migration_yaml(
                spec,
                target_host=target_host,
                target_strategy=target_strategy,
            )
        except Exception as exc:
            console.print(f"[red]✗ Conversion error: {exc}[/red]")
            sys.exit(1)

        if out_format == "json":
            import json as _j
            out_path = out_path.with_suffix(".json")
            out_path.write_text(_j.dumps(migration_data, indent=2, ensure_ascii=False))
        else:
            out_path.write_text(yaml.dump(migration_data, default_flow_style=False,
                                          allow_unicode=True, sort_keys=False))

        console.print(f"\n  [green]✓[/green] written → [bold]{out_path}[/bold]")
        if spec.warnings:
            for w in spec.warnings:
                icon = {"error": "✗", "warn": "⚠", "info": "ℹ"}.get(w.severity, "?")
                color = {"error": "red", "warn": "yellow", "info": "dim"}.get(w.severity, "dim")
                console.print(f"  [{color}]{icon} {w}[/{color}]")


def _print_import_spec(console, spec) -> None:
    """Print a ParsedSpec summary to the Rich console."""
    from rich.table import Table

    status_color = "green" if spec.confidence >= 0.8 else "yellow" if spec.confidence >= 0.5 else "red"
    console.print(
        f"\n  [bold]{spec.source_file.name}[/bold]  "
        f"[cyan]{spec.source_format}[/cyan]  "
        f"[{status_color}]{spec.confidence:.0%}[/{status_color}]"
    )

    if spec.services:
        t = Table(show_header=True, box=None, padding=(0, 2))
        t.add_column("Service", style="bold")
        t.add_column("Image")
        t.add_column("Ports", style="cyan")
        t.add_column("Volumes", style="dim")
        t.add_column("Restart", style="dim")
        for svc in spec.services:
            ports_str = ", ".join(str(p) for p in svc.ports[:3])
            if len(svc.ports) > 3:
                ports_str += f" (+{len(svc.ports) - 3})"
            vols_str = str(len(svc.volumes)) if svc.volumes else "—"
            t.add_row(
                svc.name,
                svc.image or f"[dim]build:{svc.build_context or '.'}[/dim]",
                ports_str or "—",
                vols_str,
                svc.restart or "—",
            )
        console.print(t)

    if spec.networks:
        console.print(f"  networks: {', '.join(spec.networks)}")
    if spec.runtime_hints:
        console.print(f"  runtime:  {', '.join(spec.runtime_hints)}")
    if spec.secrets_referenced:
        console.print(f"  [dim]secrets referenced: {', '.join(spec.secrets_referenced)}[/dim]")


def _default_output(src: Path, spec) -> Path:
    if src.is_dir():
        return src / "migration.yaml"
    stem = src.stem.replace("docker-compose", "migration").replace("compose", "migration")
    if stem == src.stem:
        stem = f"{src.stem}.migration"
    return src.parent / f"{stem}.yaml"


def _spec_to_migration_yaml(spec, *, target_host: str = None,
                             target_strategy: str = None) -> dict:
    """Minimal ParsedSpec → migration.yaml dict (scaffold, not final plan).

    Produces a starting point the user edits further.  Lossy fields are
    noted as YAML comments via the description strings.
    """
    services = []
    for svc in spec.services:
        entry: dict = {"name": svc.name}
        if svc.image:
            entry["image"] = svc.image
        if svc.ports:
            entry["ports"] = [str(p) for p in svc.ports]
        if svc.volumes:
            entry["volumes"] = [
                f"{v.source}:{v.target}" if v.source else v.target
                for v in svc.volumes
            ]
        if svc.env:
            entry["environment"] = svc.env
        if svc.env_files:
            entry["env_file"] = svc.env_files
        if svc.depends_on:
            entry["depends_on"] = svc.depends_on
        if svc.restart:
            entry["restart"] = svc.restart
        if svc.replicas > 1:
            entry["replicas"] = svc.replicas
        services.append(entry)

    data: dict = {
        "app": spec.source_file.stem,
        "source": str(spec.source_file),
        "source_format": spec.source_format,
        "confidence": round(spec.confidence, 2),
    }

    if target_host:
        data["host"] = target_host
    if target_strategy:
        data["strategy"] = target_strategy
    elif spec.runtime_hints:
        hint_map = {"docker": "docker_full", "podman": "podman_quadlet",
                    "k3s": "k3s", "systemd": "systemd"}
        for hint in spec.runtime_hints:
            if hint in hint_map:
                data["strategy"] = hint_map[hint]
                break

    data["services"] = services

    if spec.networks:
        data["networks"] = spec.networks
    if spec.secrets_referenced:
        data["secrets_referenced"] = spec.secrets_referenced

    if spec.warnings:
        data["import_warnings"] = [str(w) for w in spec.warnings]

    return data


# ── diff (stub — Phase 3) ─────────────────────────────────────────────────────

@cli.command()
@click.option("--ci", "ci_file", default=None, type=click.Path(exists=True),
              help="IaC/CI file to compare (docker-compose, GHA workflow, …)")
@click.option("--host", default=None,
              help="Live host to compare against (user@host)")
@click.option("--from", "from_src", default=None, type=click.Path(exists=True),
              help="Left side: IaC file or directory")
@click.option("--to", "to_src", default=None,
              help="Right side: IaC file/directory or SSH host")
@click.option("--format", "out_format", default="text",
              type=click.Choice(["text", "json"]), show_default=True)
def diff(ci_file, host, from_src, to_src, out_format):
    """Compare IaC file vs live host (drift detection).  [Phase 3 — coming soon]

    \b
    Examples:
        redeploy diff --ci docker-compose.yml --host root@prod
        redeploy diff --from docker-compose.yml --to root@prod
    """
    from rich.console import Console
    console = Console()
    console.print("[yellow]⚠ redeploy diff is not yet implemented (Phase 3).[/yellow]")
    console.print("  Planned: compare IaC file vs live SSH probe for drift detection.")
    console.print("  Use [bold]redeploy import[/bold] to parse IaC files for now.")

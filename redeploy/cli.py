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


def _run_apply(console, migration, dry_run, output) -> bool:
    from .apply import Executor

    prefix = "[DRY RUN] " if dry_run else ""
    console.print(f"\n[bold]{prefix}apply[/bold]")
    executor = Executor(migration, dry_run=dry_run)
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


# ── detect ────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--host", required=True, help="SSH host (user@ip) or 'local'")
@click.option("--app", default="c2004", show_default=True, help="Application name")
@click.option("--domain", default=None, help="Public domain for HTTP health checks")
@click.option("-o", "--output", default="infra.yaml", show_default=True,
              type=click.Path(), help="Output file for InfraState")
@click.pass_context
def detect(ctx, host, app, domain, output):
    """Probe infrastructure and produce infra.yaml."""
    from rich.console import Console
    from rich.table import Table
    from .detect import Detector

    console = Console()
    out_path = Path(output)

    try:
        d = Detector(host=host, app=app, domain=domain)
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
@click.option("--app", default="c2004", show_default=True)
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
    from .models import TargetConfig

    console = Console()

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
@click.pass_context
def run(ctx, spec_file, dry_run, plan_only, do_detect, plan_out, output):
    """Execute migration from a single YAML spec (source + target in one file).

    SPEC defaults to migration.yaml (or value from redeploy.yaml manifest).

    \b
    Example:
        redeploy run                        # uses redeploy.yaml + migration.yaml
        redeploy run examples/k3s-to-docker.yaml
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

    # overlay manifest values (host, domain, remote_dir, ssh_key)
    if manifest:
        manifest.apply_to_spec(spec)
        console.print(f"[dim]manifest: {_find_manifest_path()}[/dim]")

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

    if not _run_apply(console, migration, dry_run, output):
        sys.exit(1)


# ── helper ────────────────────────────────────────────────────────────────────

def _find_manifest_path() -> str:
    for d in [Path.cwd()] + list(Path.cwd().parents):
        c = d / "redeploy.yaml"
        if c.exists():
            return str(c)
    return "redeploy.yaml"


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

"""plan, apply, migrate, run commands — Migration planning and execution."""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ..core import (
    load_spec_or_exit,
    find_manifest_path,
    run_detect_for_spec,
    resolve_device,
    load_spec_with_manifest,
    overlay_device_onto_spec,
)
from ..display import print_plan_table


@click.command()
@click.option(
    "--infra", default="infra.yaml", show_default=True,
    type=click.Path(exists=True), help="InfraState file (from detect)"
)
@click.option(
    "--target", default=None, type=click.Path(),
    help="Target config YAML (desired state)"
)
@click.option(
    "--strategy", default=None,
    type=click.Choice(["docker_full", "podman_quadlet", "k3s", "native_kiosk", "systemd"]),
    help="Override target strategy"
)
@click.option("--domain", default=None, help="Public domain for verify step")
@click.option("--version", "target_version", default=None, help="Target version to verify")
@click.option("--compose", multiple=True, help="Compose file(s) for docker_full strategy")
@click.option("--env-file", default=None, help="Env file path")
@click.option(
    "-o", "--output", default="migration-plan.yaml", show_default=True,
    type=click.Path(), help="Output migration plan file"
)
@click.pass_context
def plan(ctx, infra, target, strategy, domain, target_version, compose, env_file, output):
    """Generate migration-plan.yaml from infra.yaml + target config."""
    from ...models import DeployStrategy
    from ...plan import Planner

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

    console.print(
        f"\n[bold]Migration plan: {migration.from_strategy.value} → {migration.to_strategy.value}[/bold]"
    )
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


@click.command()
@click.option(
    "--plan", "plan_file", default="migration-plan.yaml", show_default=True,
    type=click.Path(exists=True), help="Migration plan file"
)
@click.option("--dry-run", is_flag=True, help="Show steps without executing")
@click.option("--step", default=None, help="Run only a specific step by ID")
@click.option(
    "-o", "--output", default=None, type=click.Path(),
    help="Save results to file after apply"
)
@click.pass_context
def apply(ctx, plan_file, dry_run, step, output):
    """Execute a migration plan."""
    from ...apply import Executor

    console = Console()
    executor = Executor.from_file(Path(plan_file))

    if step:
        matched = [s for s in executor.plan.steps if s.id == step]
        if not matched:
            console.print(f"[red]Step '{step}' not found in plan[/red]")
            ids = ", ".join(s.id for s in executor.plan.steps)
            console.print(f"Available: {ids}")
            sys.exit(1)
        executor.plan.steps = matched

    executor.dry_run = dry_run

    prefix = "[DRY RUN] " if dry_run else ""
    console.print(
        f"\n{prefix}[bold]Applying: {executor.plan.from_strategy.value}"
        f" → {executor.plan.to_strategy.value}[/bold]  "
        f"({len(executor.plan.steps)} steps)"
    )

    ok = executor.run()
    console.print(f"\n{executor.summary()}")

    if output:
        executor.save_results(Path(output))

    if not ok:
        sys.exit(1)


@click.command()
@click.option("--host", required=True, help="SSH host (user@ip) or 'local'")
@click.option(
    "--app", default=None, show_default=True,
    help="Application name (default from redeploy.yaml)"
)
@click.option("--domain", default=None)
@click.option("--target", default=None, type=click.Path(), help="Target config YAML")
@click.option(
    "--strategy", default="docker_full", show_default=True,
    type=click.Choice(["docker_full", "podman_quadlet", "k3s", "native_kiosk", "systemd"])
)
@click.option("--version", "target_version", default=None)
@click.option("--compose", multiple=True)
@click.option("--env-file", default=None)
@click.option("--dry-run", is_flag=True)
@click.option(
    "--infra-out", default="infra.yaml", show_default=True, type=click.Path()
)
@click.option(
    "--plan-out", default="migration-plan.yaml", show_default=True, type=click.Path()
)
@click.pass_context
def migrate(ctx, host, app, domain, target, strategy, target_version,
            compose, env_file, dry_run, infra_out, plan_out):
    """Full pipeline: detect → plan → apply."""
    from ...models import ProjectManifest, DeployStrategy
    from ...detect import Detector
    from ...plan import Planner
    from ...apply import Executor

    console = Console()

    manifest = ProjectManifest.find_and_load(Path.cwd())
    app = app or (manifest.app if manifest else "c2004")
    domain = domain or (manifest.domain if manifest else None)

    # 1. detect
    console.print(f"\n[bold]Step 1/3 — detect[/bold]")
    d = Detector(host=host, app=app, domain=domain)
    state = d.run()
    d.save(state, Path(infra_out))
    console.print(
        f"  Strategy: {state.detected_strategy}  "
        f"  Version: {state.current_version or '?'}  "
        f"  Conflicts: {len(state.conflicts)}"
    )

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
    console.print(
        f"  Steps: {len(migration.steps)}  Risk: {migration.risk.value}  "
        f"Downtime: {migration.estimated_downtime}"
    )

    # 3. apply
    console.print(f"\n[bold]Step 3/3 — apply{'  (dry-run)' if dry_run else ''}[/bold]")
    executor = Executor(migration, dry_run=dry_run)
    ok = executor.run()
    console.print(f"\n{executor.summary()}")

    if not ok:
        sys.exit(1)


@click.command()
@click.argument("spec_file", default=None, required=False, type=click.Path(), metavar="SPEC")
@click.option("--dry-run", is_flag=True, help="Show steps without executing")
@click.option("--plan-only", is_flag=True, help="Generate plan but do not apply")
@click.option(
    "--detect", "do_detect", is_flag=True,
    help="Run live detect first (overrides source state from spec)"
)
@click.option("--plan-out", default=None, type=click.Path(), help="Save generated plan to file")
@click.option(
    "-o", "--output", default=None, type=click.Path(), help="Save apply results to file"
)
@click.option(
    "--env", "env_name", default="",
    help="Named environment from redeploy.yaml (e.g. prod, dev, rpi5)"
)
@click.option(
    "--progress-yaml", is_flag=True, help="Emit machine-readable YAML progress events to stdout"
)
@click.option(
    "--resume", is_flag=True,
    help="Skip steps already completed in the persisted checkpoint "
         "(under .redeploy/state/) and continue from the first pending step."
)
@click.option("--from-step", "from_step", default=None, help="Force start from this step id")
@click.option(
    "--state-file", default=None, type=click.Path(),
    help="Override the path of the checkpoint file."
)
@click.option("--no-state", is_flag=True, help="Disable checkpoint persistence for this run.")
@click.option(
    "--heal/--no-heal", default=True,
    help="Self-healing: on failure, collect diagnostics and ask LLM to fix the spec, then retry (default: on)."
)
@click.option(
    "--fix", "fix_hint", default=None, metavar="TEXT",
    help='Report a known problem to guide the LLM, e.g. --fix "brak ikon SVG w menu"'
)
@click.option(
    "--max-heal-retries", default=3, show_default=True,
    help="Maximum number of LLM self-healing attempts."
)
@click.option(
    "--lint/--no-lint", default=True, show_default=True,
    help="Run static analysis before deployment to catch missing files, broken references, and external path issues."
)
@click.option(
    "--preflight/--no-preflight", default=True, show_default=True,
    help="Generate operational preflight schema (resolved refs/paths/dependencies) before apply."
)
@click.option(
    "--preflight-schema-out",
    default=".redeploy/preflight-schema.yaml",
    show_default=True,
    type=click.Path(),
    help="Output path for generated preflight schema snapshot."
)
@click.option(
    "--preflight-remote/--no-preflight-remote", default=True, show_default=True,
    help="Include best-effort remote host checks (SSH + referenced remote paths) in preflight schema."
)
@click.option(
    "--strict-preflight/--no-strict-preflight", default=True, show_default=True,
    help="Abort before apply when preflight reports blockers."
)
@click.pass_context
def run(ctx, spec_file, dry_run, plan_only, do_detect, plan_out, output,
        env_name, progress_yaml, resume, from_step, state_file, no_state,
        heal, fix_hint, max_heal_retries, lint,
        preflight, preflight_schema_out, preflight_remote, strict_preflight):
    """Execute migration from a single YAML spec (source + target in one file).

    SPEC defaults to migration.yaml (or value from redeploy.yaml manifest).

    \b
    Example:
        redeploy run                              # uses redeploy.yaml + migration.yaml
        redeploy run --env prod                   # use prod environment from redeploy.yaml
        redeploy run --env rpi5 --detect          # deploy to rpi5 env with live probe
        redeploy run migration.yaml --dry-run
        redeploy run migration.yaml --detect --plan-out plan.yaml
        redeploy run migration.yaml --no-heal     # disable self-healing
        redeploy run migration.yaml --fix "brak ikon SVG w menu"  # hint for LLM
    """
    from ...models import ProjectManifest
    from ...plan import Planner
    from ...plugins import load_user_plugins
    from ...apply import Executor

    console = Console()

    # Load project manifest (redeploy.yaml) if present
    manifest = ProjectManifest.find_and_load(Path.cwd())

    # Resolve spec file: arg > manifest.spec > "migration.yaml"
    resolved_spec = spec_file or (manifest.spec if manifest else "migration.yaml")
    if not Path(resolved_spec).exists():
        console.print(f"[red]✗ spec file not found: {resolved_spec}[/red]")
        console.print("[dim]  Create one with: redeploy init[/dim]")
        sys.exit(1)

    spec = load_spec_or_exit(console, resolved_spec)

    # Overlay manifest values
    _apply_manifest_to_spec(console, manifest, spec, env_name)
    _print_spec_summary(console, spec)

    # Static analysis (lint)
    lint_result = None
    if lint:
        from ...analyze import SpecAnalyzer, IssueSeverity
        analyzer = SpecAnalyzer(base_dir=Path.cwd())
        _, lint_result = analyzer.analyze_file(Path(resolved_spec))
        if lint_result.issues:
            console.print(f"\n[bold]lint[/bold]")
            for i in lint_result.issues:
                color = "red" if i.severity == IssueSeverity.ERROR else "yellow"
                prefix = f"[{color}]{i.severity.value}[/{color}]"
                step = f" ({i.step_id})" if i.step_id else ""
                console.print(f"  {prefix}{step} {i.category}: {i.message}")
                if i.suggestion:
                    console.print(f"      [dim]→ {i.suggestion}[/dim]")
            if not lint_result.passed:
                console.print("\n[red]✗ lint failed — fix errors above or use --no-lint to skip.[/red]")
                sys.exit(1)
            else:
                console.print(f"[yellow]⚠ lint passed with {len(lint_result.warnings())} warning(s)[/yellow]")
        else:
            console.print("[green]  ✓ lint passed[/green]")

    # Optional live detect
    if do_detect:
        planner = _perform_live_detect(console, spec)
    else:
        planner = Planner.from_spec(spec)

    # Plan
    console.print(f"\n[bold]plan[/bold]")
    migration = planner.run()

    if plan_out:
        planner.save(migration, Path(plan_out))
        console.print(f"  [dim]plan saved → {plan_out}[/dim]")

    print_plan_table(console, migration)

    # Operational preflight schema (resolved refs/paths/deps) + optional strict gate
    if preflight:
        from ...analyze import generate_preflight_schema, save_preflight_schema

        preflight_result = generate_preflight_schema(
            spec_path=Path(resolved_spec),
            spec=spec,
            migration=migration,
            lint_result=lint_result,
            base_dir=Path.cwd(),
            remote_check=bool(preflight_remote and not dry_run),
        )
        save_preflight_schema(preflight_result.schema, Path(preflight_schema_out))

        blockers = len(preflight_result.blockers)
        console.print(f"\n[bold]preflight[/bold]  [dim]schema saved → {preflight_schema_out}[/dim]")
        if blockers:
            console.print(f"[yellow]⚠ preflight blockers: {blockers}[/yellow]")
            for b in preflight_result.blockers[:10]:
                sid = f" ({b.get('step_id')})" if b.get("step_id") else ""
                console.print(f"  [yellow]- {b.get('type')}{sid}: {b.get('message')}[/yellow]")
            if blockers > 10:
                console.print(f"  [dim]... and {blockers - 10} more blockers in schema file[/dim]")
            if strict_preflight:
                console.print("\n[red]✗ strict preflight failed — aborting before apply[/red]")
                sys.exit(1)
        else:
            console.print("[green]  ✓ preflight passed (no blockers)[/green]")

    if plan_only:
        console.print("\n[dim]--plan-only: stopping before apply[/dim]")
        return

    # Apply
    load_user_plugins()

    # Self-healing mode
    if heal and not dry_run:
        _load_dotenv()
        from ...heal import HealRunner
        _print_heal_banner(console, fix_hint)
        # Detect project version for repair log
        version = _detect_project_version(resolved_spec)
        runner = HealRunner(
            migration=migration,
            spec_path=resolved_spec,
            host=migration.host,
            fix_hint=fix_hint or "",
            max_retries=max_heal_retries,
            dry_run=dry_run,
            console=console,
            version=version,
            progress_yaml=progress_yaml,
            resume=resume,
            from_step=from_step,
            state_file=state_file,
            no_state=no_state,
        )
        ok = runner.run()
    else:
        ok = _run_apply(
            console, migration, dry_run, output,
            progress_yaml=progress_yaml,
            resume=resume,
            from_step=from_step,
            state_file=state_file,
            no_state=no_state,
            spec_path=str(resolved_spec)
        )

    if not ok:
        sys.exit(1)


def _apply_manifest_to_spec(console, manifest, spec, env_name) -> None:
    """Apply manifest values to spec."""
    from ...models import ProjectManifest

    if manifest:
        if env_name and env_name not in manifest.environments:
            console.print(
                f"[yellow]⚠ env '{env_name}' not in redeploy.yaml — known: "
                f"{', '.join(manifest.environments) or 'none'}[/yellow]"
            )
        manifest.apply_to_spec(spec, env_name=env_name)
        env_label = f" [cyan][env: {env_name}][/cyan]" if env_name else ""
        console.print(f"[dim]manifest: {find_manifest_path()}{env_label}[/dim]")
    elif not env_name:
        dotenv_manifest = ProjectManifest.from_dotenv(Path.cwd())
        if dotenv_manifest:
            dotenv_manifest.apply_to_spec(spec)
            console.print("[dim]manifest: .env (DEPLOY_* vars)[/dim]")


def _print_spec_summary(console, spec) -> None:
    """Print spec summary."""
    console.print(
        f"\n[bold]{spec.name}[/bold]"
        + (f"  [dim]{spec.description}[/dim]" if spec.description else "")
    )
    console.print(
        f"  [dim]{spec.source.strategy.value}[/dim]  →  "
        f"[bold]{spec.target.strategy.value}[/bold]"
        f"  ({spec.source.host})"
    )


def _perform_live_detect(console, spec):
    """Run live detect and return planner."""
    from ...detect import Detector
    from ...plan import Planner

    console.print(f"\n[bold]detect[/bold]  (live probe of {spec.source.host})")
    d = Detector(
        host=spec.source.host,
        app=spec.source.app,
        domain=spec.source.domain,
    )
    state = d.run()
    console.print(
        f"  detected: {state.detected_strategy}  "
        f"version={state.current_version or '?'}  "
        f"conflicts={len(state.conflicts)}"
    )
    planner = Planner(state, spec.to_target_config())
    planner._spec = spec
    return planner


def _run_apply(
    console,
    migration,
    dry_run,
    output,
    ssh_key: str = "",
    progress_yaml: bool = False,
    resume: bool = False,
    from_step: str | None = None,
    state_file: str | None = None,
    no_state: bool = False,
    spec_path: str | None = None,
) -> bool:
    """Run apply with given options."""
    from ...apply import Executor

    prefix = "[DRY RUN] " if dry_run else ""
    console.print(f"\n[bold]{prefix}apply[/bold]")

    state_path = Path(state_file) if state_file else None
    if no_state:
        state_path = Path("/dev/null")

    executor = Executor(
        migration,
        dry_run=dry_run,
        ssh_key=ssh_key or None,
        progress_yaml=progress_yaml,
        resume=resume,
        from_step=from_step,
        state_path=state_path if not no_state else None,
        spec_path=spec_path,
    )
    if no_state:
        executor._state = None
        executor._state_path = None

    if resume and executor.state is not None and executor.state.completed_count:
        console.print(
            f"[cyan]resume:[/cyan] {executor.state.completed_count}/"
            f"{executor.state.total_steps} step(s) already done"
            + (f" — last failure: {executor.state.failed_step_id}"
               if executor.state.failed_step_id else "")
        )
    elif resume:
        console.print("[dim]resume: no prior checkpoint, running from start[/dim]")

    ok = executor.run()
    console.print(f"\n{executor.summary()}")

    if output:
        executor.save_results(Path(output))

    return ok


def _load_dotenv() -> None:
    """Load .env from project dir or home .redeploy dir if present."""
    try:
        from dotenv import load_dotenv
        for candidate in [Path(".env"), Path.home() / ".redeploy" / ".env"]:
            if candidate.exists():
                load_dotenv(candidate, override=False)
                break
    except ImportError:
        pass


def _detect_project_version(spec_path: str) -> str:
    """Try to read VERSION file adjacent to spec, or return empty string."""
    for p in [Path(spec_path).parent / "VERSION",
              Path(spec_path).parent.parent / "VERSION",
              Path("VERSION")]:
        if p.exists():
            return p.read_text().strip()
    return ""


def _print_heal_banner(console, fix_hint: str | None) -> None:
    console.print("\n[bold green]heal[/bold green] mode: [dim]on[/dim]")
    if fix_hint:
        console.print(f"[cyan]user hint:[/cyan] {fix_hint}")

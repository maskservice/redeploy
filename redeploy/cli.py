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
    from .plugins import load_user_plugins

    load_user_plugins()

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


def _run_detect_workflow(console, hosts, manifest, app, scan_subnet, deep, save_yaml, fmt="yaml"):
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

    # ── Generated output (yaml or css) ───────────────────────────────────────
    if result.reachable:
        if fmt == "css":
            from .dsl.loader import manifest_to_css, templates_to_css
            from .detect.templates import TEMPLATES
            gen_manifest = result.reachable[0].template_result  # use detected info
            # Build a manifest from WorkflowResult
            from .models import ProjectManifest, EnvironmentConfig
            envs = {}
            for h in result.reachable:
                cfg = EnvironmentConfig(
                    host=h.host,
                    strategy=h.strategy.value,
                    verify_url=(h.state.health[0].url if h.state and h.state.health else None),
                    ssh_key=h.ssh_key or None,
                )
                envs[h.environment] = cfg
            tmp_manifest = ProjectManifest(app=app, environments=envs)
            css_out = manifest_to_css(tmp_manifest, app=app)
            css_out += "\n\n" + templates_to_css(
                [h.template_result.best.template for h in result.reachable if h.template_result]
            )
            console.print(f"\n[bold]generated redeploy.css:[/bold]")
            console.print(css_out)
            if save_yaml:
                Path(save_yaml).write_text(css_out)
                console.print(f"  [dim]saved → {save_yaml}[/dim]")
        else:
            yaml_out = result.generated_redeploy_yaml()
            console.print(f"\n[bold]generated redeploy.yaml:[/bold]")
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
              help="Workflow: save generated manifest to file")
@click.option("--format", "output_fmt", default="yaml",
              type=click.Choice(["yaml", "css"]),
              help="Output format for generated manifest (yaml or css)")
@click.pass_context
def detect(ctx, host, app, domain, output, run_workflow, scan_subnet, no_deep, save_yaml, output_fmt):
    """Probe infrastructure and produce infra.yaml.

    With --workflow: multi-host detection with template scoring.
    Reads hosts from redeploy.yaml / redeploy.css environments + registry + --scan.

    \b
    Examples:
        redeploy detect --host pi@192.168.188.108
        redeploy detect --workflow
        redeploy detect --workflow --format css --save-yaml redeploy.css
        redeploy detect --workflow --scan 192.168.188.0/24
        redeploy detect --workflow --no-deep
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
            fmt=output_fmt,
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


# ── inspect ───────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--file", "css_file", default=None, type=click.Path(),
              help="redeploy.css / redeploy.less file (auto-detected if omitted)")
@click.pass_context
def inspect(ctx, css_file):
    """Show parsed content of redeploy.css — environments, templates, workflows.

    Transparent view of what redeploy reads from the DSL file.
    Useful for debugging and for LLMs to understand project configuration.

    \b
    Examples:
        redeploy inspect
        redeploy inspect --file redeploy.css
    """
    from rich.console import Console
    from rich.table import Table
    from .models import ProjectManifest

    console = Console()

    if css_file:
        css_path = Path(css_file)
    else:
        css_path = ProjectManifest.find_css(Path.cwd())

    if not css_path or not css_path.exists():
        console.print("[yellow]No redeploy.css found — falling back to redeploy.yaml[/yellow]")
        manifest = ProjectManifest.find_and_load(Path.cwd())
        if not manifest:
            console.print("[red]✗ No redeploy.css or redeploy.yaml found[/red]")
            sys.exit(1)
        console.print(f"  app={manifest.app}  envs={list(manifest.environments.keys())}")
        return

    from .dsl.loader import load_css
    result = load_css(css_path)
    console.print(f"\n[bold]redeploy inspect[/bold]  [dim]{css_path}[/dim]\n")

    # ── App metadata ──────────────────────────────────────────────────────────
    if result.manifest:
        m = result.manifest
        console.print(f"[bold cyan]app[/bold cyan]  {m.app}  spec={m.spec}"
                      + (f"  domain={m.domain}" if m.domain else ""))

    # ── Environments ──────────────────────────────────────────────────────────
    if result.manifest and result.manifest.environments:
        console.print(f"\n[bold]Environments ({len(result.manifest.environments)})[/bold]")
        t = Table(show_header=True, box=None, padding=(0, 2))
        t.add_column("Name", style="cyan")
        t.add_column("Host")
        t.add_column("Strategy")
        t.add_column("Env file", style="dim")
        t.add_column("Verify URL", style="dim")
        for env_name, cfg in result.manifest.environments.items():
            t.add_row(
                env_name,
                cfg.host or "—",
                cfg.strategy or "—",
                cfg.env_file or "—",
                cfg.verify_url or "—",
            )
        console.print(t)

    # ── Templates ─────────────────────────────────────────────────────────────
    if result.templates:
        console.print(f"\n[bold]Detection Templates ({len(result.templates)})[/bold]")
        for tpl in result.templates:
            console.print(f"  [cyan]{tpl.id}[/cyan]  env=[yellow]{tpl.environment}[/yellow]"
                          f"  strategy={tpl.strategy.value}  max_score={tpl.max_score:.1f}")
            console.print(f"    conditions: "
                          + "  ".join(f"[dim]{c.description}[/dim]×{c.weight}" for c in tpl.conditions[:5]))
            if tpl.required:
                console.print(f"    required:   "
                              + "  ".join(f"[red]{r.description}[/red]" for r in tpl.required))
            if tpl.notes:
                for note in tpl.notes[:2]:
                    console.print(f"    [dim]→ {note}[/dim]")

    # ── Workflows ─────────────────────────────────────────────────────────────
    if result.workflows:
        console.print(f"\n[bold]Workflows ({len(result.workflows)})[/bold]")
        for wf in result.workflows:
            plugin_steps = [s for s in wf.steps if s.plugin_type]
            plugin_hint = (f"  [dim](plugins: "
                           + ", ".join(s.plugin_type for s in plugin_steps)
                           + ")[/dim]") if plugin_steps else ""
            console.print(f"  [cyan]{wf.name}[/cyan]  "
                          f"[dim]{wf.trigger}[/dim]  "
                          f"{len(wf.steps)} steps"
                          + (f"  [dim]{wf.description}[/dim]" if wf.description else "")
                          + plugin_hint)
            for step in wf.steps:
                if step.plugin_type:
                    params_str = "  ".join(f"{k}={v}" for k, v in step.plugin_params.items())
                    console.print(f"    step-{step.index}: [yellow]plugin[/yellow] "
                                  f"[cyan]{step.plugin_type}[/cyan]"
                                  + (f"  [dim]{params_str}[/dim]" if params_str else ""))
                else:
                    console.print(f"    step-{step.index}: [dim]{step.command[:80]}[/dim]")

    # ── Devices ───────────────────────────────────────────────────────────────
    devices = [n for n in result.raw_nodes if n.selector_type == "device"]
    if devices:
        console.print(f"\n[bold]Devices ({len(devices)})[/bold]")
        t3 = Table(show_header=True, box=None, padding=(0, 2))
        t3.add_column("Name", style="cyan")
        t3.add_column("Host")
        t3.add_column("Arch", style="dim")
        t3.add_column("Strategy", style="dim")
        t3.add_column("Description")
        for d in devices:
            t3.add_row(
                d.name,
                d.get("host", "—"),
                d.get("arch", "—"),
                d.get("expected_strategy", "—"),
                d.get("description", "—"),
            )
        console.print(t3)

    # ── Raw nodes summary ─────────────────────────────────────────────────────
    by_type: dict[str, int] = {}
    for n in result.raw_nodes:
        by_type[n.selector_type] = by_type.get(n.selector_type, 0) + 1
    console.print(f"\n[dim]nodes: "
                  + "  ".join(f"{t}×{c}" for t, c in sorted(by_type.items()))
                  + "[/dim]")
    console.print(f"[dim]export: redeploy export --format css  |  redeploy export --format yaml[/dim]")


# ── workflow (run named workflow from redeploy.css) ───────────────────────────

@cli.command("workflow")
@click.argument("name", required=False, default=None)
@click.option("--file", "css_file", default=None, type=click.Path(),
              help="redeploy.css file (auto-detected if omitted)")
@click.option("--dry-run", is_flag=True, help="Print steps without executing")
@click.option("--list", "list_only", is_flag=True, help="List all available workflows")
@click.pass_context
def workflow_cmd(ctx, name, css_file, dry_run, list_only):
    """Run a named workflow from redeploy.css.

    \b
    Examples:
        redeploy workflow --list
        redeploy workflow deploy:prod
        redeploy workflow deploy:rpi5 --dry-run
        redeploy workflow release
    """
    import subprocess as _sp
    from rich.console import Console
    from .models import ProjectManifest

    console = Console()

    css_path = Path(css_file) if css_file else ProjectManifest.find_css(Path.cwd())
    if not css_path or not css_path.exists():
        console.print("[red]✗ No redeploy.css found. Create one or use --file.[/red]")
        sys.exit(1)

    from .dsl.loader import load_css
    result = load_css(css_path)

    if list_only or not name:
        console.print(f"[bold]Workflows in {css_path.name}:[/bold]")
        for wf in result.workflows:
            console.print(f"  [cyan]{wf.name}[/cyan]"
                          + (f"  [dim]{wf.description}[/dim]" if wf.description else ""))
            for step in wf.steps:
                console.print(f"    step-{step.index}: [dim]{step.command[:70]}[/dim]")
        return

    wf = next((w for w in result.workflows if w.name == name), None)
    if not wf:
        available = [w.name for w in result.workflows]
        console.print(f"[red]✗ Workflow '{name}' not found.[/red]")
        console.print(f"  Available: {', '.join(available)}")
        sys.exit(1)

    console.print(f"[bold]workflow[/bold] [cyan]{wf.name}[/cyan]"
                  + (f"  [dim]{wf.description}[/dim]" if wf.description else ""))

    for step in wf.steps:
        console.print(f"\n  [dim]step-{step.index}[/dim]  {step.command}")
        if dry_run:
            continue
        ret = _sp.run(step.command, shell=True, cwd=str(css_path.parent))
        if ret.returncode != 0:
            console.print(f"  [red]✗ step-{step.index} failed (exit {ret.returncode})[/red]")
            sys.exit(ret.returncode)
        console.print(f"  [green]✓[/green]")

    if not dry_run:
        console.print(f"\n[green]✓ workflow '{wf.name}' complete[/green]")


# ── plugin ────────────────────────────────────────────────────────────────────

@cli.command("export")
@click.option("--format", "fmt", default="css",
              type=click.Choice(["css", "yaml"]),
              help="Output format (css or yaml)")
@click.option("-o", "--output", default=None, type=click.Path(),
              help="Output file (default: print to stdout)")
@click.option("--file", "src_file", default=None, type=click.Path(),
              help="Source file to convert (auto-detected if omitted)")
@click.pass_context
def export_cmd(ctx, fmt, output, src_file):
    """Convert between redeploy.css and redeploy.yaml formats.

    Reads the nearest redeploy.css or redeploy.yaml and exports to the
    requested format. Useful for migration, sharing, and LLM inspection.

    \b
    Examples:
        redeploy export --format css            # yaml → css (stdout)
        redeploy export --format css -o redeploy.css
        redeploy export --format yaml -o redeploy.yaml
        redeploy export --format yaml --file redeploy.css
    """
    from rich.console import Console
    from .models import ProjectManifest
    from .dsl.loader import load_css, manifest_to_css, templates_to_css

    console = Console(stderr=True)

    if src_file:
        src = Path(src_file)
    else:
        src = ProjectManifest.find_css(Path.cwd())
        if not src:
            src = next((Path.cwd() / f for f in ("redeploy.yaml",) if (Path.cwd() / f).exists()), None)
        if not src:
            for d in list(Path.cwd().parents)[:3]:
                for f in ("redeploy.css", "redeploy.less", "redeploy.yaml"):
                    if (d / f).exists():
                        src = d / f
                        break
                if src:
                    break

    if not src or not src.exists():
        console.print("[red]✗ No redeploy.css or redeploy.yaml found[/red]")
        sys.exit(1)

    console.print(f"[dim]source: {src}[/dim]")

    if fmt == "css":
        # Load from yaml or css → emit css
        if src.suffix in (".css", ".less"):
            result = load_css(src)
            manifest = result.manifest
            templates = result.templates
        else:
            import yaml as _yaml
            with src.open() as f:
                manifest = ProjectManifest(**_yaml.safe_load(f))
            templates = []

        if not manifest:
            console.print("[red]✗ Could not parse manifest[/red]")
            sys.exit(1)

        out = manifest_to_css(manifest)
        if templates:
            out += "\n\n" + templates_to_css(templates)

    else:  # yaml
        if src.suffix in (".css", ".less"):
            result = load_css(src)
            manifest = result.manifest
        else:
            import yaml as _yaml
            with src.open() as f:
                manifest = ProjectManifest(**_yaml.safe_load(f))

        if not manifest:
            console.print("[red]✗ Could not parse manifest[/red]")
            sys.exit(1)

        import yaml as _yaml
        out = _yaml.dump(manifest.model_dump(exclude_none=True, exclude_defaults=True),
                         default_flow_style=False, allow_unicode=True)

    if output:
        Path(output).write_text(out)
        console.print(f"[green]✓[/green] written to {output}")
    else:
        print(out)


@cli.command("plugin")
@click.argument("subcommand", default="list",
                type=click.Choice(["list", "info"]))
@click.argument("name", required=False, default=None)
@click.pass_context
def plugin_cmd(ctx, subcommand, name):
    """List or inspect registered redeploy plugins.

    \b
    Examples:
        redeploy plugin list
        redeploy plugin info browser_reload
        redeploy plugin info systemd_reload
    """
    from rich.console import Console
    from rich.table import Table
    from .plugins import registry, load_user_plugins

    console = Console()
    load_user_plugins()
    # Trigger builtin load
    _ = registry.names()

    if subcommand == "list":
        names = registry.names()
        if not names:
            console.print("[yellow]No plugins registered.[/yellow]")
            return
        console.print(f"\n[bold]Registered plugins ({len(names)})[/bold]\n")
        t = Table(show_header=True, box=None, padding=(0, 2))
        t.add_column("Name", style="cyan")
        t.add_column("Module", style="dim")
        t.add_column("Summary")
        for pname in sorted(names):
            handler = registry._handlers.get(pname)
            module = getattr(handler, "__module__", "?") if handler else "?"
            doc = (handler.__doc__ or "").strip().splitlines()[0][:60] if handler and handler.__doc__ else "—"
            t.add_row(pname, module.replace("redeploy.plugins.builtin.", "builtin/"), doc)
        console.print(t)
        console.print(f"\n[dim]User plugin dirs: ./redeploy_plugins/  ~/.redeploy/plugins/[/dim]")

    elif subcommand == "info":
        if not name:
            console.print("[red]✗ Provide plugin name: redeploy plugin info <name>[/red]")
            sys.exit(1)
        handler = registry._handlers.get(name)
        if not handler:
            console.print(f"[red]✗ Plugin '{name}' not found.[/red]")
            console.print(f"  Available: {', '.join(sorted(registry.names()))}")
            sys.exit(1)
        console.print(f"\n[bold cyan]{name}[/bold cyan]  "
                      f"[dim]{getattr(handler, '__module__', '?')}[/dim]")
        # Print full docstring of the module
        import importlib
        mod = importlib.import_module(handler.__module__)
        doc = (mod.__doc__ or handler.__doc__ or "No documentation.").strip()
        console.print(f"\n{doc}")


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


# ── audit ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("-n", "--last", default=20, show_default=True,
              help="Number of most-recent entries to show")
@click.option("--host", default=None, help="Filter by host (substring match)")
@click.option("--app", default=None, help="Filter by app name")
@click.option("--failed", "only_failed", is_flag=True, help="Show only failed deployments")
@click.option("--ok", "only_ok", is_flag=True, help="Show only successful deployments")
@click.option("--log", default=None, type=click.Path(), help="Custom audit log path")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSONL")
@click.option("--report", "show_report", default=None,
              help="Show full DeployReport for entry N (1-based)")
@click.option("--clear", "do_clear", is_flag=True, help="Truncate audit log (irreversible)")
def audit(last, host, app, only_failed, only_ok, log, as_json, show_report, do_clear):
    """Show deploy audit log from ~/.config/redeploy/audit.jsonl.

    \b
    Examples:
        redeploy audit
        redeploy audit --last 50 --failed
        redeploy audit --app myapp --host prod
        redeploy audit --report 1
        redeploy audit --clear
    """
    import json as _json
    from rich.console import Console
    from rich.table import Table
    from .observe import DeployAuditLog, DeployReport

    console = Console()
    log_path = Path(log) if log else None
    audit_log = DeployAuditLog(path=log_path)

    if do_clear:
        if not audit_log.path.exists():
            console.print("[dim]Audit log is already empty.[/dim]")
            return
        click.confirm(f"Truncate {audit_log.path}?", abort=True)
        audit_log.clear()
        console.print(f"[green]✓[/green] Audit log cleared: {audit_log.path}")
        return

    ok_filter = None
    if only_failed:
        ok_filter = False
    elif only_ok:
        ok_filter = True

    entries = audit_log.filter(host=host, app=app, ok=ok_filter)
    entries = entries[-last:]

    if not entries:
        console.print("[dim]No audit entries found.[/dim]")
        console.print(f"  Log: {audit_log.path}")
        return

    if show_report:
        try:
            idx = int(show_report) - 1
            entry = entries[idx]
        except (ValueError, IndexError):
            console.print(f"[red]Entry {show_report} not found (1–{len(entries)} available)[/red]")
            sys.exit(1)
        console.print(DeployReport(entry).text())
        return

    if as_json:
        for e in entries:
            print(_json.dumps(e.to_dict(), ensure_ascii=False))
        return

    t = Table(show_header=True, box=None, padding=(0, 2))
    t.add_column("#", style="dim", width=3)
    t.add_column("Time", style="dim")
    t.add_column("Host")
    t.add_column("App", style="bold")
    t.add_column("Strategy", style="cyan")
    t.add_column("Result")
    t.add_column("Steps", style="dim")
    t.add_column("Elapsed", style="dim")

    for i, e in enumerate(entries, 1):
        ts = e.ts[11:16] if len(e.ts) >= 16 else e.ts
        date = e.ts[:10] if len(e.ts) >= 10 else ""
        strategy = f"{e.from_strategy}→{e.to_strategy}"
        if e.ok:
            result = "[green]ok[/green]"
        else:
            result = "[red]FAIL[/red]"
        if e.dry_run:
            result += " [dim](dry)[/dim]"
        steps_str = f"{e.steps_ok}/{e.steps_total}"
        if e.steps_failed:
            steps_str += f" [red]✗{e.steps_failed}[/red]"
        elapsed = f"{e.elapsed_s:.1f}s"
        t.add_row(str(i), f"{date} {ts}", e.host, e.app,
                  strategy, result, steps_str, elapsed)

    console.print(t)
    console.print(f"\n  [dim]{len(entries)} entr{'y' if len(entries)==1 else 'ies'}  •  {audit_log.path}[/dim]")
    console.print("  [dim]Tip: --report N  for full step breakdown[/dim]")


# ── patterns ──────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("name", default=None, required=False)
def patterns(name):
    """List available deploy patterns or show detail for one.

    \b
    Examples:
        redeploy patterns
        redeploy patterns blue_green
        redeploy patterns canary
    """
    from rich.console import Console
    from rich.table import Table
    from .patterns import pattern_registry, BlueGreenPattern, CanaryPattern, RollbackOnFailurePattern

    console = Console()

    if name:
        cls = pattern_registry.get(name)
        if not cls:
            console.print(f"[red]Pattern '{name}' not found.[/red]")
            console.print(f"  Available: {', '.join(pattern_registry.keys())}")
            sys.exit(1)

        p_map = {
            "blue_green": BlueGreenPattern(app="myapp", remote_dir="~/myapp",
                                           verify_url="http://localhost:8080"),
            "canary": CanaryPattern(app="myapp", remote_dir="~/myapp",
                                    verify_url="http://localhost:8080"),
            "rollback_on_failure": RollbackOnFailurePattern(app="myapp", remote_dir="~/myapp",
                                                             verify_url="http://localhost:8080"),
        }
        instance = p_map.get(name)
        steps = instance.expand() if instance else []

        console.print(f"\n[bold]{name}[/bold] — {cls.description}")
        if steps:
            t = Table(show_header=True, box=None, padding=(0, 2))
            t.add_column("#", style="dim", width=3)
            t.add_column("ID")
            t.add_column("Action", style="cyan")
            t.add_column("Risk", style="dim")
            t.add_column("Rollback", style="dim")
            for i, s in enumerate(steps, 1):
                t.add_row(
                    str(i), s.id, s.action.value, s.risk.value,
                    "✓" if s.rollback_command else "—",
                )
            console.print(t)

        console.print(f"\n  [dim]Usage in target config:[/dim]")
        console.print(f"    [cyan]pattern: {name}[/cyan]")
        console.print(f"    [cyan]pattern_config:[/cyan]")
        console.print(f"      [cyan]verify_url: http://your-app/health[/cyan]")
        return

    # List all patterns
    console.print("\n[bold]Available deploy patterns:[/bold]\n")
    t = Table(show_header=True, box=None, padding=(0, 2))
    t.add_column("Name", style="bold cyan")
    t.add_column("Description")
    t.add_column("Steps", style="dim")

    step_counts = {
        "blue_green": len(BlueGreenPattern(app="x", remote_dir="~/x",
                                           verify_url="http://x").expand()),
        "canary": len(CanaryPattern(app="x", remote_dir="~/x",
                                    verify_url="http://x").expand()),
        "rollback_on_failure": len(RollbackOnFailurePattern(app="x", remote_dir="~/x",
                                                             verify_url="http://x").expand()),
    }

    for pname, cls in pattern_registry.items():
        t.add_row(pname, cls.description, str(step_counts.get(pname, "?")))
    console.print(t)

    console.print("\n  [dim]Use [bold]redeploy patterns <name>[/bold] for step details[/dim]")
    console.print("  [dim]Set in target YAML:  pattern: blue_green[/dim]")


# ── Version management commands ────────────────────────────────────────────────

@cli.group(name="version")
def version_cmd():
    """Declarative version management: bump, verify, diff.

    Reads .redeploy/version.yaml manifest and manages version
    across all declared sources atomically.
    """
    pass


@version_cmd.command(name="current")
@click.option("--manifest", "-m", default=".redeploy/version.yaml",
              help="Path to version manifest")
def version_current(manifest):
    """Show current version from manifest."""
    from rich.console import Console
    from .version import VersionManifest

    console = Console()
    path = Path(manifest)

    if not path.exists():
        console.print(f"[red]✗ Manifest not found: {path}[/red]")
        console.print("  Run: redeploy version init")
        sys.exit(1)

    try:
        m = VersionManifest.load(path)
        console.print(f"[bold]{m.version}[/bold]")
    except Exception as e:
        console.print(f"[red]✗ Error loading manifest: {e}[/red]")
        sys.exit(1)


@version_cmd.command(name="list")
@click.option("--manifest", "-m", default=".redeploy/version.yaml",
              help="Path to version manifest")
def version_list(manifest):
    """List all version sources and their values."""
    from rich.console import Console
    from rich.table import Table
    from .version import VersionManifest, verify_sources

    console = Console()
    path = Path(manifest)

    if not path.exists():
        console.print(f"[red]✗ Manifest not found: {path}[/red]")
        sys.exit(1)

    m = VersionManifest.load(path)
    result = verify_sources(m)

    console.print(f"[bold]Version sources[/bold] (manifest: {m.version})")
    t = Table(show_header=True, box=None)
    t.add_column("Source", style="bold")
    t.add_column("Format")
    t.add_column("Current")
    t.add_column("Status")

    for s in result["sources"]:
        status = "[green]✓" if s["match"] else "[red]✗ drift"
        actual = s["actual"] or "[dim]—[/dim]"
        t.add_row(str(s["path"]), s["format"], actual, status)

    console.print(t)
    if not result["all_match"]:
        console.print("\n[yellow]⚠ Some sources are out of sync[/yellow]")
        sys.exit(1)


@version_cmd.command(name="verify")
@click.option("--manifest", "-m", default=".redeploy/version.yaml",
              help="Path to version manifest")
def version_verify(manifest):
    """Verify all sources match manifest version."""
    from rich.console import Console
    from .version import VersionManifest, verify_sources

    console = Console()
    path = Path(manifest)

    if not path.exists():
        console.print(f"[red]✗ Manifest not found: {path}[/red]")
        sys.exit(1)

    m = VersionManifest.load(path)
    result = verify_sources(m)

    if result["all_match"]:
        console.print(f"[green]✓ All {len(result['sources'])} sources in sync at {m.version}[/green]")
    else:
        console.print(f"[red]✗ Version drift detected[/red]")
        for s in result["sources"]:
            if not s["match"]:
                console.print(f"  [red]✗[/red] {s['path']}: expected {m.version}, found {s.get('actual', 'ERROR')}")
        sys.exit(1)


@version_cmd.command(name="bump")
@click.argument("type", type=click.Choice(["patch", "minor", "major", "prerelease"]), required=False)
@click.option("--manifest", "-m", default=".redeploy/version.yaml",
              help="Path to version manifest")
@click.option("--package", "-p", help="Bump specific package (for monorepo)")
@click.option("--all-packages", is_flag=True, help="Bump all packages (for monorepo)")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying")
@click.option("--analyze", is_flag=True, help="Auto-detect bump type from conventional commits")
@click.option("--commit", is_flag=True, help="Create git commit with changes")
@click.option("--tag", is_flag=True, help="Create git tag for new version")
@click.option("--push", is_flag=True, help="Push commit and tags to origin")
@click.option("--sign", is_flag=True, help="Sign tag with GPG")
@click.option("--allow-dirty", is_flag=True, help="Allow bump with dirty working directory")
@click.option("--changelog", is_flag=True, help="Update CHANGELOG.md")
def version_bump(type, manifest, package, all_packages, dry_run, analyze, commit, tag, push, sign, allow_dirty, changelog):
    """Bump version across all sources atomically.

    Examples:
        redeploy version bump patch
        redeploy version bump patch --commit --tag --push
        redeploy version bump --analyze --commit --tag  # Auto-detect from commits
    """
    from rich.console import Console
    from .version import VersionManifest

    console = Console()
    path = Path(manifest)

    if not path.exists():
        console.print(f"[red]✗ Manifest not found: {path}[/red]")
        console.print("  Run: redeploy version init")
        sys.exit(1)

    m = VersionManifest.load(path)

    # Handle monorepo packages
    if package:
        # Bump specific package
        pkg = m.get_package(package)
        if pkg is None:
            console.print(f"[red]✗ Package '{package}' not found in manifest[/red]")
            console.print(f"  Available: {m.list_packages()}")
            sys.exit(1)

        # Create temporary manifest for this package
        from .version.manifest import VersionManifest, GitConfig

        pkg_manifest = VersionManifest(
            version=pkg.version,
            scheme=m.scheme,
            policy="synced",  # Single package uses synced
            sources=pkg.sources,
            git=pkg.git or m.git,
            changelog=pkg.changelog,
            commits=m.commits,
        )

        result = _bump_single(
            pkg_manifest, type, dry_run, analyze, commit, tag, push, sign, allow_dirty, changelog,
            repo_path=path.parent.parent,
            console=console,
            package_name=package,
        )

        # Update package version in main manifest
        if not dry_run and result:
            pkg.version = result.version if hasattr(result, 'version') else result['new_version']
            m.save(path)

        return

    if all_packages and m.is_monorepo():
        # Bump all packages
        for pkg_name in m.list_packages():
            console.print(f"\n[bold]Bumping package: {pkg_name}[/bold]")
            pkg = m.get_package(pkg_name)
            pkg_manifest = VersionManifest(
                version=pkg.version,
                scheme=m.scheme,
                policy="synced",
                sources=pkg.sources,
                git=pkg.git or m.git,
                changelog=pkg.changelog,
                commits=m.commits,
            )

            _bump_single(
                pkg_manifest, type, dry_run, analyze, commit, tag, push, sign, allow_dirty, changelog,
                repo_path=path.parent.parent,
                console=console,
                package_name=pkg_name,
            )

            if not dry_run:
                pkg.version = pkg_manifest.version

        if not dry_run:
            m.save(path)
        return

    # Standard single-repo bump
    old = m.version
    _bump_single(
        m, type, dry_run, analyze, commit, tag, push, sign, allow_dirty, changelog,
        repo_path=path.parent.parent,
        console=console,
        manifest_path=path,
    )

    if not dry_run:
        m.save(path)


def _bump_single(
    m, type, dry_run, analyze, commit, tag, push, sign, allow_dirty, changelog,
    *, repo_path, console, package_name: str = None, manifest_path: Path | None = None,
    new_version: str | None = None,
):
    from .version.bump import _calculate_bump, bump_version, bump_version_with_git
    from .version.changelog import ChangelogManager, get_commits_since_tag
    from .version.commits import analyze_commits, format_analysis_report
    from .version.git_integration import GitIntegrationError

    old = m.version
    prefix = f"[{package_name}] " if package_name else ""

    # Auto-analyze if requested
    if analyze:
        last_tag = m.git.tag_format.format(version=old)
        analysis = analyze_commits(last_tag, repo_path, m.commits)

        console.print(f"{prefix}[bold]Analyzing commits...[/bold]")
        console.print(format_analysis_report(analysis))

        if analysis.bump_type:
            type = analysis.bump_type
            console.print(f"\n{prefix}Using detected bump type: [bold]{type}[/bold]")
        else:
            console.print(f"\n{prefix}[yellow]No bump-worthy commits found. Use explicit type to force bump.[/yellow]")
            return None

    if not type:
        console.print("[red]✗ Bump type required (patch/minor/major) or use --analyze[/red]")
        sys.exit(1)

    target_version = new_version or _calculate_bump(old, type)

    # Dry run
    if dry_run:
        console.print(f"[DRY RUN] Would change version: {old} → {target_version}")
        console.print(f"  Sources: {len(m.sources)}")
        if commit or tag or push:
            console.print(f"  Git: commit={commit}, tag={tag}, push={push}, sign={sign}")
        if changelog:
            changelog_path = m.changelog.path if m.changelog else Path("CHANGELOG.md")
            console.print(f"  Changelog: update {changelog_path}")
        for s in m.sources:
            console.print(f"    - {s.path} ({s.format})")
        return

    # Real bump
    try:
        # Handle changelog update
        if changelog:
            changelog_path = m.changelog.path if m.changelog else Path("CHANGELOG.md")
            changelog_mgr = ChangelogManager(repo_path / changelog_path)
            commits = get_commits_since_tag(repo_path, m.git.tag_format.format(version=old))
            new_content = changelog_mgr.prepare_release(target_version, commit_messages=commits)
            changelog_mgr.write(new_content)
            console.print(f"[green]✓ Updated {changelog_path}[/green]")

        if commit or tag or push:
            # Use git integration
            result = bump_version_with_git(
                m, type,
                repo_path=repo_path,
                new_version=target_version,
                manifest_path=manifest_path,
                commit=commit or push,
                tag=tag or push,
                push=push,
                sign=sign,
                allow_dirty=allow_dirty,
            )
            console.print(f"[green]✓ Changed version: {old} → {result.version}[/green]")
            console.print(f"  Updated {result.files_updated} files")
            if result.commit_hash:
                console.print(f"  Commit: {result.commit_hash[:8]}")
            if result.tag_name:
                console.print(f"  Tag: {result.tag_name}")
            if result.pushed:
                console.print("  Pushed to origin")
            return result
        else:
            result = bump_version(m, type, new_version=target_version)
            if manifest_path is not None:
                m.save(manifest_path)
            console.print(f"[green]✓ Changed version: {old} → {result['new_version']}[/green]")
            console.print(f"  Updated {result['success']}/{result['total']} sources")
            return result

    except GitIntegrationError as e:
        console.print(f"[red]✗ Git error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Bump failed: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)


def _calculate_bump(current: str, bump_type: str) -> str:
    """Calculate new version from current + bump type."""
    import re
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$", current)
    if not match:
        raise ValueError(f"Cannot bump non-semver version: {current}")

    major, minor, patch, prerelease = match.groups()
    major, minor, patch = int(major), int(minor), int(patch)

    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    elif bump_type == "prerelease":
        if prerelease:
            base = re.match(r"^(.*?)(\d+)$", prerelease)
            if base:
                prefix, num = base.groups()
                return f"{major}.{minor}.{patch}-{prefix}{int(num) + 1}"
            return f"{major}.{minor}.{patch}-{prerelease}.1"
        return f"{major}.{minor}.{patch}-rc.1"
    else:
        raise ValueError(f"Unknown bump type: {bump_type}")


@version_cmd.command(name="set")
@click.argument("version")
@click.option("--manifest", "manifest_path_str", default=".redeploy/version.yaml",
              help="Path to version manifest")
@click.option("--package", "package_name", "-p", help="Set version for a specific package (for monorepo)")
@click.option("--all-packages", is_flag=True, help="Set version for all packages (for monorepo)")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying")
@click.option("--commit", is_flag=True, help="Create git commit with changes")
@click.option("--tag", is_flag=True, help="Create git tag for new version")
@click.option("--push", is_flag=True, help="Push commit and tags to origin")
@click.option("--sign", is_flag=True, help="Sign tag with GPG")
@click.option("--allow-dirty", is_flag=True, help="Allow version change with dirty working directory")
@click.option("--changelog", is_flag=True, help="Update CHANGELOG.md")
def version_set(version, manifest_path_str, package_name, all_packages, dry_run, commit, tag, push, sign, allow_dirty, changelog):
    """Set an explicit version across all manifest sources."""
    from rich.console import Console
    from .version import VersionManifest
    from .version.bump import bump_package
    from .version.changelog import ChangelogManager, get_commits_since_tag
    from .version.git_integration import GitIntegration, GitIntegrationError

    console = Console()
    manifest_path = Path(manifest_path_str)

    if not manifest_path.exists():
        console.print(f"[red]✗ Manifest not found: {manifest_path}[/red]")
        console.print("  Run: redeploy version init")
        sys.exit(1)

    manifest_model = VersionManifest.load(manifest_path)

    if package_name and all_packages:
        console.print("[red]✗ Use either --package NAME or --all-packages, not both.[/red]")
        sys.exit(1)

    if package_name or all_packages:
        if not manifest_model.is_monorepo():
            console.print("[red]✗ Manifest has no packages defined. Add 'packages:' section for monorepo support.[/red]")
            sys.exit(1)

        if package_name:
            targets = [package_name]
            pkg = manifest_model.get_package(package_name)
            if pkg is None:
                console.print(f"[red]✗ Package '{package_name}' not found in manifest[/red]")
                console.print(f"  Available: {manifest_model.list_packages()}")
                sys.exit(1)
        else:
            targets = manifest_model.list_packages()

        repo_path = manifest_path.parent.parent

        if dry_run:
            for pkg_name in targets:
                pkg = manifest_model.get_package(pkg_name)
                console.print(f"[DRY RUN] Would set {pkg_name}: {pkg.version} → {version}")
                console.print(f"  Sources: {len(pkg.sources)}")
                for source in pkg.sources:
                    console.print(f"    - {source.path} ({source.format})")
            return

        try:
            git = None
            if commit or tag or push:
                git_config = manifest_model.get_package(package_name).git if package_name and manifest_model.get_package(package_name) and manifest_model.get_package(package_name).git else manifest_model.git
                git = GitIntegration(git_config, repo_path)
                if git_config.require_clean and not allow_dirty:
                    git.require_clean()

            touched_files = []
            if changelog:
                changelog_path = manifest_model.changelog.path if manifest_model.changelog else Path("CHANGELOG.md")
                changelog_mgr = ChangelogManager(repo_path / changelog_path)
                commits = get_commits_since_tag(repo_path, manifest_model.git.tag_format.format(version=manifest_model.version))
                new_content = changelog_mgr.prepare_release(version, commit_messages=commits)
                changelog_mgr.write(new_content)
                console.print(f"[green]✓ Updated {changelog_path}[/green]")
                touched_files.append(changelog_path)

            for pkg_name in targets:
                pkg = manifest_model.get_package(pkg_name)
                result = bump_package(manifest_model, pkg_name, "patch", new_version=version)
                touched_files.extend(source.path for source in pkg.sources)
                console.print(f"[green]✓[/green] {pkg_name}: {result['old']} → {result['new_version']}  ({result['success']}/{result['total']} sources)")

            manifest_model.save(manifest_path)
            touched_files.append(manifest_path)

            if git:
                unique_files = []
                for file_path in touched_files:
                    if file_path not in unique_files:
                        unique_files.append(file_path)

                commit_hash = None
                tag_name = None
                if commit or push:
                    commit_hash = git.commit(version, unique_files)
                if tag or push:
                    tag_name = git.tag(version, sign=sign)
                if push:
                    git.push(follow_tags=True)

                console.print(f"[green]✓ Set version to {version} for {len(targets)} package(s)[/green]")
                if commit_hash:
                    console.print(f"  Commit: {commit_hash[:8]}")
                if tag_name:
                    console.print(f"  Tag: {tag_name}")
                if push:
                    console.print("  Pushed to origin")

            return
        except GitIntegrationError as e:
            console.print(f"[red]✗ Git error: {e}[/red]")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]✗ Version set failed: {e}[/red]")
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
            sys.exit(1)

    _bump_single(
        manifest_model,
        "patch",
        dry_run,
        False,
        commit,
        tag,
        push,
        sign,
        allow_dirty,
        changelog,
        repo_path=manifest_path.parent.parent,
        console=console,
        manifest_path=manifest_path,
        new_version=version,
    )

    if not dry_run:
        manifest_model.save(manifest_path)


@version_cmd.command(name="init")
@click.option("--scan", is_flag=True, help="Auto-detect version sources")
@click.option("--force", is_flag=True, help="Overwrite existing manifest")
def version_init(scan, force):
    """Initialize .redeploy/version.yaml manifest."""
    from rich.console import Console
    from .version.manifest import VersionManifest, SourceConfig, GitConfig

    console = Console()
    manifest_path = Path(".redeploy/version.yaml")

    if manifest_path.exists() and not force:
        console.print(f"[yellow]⚠ Manifest already exists: {manifest_path}[/yellow]")
        console.print("  Use --force to overwrite or edit existing file")
        sys.exit(1)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    # Detect sources if --scan
    sources = []
    if scan:
        # Check common locations
        if Path("VERSION").exists():
            sources.append(SourceConfig(path=Path("VERSION"), format="plain"))
        if Path("pyproject.toml").exists():
            sources.append(SourceConfig(path=Path("pyproject.toml"), format="toml", key="project.version"))
        if Path("package.json").exists():
            sources.append(SourceConfig(path=Path("package.json"), format="json", key="version"))

    if not sources:
        # Default minimal manifest
        sources = [SourceConfig(path=Path("VERSION"), format="plain")]

    # Detect current version
    current = "0.1.0"
    for s in sources:
        if s.path.exists():
            try:
                from .version.sources import get_adapter
                current = get_adapter(s.format).read(s.path, s)
                break
            except Exception:
                pass

    m = VersionManifest(
        version=current,
        scheme="semver",
        policy="synced",
        sources=sources,
        git=GitConfig(),
    )

    m.save(manifest_path)
    console.print(f"[green]✓ Created {manifest_path}[/green]")
    console.print(f"  Current version: {current}")
    console.print(f"  Sources: {len(sources)}")
    for s in sources:
        console.print(f"    - {s.path} ({s.format})")


@version_cmd.command(name="diff")
@click.option("--manifest", "-m", default=".redeploy/version.yaml",
              help="Path to version manifest")
@click.option("--spec", help="Path to migration.yaml to compare")
@click.option("--live", help="SSH host to check live version (user@host)")
@click.option("--app", default="c2004", help="Application name for live check")
def version_diff(manifest, spec, live, app):
    """Compare manifest version vs spec vs live.

    Examples:
        redeploy version diff                    # sources only
        redeploy version diff --spec migration.yaml   # vs migration.yaml
        redeploy version diff --live root@vps.example.com  # vs live
    """
    from rich.console import Console
    from .version import VersionManifest, verify_sources
    from .version.diff import VersionDiff, diff_manifest_vs_spec, diff_manifest_vs_live, format_diff_report

    console = Console()
    path = Path(manifest)

    if not path.exists():
        console.print(f"[red]✗ Manifest not found: {path}[/red]")
        sys.exit(1)

    m = VersionManifest.load(path)
    diffs = []

    # 1. Check sources (always)
    result = verify_sources(m)
    if not result["all_match"]:
        console.print(f"[yellow]⚠ Source drift detected in {len([s for s in result['sources'] if not s['match']])} file(s)[/yellow]")
        for s in result["sources"]:
            if not s["match"]:
                console.print(f"  [red]✗[/red] {s['path']}: {s.get('actual', 'ERROR')} ≠ {m.version}")
    else:
        console.print(f"[green]✓ All {len(result['sources'])} sources in sync at {m.version}[/green]")

    # 2. Compare with migration.yaml spec
    if spec:
        import yaml
        spec_path = Path(spec)
        if not spec_path.exists():
            diffs.append(VersionDiff(
                source="spec",
                version=None,
                expected=m.version,
                match=False,
                error=f"Spec not found: {spec_path}",
            ))
        else:
            try:
                spec_data = yaml.safe_load(spec_path.read_text()) or {}
                if not isinstance(spec_data, dict):
                    raise ValueError("spec root must be a mapping")

                target_data = spec_data.get("target") or {}
                if not isinstance(target_data, dict):
                    raise ValueError("spec target must be a mapping")

                diffs.append(diff_manifest_vs_spec(m, target_data.get("version")))
            except Exception as e:
                diffs.append(VersionDiff(
                    source="spec",
                    version=None,
                    expected=m.version,
                    match=False,
                    error=f"Could not read spec: {e}",
                ))

    # 3. Compare with live host
    if live:
        from .version import read_remote_version
        from .ssh import SshClient

        try:
            remote = SshClient(live)
            live_version = read_remote_version(remote, "~/c2004", app)
            diff = diff_manifest_vs_live(m, live_version)
            diffs.append(diff)
        except Exception as e:
            diffs.append(VersionDiff(
                source="live",
                version=None,
                expected=m.version,
                match=False,
                error=f"Could not check live version: {e}",
            ))

    if diffs:
        console.print()
        console.print(format_diff_report(diffs, m.version))

    # Summary
    all_match = result["all_match"] and all(d.match for d in diffs)
    if all_match:
        console.print(f"\n[green]✓ No version drift detected[/green]")
    else:
        console.print(f"\n[yellow]⚠ Version drift detected - review before deploying[/yellow]")
        sys.exit(1)

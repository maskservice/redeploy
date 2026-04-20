"""Display and formatting utilities for CLI output."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console
    from ..models import ProjectManifest, EnvironmentConfig


def print_plan_table(console: "Console", migration) -> None:
    """Print migration plan as a table."""
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
    for note in migration.notes or []:
        console.print(f"  [yellow]⚠ {note}[/yellow]")


def print_infrastructure_summary(console: "Console", state, host: str) -> None:
    """Print infrastructure summary from detection state."""
    from rich.table import Table

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


def print_docker_services(console: "Console", state) -> None:
    """Print Docker container status."""
    if state.services.get("docker"):
        console.print("\n[bold]Docker containers:[/bold]")
        for s in state.services["docker"]:
            icon = "✅" if s.status == "healthy" else "⚪"
            console.print(f"  {icon} {s.name}  ({s.status})")


def print_k3s_pods(console: "Console", state) -> None:
    """Print k3s pod status."""
    if state.services.get("k3s"):
        console.print(f"\n[bold]k3s pods ({len(state.services['k3s'])}):[/bold]")
        for s in state.services["k3s"]:
            icon = "✅" if s.status == "running" else "⚪"
            console.print(f"  {icon} {s.namespace}/{s.name}  ({s.status})")


def print_conflicts(console: "Console", state) -> None:
    """Print detection conflicts."""
    if state.conflicts:
        console.print(f"\n[bold yellow]Conflicts ({len(state.conflicts)}):[/bold yellow]")
        for c in state.conflicts:
            color = {"critical": "red", "high": "yellow", "medium": "blue", "low": "dim"}[
                c.severity.value
            ]
            console.print(f"  [{color}][{c.severity.upper()}][/{color}] {c.type}: {c.description}")
            if c.fix_hint:
                console.print(f"    [dim]hint: {c.fix_hint}[/dim]")
    else:
        console.print("\n[green]No conflicts detected.[/green]")


def print_inspect_app_metadata(console: "Console", result) -> None:
    """Print app metadata from inspect result."""
    if result.manifest:
        m = result.manifest
        console.print(
            f"[bold cyan]app[/bold cyan]  {m.app}  spec={m.spec}"
            + (f"  domain={m.domain}" if m.domain else "")
        )


def print_inspect_environments(console: "Console", result) -> None:
    """Print environments from inspect result."""
    from rich.table import Table

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


def print_inspect_templates(console: "Console", result) -> None:
    """Print detection templates from inspect result."""
    if result.templates:
        console.print(f"\n[bold]Detection Templates ({len(result.templates)})[/bold]")
        for tpl in result.templates:
            console.print(
                f"  [cyan]{tpl.id}[/cyan]  env=[yellow]{tpl.environment}[/yellow]"
                f"  strategy={tpl.strategy.value}  max_score={tpl.max_score:.1f}"
            )
            console.print(
                f"    conditions: "
                + "  ".join(f"[dim]{c.description}[/dim]×{c.weight}" for c in tpl.conditions[:5])
            )
            if tpl.required:
                console.print(
                    f"    required:   "
                    + "  ".join(f"[red]{r.description}[/red]" for r in tpl.required)
                )
            if tpl.notes:
                for note in tpl.notes[:2]:
                    console.print(f"    [dim]→ {note}[/dim]")


def print_inspect_workflows(console: "Console", result) -> None:
    """Print workflows from inspect result."""
    if result.workflows:
        console.print(f"\n[bold]Workflows ({len(result.workflows)})[/bold]")
        for wf in result.workflows:
            plugin_steps = [s for s in wf.steps if s.plugin_type]
            plugin_hint = (
                f"  [dim](plugins: " + ", ".join(s.plugin_type for s in plugin_steps) + ")[/dim]"
                if plugin_steps
                else ""
            )
            console.print(
                f"  [cyan]{wf.name}[/cyan]  "
                f"[dim]{wf.trigger}[/dim]  "
                f"{len(wf.steps)} steps"
                + (f"  [dim]{wf.description}[/dim]" if wf.description else "")
                + plugin_hint
            )
            for step in wf.steps:
                if step.plugin_type:
                    params_str = "  ".join(f"{k}={v}" for k, v in step.plugin_params.items())
                    console.print(
                        f"    step-{step.index}: [yellow]plugin[/yellow] "
                        f"[cyan]{step.plugin_type}[/cyan]"
                        + (f"  [dim]{params_str}[/dim]" if params_str else "")
                    )
                else:
                    console.print(f"    step-{step.index}: [dim]{step.command[:80]}[/dim]")


def print_inspect_devices(console: "Console", result) -> None:
    """Print devices from inspect result."""
    from rich.table import Table

    devices = [n for n in result.raw_nodes if n.selector_type == "device"]
    if devices:
        console.print(f"\n[bold]Devices ({len(devices)})[/bold]")
        t = Table(show_header=True, box=None, padding=(0, 2))
        t.add_column("Name", style="cyan")
        t.add_column("Host")
        t.add_column("Arch", style="dim")
        t.add_column("Strategy", style="dim")
        t.add_column("Description")
        for d in devices:
            t.add_row(
                d.name,
                d.get("host", "—"),
                d.get("arch", "—"),
                d.get("expected_strategy", "—"),
                d.get("description", "—"),
            )
        console.print(t)


def print_inspect_raw_nodes_summary(console: "Console", result) -> None:
    """Print raw nodes summary from inspect result."""
    by_type: dict[str, int] = {}
    for n in result.raw_nodes:
        by_type[n.selector_type] = by_type.get(n.selector_type, 0) + 1
    console.print(
        f"\n[dim]nodes: "
        + "  ".join(f"{t}×{c}" for t, c in sorted(by_type.items()))
        + "[/dim]"
    )
    console.print("[dim]export: redeploy export --format css  |  redeploy export --format yaml[/dim]")


def print_workflow_summary_table(console: "Console", result) -> None:
    """Print workflow summary as a table."""
    from rich.table import Table

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
            conf_color = {"high": "green", "medium": "yellow", "low": "red"}.get(
                h.confidence, "dim"
            )
            conflicts = str(len(h.state.conflicts)) if h.state else "—"
            t.add_row(
                h.host,
                h.environment,
                h.strategy.value,
                h.template_name[:30],
                f"[{conf_color}]{h.confidence}[/{conf_color}]",
                h.arch or "—",
                conflicts,
            )
        else:
            t.add_row(h.host, "—", "—", f"[red]✗ {h.error[:30]}[/red]", "—", "—", "—")
    console.print(t)
    console.print(f"\n  {len(result.reachable)}/{len(result.hosts)} reachable")


def print_workflow_host_details(console: "Console", result) -> None:
    """Print detailed host information from workflow result."""
    for h in result.reachable:
        if not h.template_result:
            continue
        best = h.template_result.best
        console.print(
            f"\n[bold]── {h.host} ──[/bold]  [cyan]{h.environment}[/cyan]  {h.strategy.value}"
        )
        console.print(f"  Template:   {best.template.name}")
        console.print(
            f"  Confidence: {best.score:.1f}/{best.max_score:.1f}  ({best.confidence_label})"
        )
        if best.matched_conditions:
            console.print(f"  [green]✓[/green] " + "  ".join(best.matched_conditions[:5]))
        if best.failed_conditions:
            console.print(f"  [dim]✗ " + "  ".join(best.failed_conditions[:4]) + "[/dim]")
        if best.template.notes:
            for note in best.template.notes[:2]:
                console.print(f"  [dim]→ {note}[/dim]")

        alts = [m for m in h.template_result.ranked[1:4] if m.score > 0]
        if alts:
            console.print(
                f"  [dim]alternatives: "
                + " | ".join(f"{m.template.id} ({m.score:.1f})" for m in alts)
                + "[/dim]"
            )


def generate_workflow_output_css(
    console: "Console", result, app: str, save_yaml: str | None
) -> None:
    """Generate and display/save CSS output from workflow."""
    from ..dsl.loader import manifest_to_css, templates_to_css
    from ..models import ProjectManifest, EnvironmentConfig

    gen_manifest = result.reachable[0].template_result
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


def generate_workflow_output_yaml(
    console: "Console", result, save_yaml: str | None
) -> None:
    """Generate and display/save YAML output from workflow."""
    yaml_out = result.generated_redeploy_yaml()
    console.print(f"\n[bold]generated redeploy.yaml:[/bold]")
    console.print(yaml_out)
    if save_yaml:
        Path(save_yaml).write_text(yaml_out)
        console.print(f"  [dim]saved → {save_yaml}[/dim]")


def print_import_spec(console: "Console", spec) -> None:
    """Print a ParsedSpec summary to the Rich console."""
    from rich.table import Table

    status_color = (
        "green" if spec.confidence >= 0.8 else "yellow" if spec.confidence >= 0.5 else "red"
    )
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

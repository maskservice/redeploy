"""import command — Parse IaC/CI-CD file and produce migration.yaml scaffold."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table


@click.command(name="import")
@click.argument("source", required=False, type=click.Path())
@click.option(
    "-o", "--output", default=None, type=click.Path(),
    help="Output migration.yaml path (default: <source-stem>.migration.yaml)"
)
@click.option(
    "--target-host", default=None,
    help="Target SSH host (user@host) to embed in migration.yaml"
)
@click.option(
    "--target-strategy", default=None,
    help="Override detected strategy (e.g. docker_full, podman_quadlet)"
)
@click.option(
    "--dry-run", is_flag=True,
    help="Parse and display result without writing output file"
)
@click.option(
    "--format", "out_format", default="yaml",
    type=click.Choice(["yaml", "json", "summary"]), show_default=True,
    help="Output format"
)
@click.option(
    "--parser", default=None,
    help="Force specific parser (e.g. docker_compose). Default: auto-detect"
)
@click.option(
    "--plugin-template",
    type=click.Choice(["helm-ansible", "helm-kustomize", "argocd-flux", "gitops-ci"]),
    default=None,
    help="Copy a ready-made parser plugin template into the project instead of parsing SOURCE.",
)
@click.option(
    "--plugin-dir",
    default="redeploy_iac_parsers",
    type=click.Path(),
    show_default=True,
    help="Destination directory for --plugin-template.",
)
@click.option(
    "--list-plugin-templates",
    is_flag=True,
    help="List built-in parser plugin templates and exit.",
)
def import_cmd(
    source,
    output,
    target_host,
    target_strategy,
    dry_run,
    out_format,
    parser,
    plugin_template,
    plugin_dir,
    list_plugin_templates,
):
    """Parse an IaC/CI-CD file and produce a migration.yaml scaffold.

        Auto-detects format from filename. Built-in parsers cover:
        docker-compose, Dockerfile, Kubernetes YAML, Terraform, TOML/pyproject,
        Vite config, nginx.conf, GitHub Actions, GitLab CI, Jenkinsfile.

        Additional parsers can be provided via plugins:
            - Python entry points group: redeploy.iac.parsers
            - Local files: ./redeploy_iac_parsers/*.py
            - User files: ~/.redeploy/iac_parsers/*.py

    \b
    Examples:
        redeploy import docker-compose.yml
        redeploy import docker-compose.yml -o migration.yaml
        redeploy import docker-compose.yml --target-host root@vps.example.com
        redeploy import . --dry-run               # parse whole directory
        redeploy import docker-compose.yml --format summary
        redeploy import --plugin-template helm-kustomize
    """
    import json as _json
    from ...iac import parse_file, parse_dir, parser_registry

    console = Console()

    if list_plugin_templates:
        _print_plugin_templates(console)
        return

    if plugin_template:
        _copy_plugin_template(
            console,
            plugin_template=plugin_template,
            plugin_dir=Path(plugin_dir),
            dry_run=dry_run,
        )
        return

    if not source:
        console.print("[red]✗ SOURCE is required unless --plugin-template is used[/red]")
        sys.exit(1)

    src_path = Path(source)
    if not src_path.exists():
        console.print(f"[red]✗ source does not exist: {source}[/red]")
        sys.exit(1)

    # Parse
    if parser:
        p = next((p for p in parser_registry._parsers if p.name == parser), None)
        if not p:
            console.print(
                f"[red]✗ Unknown parser '{parser}'. "
                f"Known: {parser_registry.registered}[/red]"
            )
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

    console.print(
        f"[bold]import[/bold]  {source}  "
        f"({len(specs)} file(s) parsed)"
    )

    # Display
    for spec in specs:
        _print_import_spec(console, spec)

    if dry_run:
        console.print("\n[dim][DRY RUN] No file written.[/dim]")
        return

    if out_format == "summary":
        return

    # Convert + write
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
            out_path = out_path.with_suffix(".json")
            out_path.write_text(_json.dumps(migration_data, indent=2, ensure_ascii=False))
        else:
            import yaml as _yaml

            out_path.write_text(
                _yaml.dump(
                    migration_data,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )
            )

        console.print(f"\n  [green]✓[/green] written → [bold]{out_path}[/bold]")
        if spec.warnings:
            for w in spec.warnings:
                icon = {"error": "✗", "warn": "⚠", "info": "ℹ"}.get(w.severity, "?")
                color = {"error": "red", "warn": "yellow", "info": "dim"}.get(
                    w.severity, "dim"
                )
                console.print(f"  [{color}]{icon} {w}[/{color}]")


def _print_import_spec(console, spec) -> None:
    """Print a ParsedSpec summary."""
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


def _default_output(src: Path, spec) -> Path:
    """Get default output path."""
    if src.is_dir():
        return src / "migration.yaml"
    stem = src.stem.replace("docker-compose", "migration").replace("compose", "migration")
    if stem == src.stem:
        stem = f"{src.stem}.migration"
    return src.parent / f"{stem}.yaml"


def _plugin_templates() -> dict[str, str]:
    return {
        "helm-ansible": "helm_ansible.py",
        "helm-kustomize": "helm_kustomize.py",
        "argocd-flux": "argocd_flux.py",
        "gitops-ci": "gitops_ci.py",
    }


def _examples_plugin_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "examples" / "redeploy_iac_parsers"


def _print_plugin_templates(console: Console) -> None:
    console.print("[bold]Available parser plugin templates[/bold]")
    for name, filename in _plugin_templates().items():
        console.print(f"  - [cyan]{name}[/cyan]  ({filename})")


def _copy_plugin_template(
    console: Console,
    *,
    plugin_template: str,
    plugin_dir: Path,
    dry_run: bool,
) -> Path:
    templates = _plugin_templates()
    filename = templates[plugin_template]
    src = _examples_plugin_dir() / filename
    dst = plugin_dir / filename

    if not src.exists():
        console.print(f"[red]✗ built-in plugin template not found: {src}[/red]")
        sys.exit(1)

    console.print(f"[bold]plugin template[/bold]  {plugin_template}")
    console.print(f"  source:      {src}")
    console.print(f"  destination: {dst}")

    if dry_run:
        console.print("\n[dim][DRY RUN] No file written.[/dim]")
        return dst

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    console.print(f"\n  [green]✓[/green] copied → [bold]{dst}[/bold]")
    return dst


def _spec_to_migration_yaml(
    spec, *, target_host: str = None, target_strategy: str = None
) -> dict:
    """Convert ParsedSpec to migration.yaml dict."""
    import yaml as _yaml

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
        hint_map = {
            "docker": "docker_full",
            "podman": "podman_quadlet",
            "k3s": "k3s",
            "systemd": "systemd",
        }
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

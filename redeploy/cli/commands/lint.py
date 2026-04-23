"""lint command — static analysis of migration specs before deployment."""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ...analyze import SpecAnalyzer


@click.command()
@click.argument("spec_file", default=None, required=False, type=click.Path(), metavar="SPEC")
@click.option("--env", "env_name", default="", help="Named environment from redeploy.yaml")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
@click.option("--exit-zero", is_flag=True, help="Exit 0 even if errors found")
@click.pass_context
def lint(ctx, spec_file, env_name, as_json, exit_zero):
    """Static analysis of a migration spec (YAML or markpact .md).

    Detects missing files, broken references, missing command_ref blocks,
    docker-compose inconsistencies, and hardcoded external paths.
    """
    console = Console()
    from ...cli.core import load_spec_or_exit
    from ...models import ProjectManifest

    manifest = ProjectManifest.find_and_load(Path.cwd())
    resolved = spec_file or (manifest.spec if manifest else "migration.yaml")

    if not Path(resolved).exists():
        console.print(f"[red]✗ spec file not found: {resolved}[/red]")
        sys.exit(1)

    spec = load_spec_or_exit(console, resolved)

    if manifest and env_name:
        if env_name not in manifest.environments:
            console.print(f"[yellow]⚠ env '{env_name}' not in redeploy.yaml[/yellow]")
        manifest.apply_to_spec(spec, env_name=env_name)

    analyzer = SpecAnalyzer(base_dir=Path(resolved).parent)
    _, result = analyzer.analyze_file(Path(resolved))

    if as_json:
        import json
        out = {
            "passed": result.passed,
            "errors": len(result.errors()),
            "warnings": len(result.warnings()),
            "issues": [
                {
                    "severity": i.severity.value,
                    "category": i.category,
                    "step_id": i.step_id,
                    "message": i.message,
                    "suggestion": i.suggestion,
                }
                for i in result.issues
            ],
        }
        console.print(json.dumps(out, indent=2))
    else:
        if result.passed and not result.issues:
            console.print("[green]✓ No issues found[/green]")
        else:
            if result.errors():
                console.print(f"[red]✗ {len(result.errors())} error(s)[/red]")
            if result.warnings():
                console.print(f"[yellow]⚠ {len(result.warnings())} warning(s)[/yellow]")

            t = Table(show_header=True, box=None, padding=(0, 2))
            t.add_column("Severity", width=8)
            t.add_column("Category", width=12)
            t.add_column("Step", width=20)
            t.add_column("Message")
            t.add_column("Suggestion", style="dim")
            for i in result.issues:
                sev = f"[red]{i.severity.value}[/red]" if i.severity.value == "error" else f"[yellow]{i.severity.value}[/yellow]"
                t.add_row(sev, i.category, i.step_id or "—", i.message, i.suggestion or "")
            console.print(t)

    if not exit_zero and not result.passed:
        sys.exit(1)

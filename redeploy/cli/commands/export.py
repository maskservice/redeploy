"""export command — Convert between redeploy.css and redeploy.yaml formats."""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console


@click.command("export")
@click.option(
    "--format", "fmt", default="yaml", type=click.Choice(["css", "yaml"]),
    help="Output format (css or yaml)"
)
@click.option(
    "-o", "--output", default=None, type=click.Path(),
    help="Output file (default: print to stdout)"
)
@click.option(
    "--file", "src_file", default=None, type=click.Path(),
    help="Source file to convert (auto-detected if omitted)"
)
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
    console = Console(stderr=True)

    src = _find_export_source(src_file, console)

    if not src or not src.exists():
        console.print("[red]✗ No redeploy.css or redeploy.yaml found[/red]")
        sys.exit(1)

    console.print(f"[dim]source: {src}[/dim]")

    # Load manifest based on source type
    if src.suffix in (".css", ".less"):
        manifest, templates = _load_manifest_from_css(src)
    else:
        manifest, templates = _load_manifest_from_yaml(src)

    if not manifest:
        console.print("[red]✗ Could not parse manifest[/red]")
        sys.exit(1)

    # Export to requested format
    if fmt == "css":
        out = _export_to_css(manifest, templates)
    else:
        out = _export_to_yaml(manifest)

    if output:
        Path(output).write_text(out)
        console.print(f"[green]✓[/green] written to {output}")
    else:
        print(out)


def _find_export_source(src_file, console) -> Path | None:
    """Find export source file."""
    from ...models import ProjectManifest

    if src_file:
        return Path(src_file)
    src = ProjectManifest.find_css(Path.cwd())
    if not src:
        src = next(
            (Path.cwd() / f for f in ("redeploy.yaml",) if (Path.cwd() / f).exists()), None
        )
    if not src:
        for d in list(Path.cwd().parents)[:3]:
            for f in ("redeploy.css", "redeploy.less", "redeploy.yaml"):
                if (d / f).exists():
                    return d / f
    return src


def _load_manifest_from_css(src):
    """Load manifest from CSS file."""
    from ...dsl.loader import load_css

    result = load_css(src)
    return result.manifest, result.templates


def _load_manifest_from_yaml(src):
    """Load manifest from YAML file."""
    from ...models import ProjectManifest
    import yaml as _yaml

    with src.open() as f:
        manifest = ProjectManifest(**_yaml.safe_load(f))
    return manifest, []


def _export_to_css(manifest, templates) -> str:
    """Export manifest to CSS format."""
    from ...dsl.loader import manifest_to_css, templates_to_css

    out = manifest_to_css(manifest)
    if templates:
        out += "\n\n" + templates_to_css(templates)
    return out


def _export_to_yaml(manifest) -> str:
    """Export manifest to YAML format."""
    import yaml as _yaml

    return _yaml.dump(
        manifest.model_dump(exclude_none=True, exclude_defaults=True),
        default_flow_style=False,
        allow_unicode=True,
    )

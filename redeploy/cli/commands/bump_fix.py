"""bump and fix commands — version bumping and self-healing deploy."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import click
from rich.console import Console


# ── helpers ──────────────────────────────────────────────────────────────────

def _find_spec(spec_arg: str) -> Path:
    """Resolve spec path from '.' (use migration.yaml/migration.md) or explicit path."""
    p = Path(spec_arg)
    if p.is_dir():
        for candidate in ["migration.md", "migration.yaml", "migration.yml"]:
            c = p / candidate
            if c.exists():
                return c
        # also check one level up for c2004 project pattern
        for sub in sorted(p.rglob("migration.md"), key=lambda x: len(x.parts)):
            return sub
        for sub in sorted(p.rglob("migration.yaml"), key=lambda x: len(x.parts)):
            return sub
        raise click.ClickException(f"No migration spec found under {spec_arg!r}")
    if not p.exists():
        raise click.ClickException(f"Spec not found: {spec_arg!r}")
    return p


def _find_version_file(spec_path: Path) -> Path | None:
    """Walk up from spec to find VERSION file."""
    for parent in [spec_path.parent, spec_path.parent.parent,
                   spec_path.parent.parent.parent, Path.cwd()]:
        v = parent / "VERSION"
        if v.exists():
            return v
    return None


def _bump_patch(version: str) -> str:
    """Bump the patch component: 1.0.30 → 1.0.31."""
    m = re.match(r"^(\d+\.\d+\.)(\d+)(.*)", version.strip())
    if not m:
        raise click.ClickException(f"Cannot parse version: {version!r}")
    return f"{m.group(1)}{int(m.group(2)) + 1}{m.group(3)}"


def _bump_version_file(version_file: Path, console: Console) -> str:
    """Read, increment patch, write back. Returns new version."""
    old = version_file.read_text().strip()
    new = _bump_patch(old)
    version_file.write_text(new + "\n")
    console.print(f"[green]bump[/green] {old} → [bold]{new}[/bold]  ({version_file})")
    return new


def _update_migration_header(spec_path: Path, new_version: str) -> None:
    """Update 'version:' line in spec file header if present."""
    text = spec_path.read_text()
    updated = re.sub(
        r"^(version:\s*)[\w\.\-]+",
        lambda m: f"{m.group(1)}{new_version}",
        text, flags=re.MULTILINE
    )
    if updated != text:
        spec_path.write_text(updated)


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        for candidate in [Path(".env"), Path.home() / ".redeploy" / ".env"]:
            if candidate.exists():
                load_dotenv(candidate, override=False)
                break
    except ImportError:
        pass


# ── bump command ──────────────────────────────────────────────────────────────

@click.command("bump")
@click.argument("spec_or_dir", default=".", metavar="PATH")
@click.option(
    "--minor", is_flag=True, help="Bump minor instead of patch (1.0.x → 1.1.0)"
)
@click.option(
    "--major", is_flag=True, help="Bump major instead of patch (1.x.y → 2.0.0)"
)
def bump_cmd(spec_or_dir, minor, major):
    """Bump the project version (patch by default).

    \b
    PATH is a spec file or directory containing migration.yaml / migration.md.
    '.' uses the current directory.

    \b
    Examples:
        redeploy bump .
        redeploy bump redeploy/pi109/migration.md
        redeploy bump . --minor
    """
    console = Console()
    spec_path = _find_spec(spec_or_dir)
    version_file = _find_version_file(spec_path)

    if version_file is None:
        console.print(
            "[yellow]No VERSION file found — creating one alongside spec[/yellow]"
        )
        version_file = spec_path.parent / "VERSION"
        version_file.write_text("1.0.0\n")

    old = version_file.read_text().strip()

    if major:
        m = re.match(r"^(\d+)(.*)", old)
        new = f"{int(m.group(1)) + 1}.0.0" if m else old
    elif minor:
        m = re.match(r"^(\d+)\.(\d+)(.*)", old)
        new = f"{m.group(1)}.{int(m.group(2)) + 1}.0" if m else old
    else:
        new = _bump_patch(old)

    version_file.write_text(new + "\n")
    console.print(f"[green]bump[/green] {old} → [bold]{new}[/bold]  ({version_file})")
    _update_migration_header(spec_path, new)
    console.print(f"[dim]updated spec header: {spec_path}[/dim]")


# ── fix command ───────────────────────────────────────────────────────────────

@click.command("fix")
@click.argument("spec_or_dir", default=".", metavar="PATH")
@click.option(
    "--hint", "-m", default=None, metavar="TEXT",
    help='Describe the problem, e.g. --hint "brak ikon SVG w menu"'
)
@click.option(
    "--bump/--no-bump", default=True,
    help="Bump version before deploying (default: on)"
)
@click.option(
    "--retries", default=3, show_default=True,
    help="Max LLM self-healing attempts"
)
@click.option("--dry-run", is_flag=True, help="Plan only, no apply")
@click.option(
    "--env", "env_name", default="",
    help="Named environment from redeploy.yaml"
)
def fix_cmd(spec_or_dir, hint, bump, retries, dry_run, env_name):
    """Self-healing deploy: bump version, then run with LLM auto-fix on failure.

    \b
    PATH is a spec file or directory containing migration.yaml / migration.md.
    '.' uses the current directory.

    \b
    Examples:
        redeploy fix .
        redeploy fix . --hint "brak ikon SVG w menu"
        redeploy fix redeploy/pi109/migration.md --no-bump
        redeploy fix . --hint "chromium nie startuje" --retries 5
    """
    console = Console()
    _load_dotenv()

    spec_path = _find_spec(spec_or_dir)

    # Bump version first
    version = ""
    if bump and not dry_run:
        version_file = _find_version_file(spec_path)
        if version_file is None:
            version_file = spec_path.parent / "VERSION"
            version_file.write_text("1.0.0\n")
        version = _bump_version_file(version_file, console)
        _update_migration_header(spec_path, version)

    if hint:
        console.print(f"[cyan]hint:[/cyan] {hint}")

    # Load spec + plan (reuse plan_apply helpers)
    from ..core import load_spec_or_exit
    from ...plan import Planner
    from ...plugins import load_user_plugins
    from ...models import ProjectManifest

    manifest = ProjectManifest.find_and_load(Path.cwd())
    spec = load_spec_or_exit(console, str(spec_path))

    # Apply manifest overlays if any
    if manifest and env_name:
        env = manifest.environments.get(env_name)
        if env:
            if env.host:
                spec.target.host = env.host

    console.print(
        f"\n[bold]plan[/bold]  [dim]({spec_path})[/dim]"
    )
    planner = Planner.from_spec(spec)
    migration = planner.run()

    from ..display import print_plan_table
    print_plan_table(console, migration)

    if dry_run:
        console.print("\n[dim]--dry-run: stopping before apply[/dim]")
        return

    load_user_plugins()

    _print_banner(console, hint)
    version = version or _detect_version(spec_path)

    from ...heal import HealRunner
    runner = HealRunner(
        migration=migration,
        spec_path=spec_path,
        host=migration.host,
        fix_hint=hint or "",
        max_retries=retries,
        dry_run=dry_run,
        console=console,
        version=version,
    )
    ok = runner.run()
    if not ok:
        sys.exit(1)


def _print_banner(console: Console, hint: str | None) -> None:
    console.print("\n[bold green]fix[/bold green] [dim]heal mode: on[/dim]")
    if hint:
        console.print(f"[cyan]user hint:[/cyan] {hint}")


def _detect_version(spec_path: Path) -> str:
    vf = _find_version_file(spec_path)
    return vf.read_text().strip() if vf else ""

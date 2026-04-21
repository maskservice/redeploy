"""bump and fix commands — version bumping and self-healing deploy."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import click
from rich.console import Console


# ── helpers ──────────────────────────────────────────────────────────────────

def _find_spec(spec_arg: str) -> Path:
    """Resolve spec path from '.' / dir or explicit file.

    Discovery order when given a directory:
    1. Direct match:  <dir>/migration.{md,yaml,yml}
    2. Project pattern: <dir>/redeploy/*/migration.{md,yaml,yml}  (e.g. redeploy/pi109/migration.md)
    3. Recursive fallback: first migration spec found anywhere under <dir>

    When multiple candidates are found the user is prompted to choose.
    """
    p = Path(spec_arg).resolve()
    if not p.is_dir():
        if not p.exists():
            raise click.ClickException(f"Spec not found: {spec_arg!r}")
        return p

    # 1. Direct match in the given directory
    for candidate in ("migration.md", "migration.yaml", "migration.yml"):
        c = p / candidate
        if c.exists():
            return c

    # 2. Project pattern: redeploy/<target>/migration.*
    project_specs: list[Path] = []
    redeploy_dir = p / "redeploy"
    if redeploy_dir.is_dir():
        for sub in sorted(redeploy_dir.iterdir()):
            if sub.is_dir():
                for candidate in ("migration.md", "migration.yaml", "migration.yml"):
                    c = sub / candidate
                    if c.exists():
                        project_specs.append(c)
                        break

    if len(project_specs) == 1:
        return project_specs[0]

    if len(project_specs) > 1:
        return _prompt_choose_spec(project_specs, p)

    # 3. Recursive fallback
    all_specs: list[Path] = []
    for pattern in ("migration.md", "migration.yaml", "migration.yml"):
        all_specs.extend(sorted(p.rglob(pattern), key=lambda x: len(x.parts)))

    if not all_specs:
        raise click.ClickException(f"No migration spec found under {spec_arg!r}")
    if len(all_specs) == 1:
        return all_specs[0]
    return _prompt_choose_spec(all_specs, p)


def _prompt_choose_spec(specs: list[Path], base: Path) -> Path:
    """Interactively ask the user to pick from multiple migration specs."""
    console = Console(stderr=True)
    console.print(f"[bold yellow]Multiple migration specs found:[/bold yellow]")
    for i, s in enumerate(specs, 1):
        try:
            rel = s.relative_to(base)
        except ValueError:
            rel = s
        console.print(f"  [cyan]{i}[/cyan]. {rel}")
    raw = click.prompt("Choose spec", default="1")
    try:
        idx = int(raw) - 1
        if not (0 <= idx < len(specs)):
            raise ValueError
    except ValueError:
        raise click.ClickException(f"Invalid choice: {raw!r}")
    return specs[idx]


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
    """Update version references in spec file header.

    Handles multiple formats:
      version: 1.0.30
      name: "c2004 pi109 deploy v1.0.30"
      description: "Deploy c2004 v1.0.30 na ..."
    Also updates Environment=SERVICE_VERSION= in *.container quadlet files.
    """
    text = spec_path.read_text()
    # ^version: x.y.z
    updated = re.sub(r"^(version:\s*)[\w\.\-]+", lambda m: f"{m.group(1)}{new_version}", text, flags=re.MULTILINE)
    # name/description: "... vX.Y.Z ..."
    updated = re.sub(r'((?:name|description):\s*"[^"]*\bv)\d+\.\d+\.\d+', lambda m: f"{m.group(1)}{new_version}", updated)
    if updated != text:
        spec_path.write_text(updated)

    # Update SERVICE_VERSION= in *.container Quadlet files adjacent to the spec
    # Search up to 3 parent dirs for quadlet/ or redeploy/quadlet-only/ directories
    _update_quadlet_service_version(spec_path.parent, new_version)


def _update_quadlet_service_version(start: Path, new_version: str) -> None:
    """Find *.container files near the project root and update SERVICE_VERSION=.

    Walk UP from `start` to find the project root (directory containing VERSION
    or the highest ancestor within 6 levels), then rglob ALL *.container files
    from that root so all quadlet subdirs are covered.
    """
    pattern = re.compile(r"^(Environment=SERVICE_VERSION=)[\w\.\-]+", re.MULTILINE)

    # Find project root: walk up until we find a VERSION file or hit 6 levels
    root = start.resolve()
    for _ in range(6):
        if (root / "VERSION").exists():
            break
        parent = root.parent
        if parent == root:
            break
        root = parent

    updated_count = 0
    for container_file in root.rglob("*.container"):
        text = container_file.read_text()
        new_text = pattern.sub(lambda m: f"{m.group(1)}{new_version}", text)
        if new_text != text:
            container_file.write_text(new_text)
            updated_count += 1


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
@click.option("--minor", is_flag=True, help="Bump minor instead of patch (1.0.x → 1.1.0)")
@click.option("--major", is_flag=True, help="Bump major instead of patch (1.x.y → 2.0.0)")
@click.option(
    "--retries", default=3, show_default=True,
    help="Max LLM self-healing attempts"
)
@click.option("--dry-run", is_flag=True, help="Plan only, no apply")
@click.option(
    "--env", "env_name", default="",
    help="Named environment from redeploy.yaml"
)
def fix_cmd(spec_or_dir, hint, bump, minor, major, retries, dry_run, env_name):
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
        old = version_file.read_text().strip()
        if major:
            m = re.match(r"^(\d+)(.*)", old)
            version = f"{int(m.group(1)) + 1}.0.0" if m else old
        elif minor:
            m = re.match(r"^(\d+)\.(\d+)(.*)", old)
            version = f"{m.group(1)}.{int(m.group(2)) + 1}.0" if m else old
        else:
            version = _bump_patch(old)
        version_file.write_text(version + "\n")
        console.print(f"[green]bump[/green] {old} → [bold]{version}[/bold]  ({version_file})")
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

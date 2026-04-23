"""gh-workflow command - inspect and trigger GitHub Actions workflows on demand."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.table import Table


def _find_repo_root(start: Path) -> Path | None:
    cur = start.resolve()
    for p in [cur, *cur.parents]:
        if (p / ".git").exists() or (p / ".github" / "workflows").exists():
            return p
    return None


def _resolve_repo_root(repo_root_opt: str | None) -> Path:
    root = Path(repo_root_opt).resolve() if repo_root_opt else _find_repo_root(Path.cwd())
    if not root:
        raise click.ClickException(
            "Could not detect repository root. Use --repo-root PATH."
        )
    return root


def _workflows_dir(repo_root: Path) -> Path:
    wf_dir = repo_root / ".github" / "workflows"
    if not wf_dir.exists():
        raise click.ClickException(f"No workflows directory found: {wf_dir}")
    return wf_dir


def _load_yaml(path: Path) -> dict:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise click.ClickException(f"Failed to parse workflow YAML: {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise click.ClickException(f"Workflow file must contain a YAML mapping: {path}")
    return raw


def _on_section(raw: dict) -> object:
    # PyYAML can parse key "on" as boolean True (YAML 1.1).
    return raw.get("on", raw.get(True))


def _trigger_list(on_value: object) -> list[str]:
    if isinstance(on_value, str):
        return [on_value]
    if isinstance(on_value, list):
        return [str(x) for x in on_value]
    if isinstance(on_value, dict):
        return [str(k) for k in on_value.keys()]
    return []


def _has_workflow_dispatch(on_value: object) -> bool:
    if isinstance(on_value, str):
        return on_value == "workflow_dispatch"
    if isinstance(on_value, list):
        return "workflow_dispatch" in on_value
    if isinstance(on_value, dict):
        return "workflow_dispatch" in on_value
    return False


def _collect_workflow_meta(path: Path) -> dict:
    raw = _load_yaml(path)
    on_value = _on_section(raw)
    jobs = raw.get("jobs", {})
    job_names = list(jobs.keys()) if isinstance(jobs, dict) else []
    return {
        "file": path.name,
        "name": str(raw.get("name") or path.stem),
        "triggers": _trigger_list(on_value),
        "dispatch": _has_workflow_dispatch(on_value),
        "jobs": job_names,
    }


def _resolve_workflow_identifier(wf_dir: Path, workflow: str) -> Path:
    candidate = wf_dir / workflow
    if candidate.exists() and candidate.is_file():
        return candidate

    for ext in (".yml", ".yaml"):
        p = wf_dir / f"{workflow}{ext}"
        if p.exists() and p.is_file():
            return p

    for p in sorted(wf_dir.glob("*.y*ml")):
        meta = _collect_workflow_meta(p)
        if meta["name"] == workflow or p.stem == workflow:
            return p

    available = ", ".join(sorted(p.name for p in wf_dir.glob("*.y*ml")))
    raise click.ClickException(
        f"Workflow not found: {workflow}. Available files: {available}"
    )


def _gh_available() -> bool:
    return shutil.which("gh") is not None


def _parse_fields(fields: tuple[str, ...]) -> list[str]:
    parsed: list[str] = []
    for item in fields:
        if "=" not in item:
            raise click.ClickException(
                f"Invalid --field '{item}'. Expected KEY=VALUE."
            )
        parsed.append(item)
    return parsed


@click.group("gh-workflow")
def gh_workflow_cmd():
    """Inspect and run GitHub Actions workflows on demand."""


@gh_workflow_cmd.command("list")
@click.option("--repo-root", default=None, type=click.Path(file_okay=False, path_type=str),
              help="Repository root (auto-detected if omitted)")
def gh_workflow_list(repo_root: str | None):
    """List workflow files and whether they are dispatchable."""
    console = Console()
    root = _resolve_repo_root(repo_root)
    wf_dir = _workflows_dir(root)
    files = sorted(wf_dir.glob("*.y*ml"))
    if not files:
        console.print(f"[yellow]No workflow files found in {wf_dir}[/yellow]")
        return

    table = Table(title=f"GitHub Workflows ({root.name})")
    table.add_column("File", style="cyan")
    table.add_column("Name")
    table.add_column("Dispatch", justify="center")
    table.add_column("Triggers")
    table.add_column("Jobs", justify="right")

    for path in files:
        meta = _collect_workflow_meta(path)
        dispatch = "yes" if meta["dispatch"] else "no"
        triggers = ", ".join(meta["triggers"]) if meta["triggers"] else "-"
        table.add_row(meta["file"], meta["name"], dispatch, triggers, str(len(meta["jobs"])))

    console.print(table)


@gh_workflow_cmd.command("analyze")
@click.argument("workflow", required=False, default=None)
@click.option("--repo-root", default=None, type=click.Path(file_okay=False, path_type=str),
              help="Repository root (auto-detected if omitted)")
def gh_workflow_analyze(workflow: str | None, repo_root: str | None):
    """Analyze one workflow (or all workflows) for triggers/jobs/dispatch readiness."""
    console = Console()
    root = _resolve_repo_root(repo_root)
    wf_dir = _workflows_dir(root)

    selected: list[Path]
    if workflow:
        selected = [_resolve_workflow_identifier(wf_dir, workflow)]
    else:
        selected = sorted(wf_dir.glob("*.y*ml"))

    for path in selected:
        meta = _collect_workflow_meta(path)
        console.print(f"[bold]{meta['name']}[/bold]  [dim]({meta['file']})[/dim]")
        console.print(f"  dispatchable: {'yes' if meta['dispatch'] else 'no'}")
        console.print(
            "  triggers: "
            + (", ".join(meta["triggers"]) if meta["triggers"] else "none")
        )
        if meta["jobs"]:
            console.print("  jobs: " + ", ".join(meta["jobs"]))
        else:
            console.print("  jobs: none")
        if not meta["dispatch"]:
            console.print(
                "  [yellow]hint:[/yellow] add 'workflow_dispatch:' under 'on:' to run on demand"
            )
        console.print()


@gh_workflow_cmd.command("run")
@click.argument("workflow")
@click.option("--repo-root", default=None, type=click.Path(file_okay=False, path_type=str),
              help="Repository root (auto-detected if omitted)")
@click.option("--ref", default=None, help="Git ref (branch/tag/SHA) for workflow_dispatch")
@click.option(
    "--field",
    "fields",
    multiple=True,
    help="workflow_dispatch input as KEY=VALUE (repeatable)",
)
@click.option("--watch", is_flag=True, help="Watch the newly started run until completion")
@click.option("--dry-run", is_flag=True, help="Print commands without executing")
def gh_workflow_run(
    workflow: str,
    repo_root: str | None,
    ref: str | None,
    fields: tuple[str, ...],
    watch: bool,
    dry_run: bool,
):
    """Trigger a GitHub Actions workflow_dispatch run on demand via gh CLI."""
    console = Console()
    root = _resolve_repo_root(repo_root)
    wf_dir = _workflows_dir(root)
    wf_path = _resolve_workflow_identifier(wf_dir, workflow)
    meta = _collect_workflow_meta(wf_path)

    if not meta["dispatch"]:
        raise click.ClickException(
            f"Workflow '{meta['file']}' is not dispatchable (missing workflow_dispatch trigger)."
        )

    if not _gh_available():
        raise click.ClickException(
            "GitHub CLI 'gh' is required. Install gh and run 'gh auth login'."
        )

    parsed_fields = _parse_fields(fields)

    run_cmd: list[str] = ["gh", "workflow", "run", wf_path.name]
    if ref:
        run_cmd.extend(["--ref", ref])
    for item in parsed_fields:
        run_cmd.extend(["-f", item])

    console.print(f"[bold]workflow:[/bold] {meta['name']} ({wf_path.name})")
    console.print("[bold]command:[/bold] " + " ".join(run_cmd))

    if dry_run:
        return

    result = subprocess.run(run_cmd, cwd=str(root), capture_output=True, text=True)
    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip() or "gh workflow run failed"
        raise click.ClickException(msg)

    if result.stdout.strip():
        console.print(result.stdout.strip())

    if not watch:
        return

    list_cmd = [
        "gh",
        "run",
        "list",
        "--workflow",
        wf_path.name,
        "--limit",
        "1",
        "--json",
        "databaseId,url,status,conclusion",
    ]
    list_res = subprocess.run(list_cmd, cwd=str(root), capture_output=True, text=True)
    if list_res.returncode != 0:
        msg = list_res.stderr.strip() or list_res.stdout.strip() or "gh run list failed"
        raise click.ClickException(msg)

    try:
        entries = json.loads(list_res.stdout)
    except Exception as exc:
        raise click.ClickException(f"Could not parse gh run list output: {exc}") from exc

    if not entries:
        raise click.ClickException("No run found to watch.")

    run_id = str(entries[0].get("databaseId", "")).strip()
    run_url = str(entries[0].get("url", "")).strip()
    if run_url:
        console.print(f"[bold]run:[/bold] {run_url}")
    if not run_id:
        raise click.ClickException("Run ID missing from gh run list output.")

    watch_cmd = ["gh", "run", "watch", run_id, "--exit-status"]
    watch_res = subprocess.run(watch_cmd, cwd=str(root))
    if watch_res.returncode != 0:
        sys.exit(watch_res.returncode)

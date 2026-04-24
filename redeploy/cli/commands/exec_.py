"""exec and exec-multi commands — Execute scripts from markdown codeblocks."""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table


@click.command("exec")
@click.argument("ref", required=True)
@click.option("--host", required=True, help="SSH host (user@ip) or 'local'")
@click.option(
    "--file", "markdown_file", default=None, type=click.Path(),
    help="Markdown file (required if ref doesn't specify file)"
)
@click.option("--dry-run", is_flag=True, help="Show script without executing")
@click.option("--timeout", default=300, help="Step timeout in seconds")
@click.pass_context
def exec_cmd(ctx, ref, host, markdown_file, dry_run, timeout):
    """Execute a script from a markdown codeblock by reference.

    REF format: #section-id or ./file.md#section-id or just ref-id (for markpact:ref)

    Extracts the script from a ```bash codeblock in the specified section
    or from a codeblock marked with markpact:ref <id>.

    \b
    Examples:
        redeploy exec '#kiosk-browser-configuration-script' --host pi@192.168.188.108 --file migration.md
        redeploy exec './migration.md#kiosk-script' --host pi@192.168.188.108
        redeploy exec '#install-deps' --host root@server.com --file deploy.md --dry-run
        redeploy exec 'kiosk-browser-configuration-script' --host pi@192.168.188.108 --file migration.md
    """
    from ...apply.executor import Executor, MigrationPlan, MigrationStep, StepAction

    console = Console()

    # Parse reference
    if "#" in ref:
        file_part, section_id = ref.split("#", 1)
        if file_part:
            md_path = Path(file_part)
        elif markdown_file:
            md_path = Path(markdown_file)
        else:
            console.print("[red]✗ No file specified in ref and no --file provided[/red]")
            sys.exit(1)
        ref_id = section_id
    else:
        ref_id = ref
        if not markdown_file:
            console.print("[red]✗ --file required when ref doesn't specify file[/red]")
            sys.exit(1)
        md_path = Path(markdown_file)

    if not md_path.exists():
        console.print(f"[red]✗ File not found: {md_path}[/red]")
        sys.exit(1)

    # Extract script from markdown
    console.print(f"[dim]Reading {md_path}...[/dim]")
    md_content = md_path.read_text(encoding="utf-8")

    result = _extract_script_for_ref(md_content, ref_id)
    if result is None:
        console.print(f"[red]✗ Could not find bash script with ref '#{ref_id}'[/red]")
        console.print("[dim]  Make sure there's either:[/dim]")
        console.print("[dim]    - A codeblock: ```bash markpact:ref {ref_id}[/dim]")
        console.print("[dim]    - Or a ## section heading and ```bash codeblock[/dim]")
        sys.exit(1)
    script, lookup_method = result

    console.print(f"[green]✓[/green] Found script ({len(script)} chars) via {lookup_method} '#{ref_id}'")

    if dry_run:
        console.print(f"\n[bold]Script content (dry-run):[/bold]")
        console.print("```bash")
        console.print(script)
        console.print("```")
        return

    # Execute script on remote host
    console.print(f"\n[bold]Executing on {host}...[/bold]")

    step = MigrationStep(
        id=f"exec_{ref_id}",
        action=StepAction.INLINE_SCRIPT,
        description=f"Execute script from #{ref_id}",
        command=script,
        timeout=timeout,
    )
    plan = MigrationPlan(
        host=host,
        app="exec",
        from_strategy="unknown",
        to_strategy="unknown",
        steps=[step],
    )

    executor = Executor(plan, dry_run=False)
    ok = executor.run()

    if not ok:
        sys.exit(1)

    console.print(f"[green]✓ Script executed successfully[/green]")


@click.command("exec-multi")
@click.argument("refs")
@click.option("--host", required=True, help="SSH host (user@ip) or 'local'")
@click.option(
    "--file", "markdown_file", required=True, type=click.Path(),
    help="Markdown file containing scripts"
)
@click.option("--dry-run", is_flag=True, help="Show scripts without executing")
@click.option("--timeout", default=300, help="Step timeout in seconds")
@click.option("--parallel", is_flag=True, help="Execute scripts in parallel (default: sequential)")
@click.pass_context
def exec_multi_cmd(ctx, refs, host, markdown_file, dry_run, timeout, parallel):
    """Execute multiple scripts from markdown codeblocks by reference.

    REFS format: comma-separated list of ref ids (markpact:ref or section headings)

    \b
    Examples:
        redeploy exec-multi 'kiosk-script,install-deps,cleanup' \
            --host pi@192.168.188.108 --file migration.md

        redeploy exec-multi '#section1,#section2' \
            --host root@server.com --file deploy.md --dry-run
    """
    console = Console()
    md_path = Path(markdown_file)

    if not md_path.exists():
        console.print(f"[red]✗ File not found: {md_path}[/red]")
        sys.exit(1)

    # Parse refs
    ref_list = [r.strip() for r in refs.split(",")]
    console.print(f"[bold]Loading {len(ref_list)} scripts from {md_path}...[/bold]")

    # Extract all scripts
    scripts = _extract_all_scripts(md_path, ref_list, console)

    if dry_run:
        console.print(f"\n[bold]Scripts (dry-run):[/bold]")
        for ref_id, script, _ in scripts:
            console.print(f"\n--- {ref_id} ---")
            console.print("```bash")
            console.print(script[:500] + ("..." if len(script) > 500 else ""))
            console.print("```")
        return

    # Execute scripts
    console.print(f"\n[bold]Executing on {host}...[/bold]")

    results = []
    for ref_id, script, _ in scripts:
        console.print(f"  Running {ref_id}...", end=" ")
        ok = _execute_single_script(ref_id, script, host, timeout)
        results.append((ref_id, ok))

        if ok:
            console.print("[green]✓[/green]")
        else:
            console.print("[red]✗[/red]")

    # Summary table
    _print_execution_results(console, results)

    if not all(ok for _, ok in results):
        sys.exit(1)

    console.print(f"\n[green]✓ All {len(scripts)} scripts executed successfully[/green]")


def _extract_all_scripts(md_path, ref_list, console) -> list[tuple[str, str, str]]:
    """Extract all scripts from markdown by ref list."""
    md_content = md_path.read_text(encoding="utf-8")
    scripts: list[tuple[str, str, str]] = []

    for ref_id in ref_list:
        result = _extract_script_for_ref(md_content, ref_id)
        if result is None:
            console.print(f"[red]✗ Could not find script: {ref_id}[/red]")
            sys.exit(1)
        script, lookup_method = result
        scripts.append((ref_id, script, lookup_method))
        console.print(f"  [green]✓[/green] {ref_id} ({len(script)} chars, {lookup_method})")

    return scripts


def _extract_script_for_ref(md_content, ref_id) -> tuple[str, str] | None:
    """Extract script for a single ref."""
    from ...markpact import resolve_script_ref

    result = resolve_script_ref(md_content, ref_id, language="bash")
    if result is None:
        return None
    return result


def _execute_single_script(ref_id, script, host, timeout) -> bool:
    """Execute a single script and return success status."""
    from ...apply.executor import Executor, MigrationPlan, MigrationStep, StepAction

    step = MigrationStep(
        id=f"exec_{ref_id}",
        action=StepAction.INLINE_SCRIPT,
        description=f"Execute script from {ref_id}",
        command=script,
        timeout=timeout,
    )
    plan = MigrationPlan(
        host=host,
        app="exec-multi",
        from_strategy="unknown",
        to_strategy="unknown",
        steps=[step],
    )

    executor = Executor(plan, dry_run=False)
    return executor.run()


def _print_execution_results(console, results) -> None:
    """Print execution results table."""
    t = Table(show_header=True, box=None)
    t.add_column("Script")
    t.add_column("Status")
    for ref_id, ok in results:
        status = "[green]✓ OK[/green]" if ok else "[red]✗ Failed[/red]"
        t.add_row(ref_id, status)
    console.print(t)

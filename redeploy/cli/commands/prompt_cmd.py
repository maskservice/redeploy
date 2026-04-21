"""redeploy prompt command — natural language → redeploy invocation via LLM.

Usage:
    redeploy prompt "wdróż c2004 na pi109"
    redeploy prompt -P "zbuilduj i wypchnij nową wersję"
    redeploy prompt "show deploy plan for pi109" --dry-run
    redeploy prompt "what specs are available?" --schema-only
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a DevOps assistant that translates natural language instructions into
redeploy CLI commands.

You will receive a JSON schema describing the current workspace with:
- cwd         : current working directory
- version     : project version
- git_branch  : current git branch
- specs       : list of discovered migration specs (path, version, target, name)
- commands    : catalogue of available redeploy commands with descriptions and examples

Your task: map the user's instruction to a single redeploy command.

Output ONLY valid JSON (no markdown fences, no extra text) with this structure:
{
  "thought":  "<one sentence reasoning>",
  "argv":     ["redeploy", "<command>", "<arg1>", ...],
  "confirm":  true | false,
  "human_summary": "<one sentence in the same language as the user's prompt>"
}

Rules:
- argv[0] MUST be "redeploy".
- Use relative paths for specs (relative to cwd).
- If the user's intent is unclear, pick the safest command (e.g. "plan" with --dry-run=true).
- Set confirm=false ONLY for read-only/safe commands (plan, inspect, status, audit, diff, diagnose).
- Set confirm=true for commands that change state (fix, run, bump, push, init).
- If the user explicitly says "dry run" / "pokaż" / "sprawdź" / "plan", prefer --dry-run.
- Never invent spec paths — use only paths from the schema["specs"] list.
- If no matching spec exists, return argv=["redeploy", "plan", "--help"] and explain in human_summary.
"""


def _call_llm(schema: dict, user_prompt: str) -> str:
    """Call LiteLLM with schema + prompt. Returns raw LLM text."""
    try:
        import litellm
        litellm.suppress_debug_info = True
        litellm.verbose = False
    except ImportError:
        raise click.ClickException(
            "litellm is not installed. Run: pip install litellm"
        )

    # load .env for API keys
    try:
        from dotenv import load_dotenv
        for candidate in [Path(".env"), Path.home() / ".redeploy" / ".env"]:
            if candidate.exists():
                load_dotenv(candidate, override=False)
                break
    except ImportError:
        pass

    model = os.environ.get("LLM_MODEL", "openrouter/anthropic/claude-3.5-haiku")
    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Workspace schema:\n```json\n{json.dumps(schema, indent=2)}\n```\n\n"
                f"User instruction: {user_prompt}"
            ),
        },
    ]

    kwargs: dict = {"model": model, "messages": messages}
    if api_key:
        kwargs["api_key"] = api_key

    resp = litellm.completion(**kwargs)
    return resp.choices[0].message.content.strip()


def _parse_llm_response(raw: str) -> dict:
    """Parse JSON from LLM response, strip accidental fences."""
    # Strip ```json ... ``` if present
    clean = raw.strip()
    if clean.startswith("```"):
        lines = clean.splitlines()
        clean = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        )
    return json.loads(clean)


# ---------------------------------------------------------------------------
# Click command
# ---------------------------------------------------------------------------

@click.command("prompt")
@click.argument("instruction", metavar="INSTRUCTION")
@click.option(
    "--schema-only", is_flag=True,
    help="Print the discovered workspace schema and exit (no LLM call).",
)
@click.option(
    "--dry-run", is_flag=True,
    help="Force --dry-run on whatever command the LLM produces.",
)
@click.option(
    "--yes", "-y", is_flag=True,
    help="Skip confirmation prompt and execute immediately.",
)
@click.option(
    "--show-schema", is_flag=True,
    help="Print the schema sent to the LLM before the result.",
)
def prompt_cmd(instruction: str, schema_only: bool, dry_run: bool, yes: bool, show_schema: bool):
    """Natural-language → redeploy command via LLM.

    \b
    INSTRUCTION is a free-text description of what you want to do.

    \b
    Examples:
        redeploy prompt "deploy c2004 to pi109"
        redeploy prompt "pokaż plan deployu na pi109"
        redeploy prompt "bump version and redeploy" --yes
        redeploy prompt "what specs exist?" --schema-only
    """
    console = Console()

    from redeploy.schema import build_schema

    schema = build_schema()

    if schema_only or show_schema:
        console.print(
            Panel(
                Syntax(json.dumps(schema, indent=2), "json", theme="monokai"),
                title="[bold cyan]Workspace Schema[/bold cyan]",
                border_style="cyan",
            )
        )
        if schema_only:
            return

    console.print(f"[dim]instruction:[/dim] {instruction}")

    # --- LLM call ---
    try:
        raw = _call_llm(schema, instruction)
    except Exception as exc:
        raise click.ClickException(f"LLM call failed: {exc}") from exc

    try:
        result = _parse_llm_response(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        console.print("[red]LLM returned invalid JSON:[/red]")
        console.print(raw)
        raise click.ClickException(f"Cannot parse LLM response: {exc}") from exc

    thought = result.get("thought", "")
    argv: list[str] = result.get("argv", [])
    needs_confirm: bool = result.get("confirm", True)
    summary: str = result.get("human_summary", "")

    if not argv or argv[0] != "redeploy":
        raise click.ClickException(f"LLM returned unexpected argv: {argv!r}")

    # Inject --dry-run if user asked for it (and command supports it)
    if dry_run and "--dry-run" not in argv:
        argv.append("--dry-run")

    # Pretty print the plan
    rendered_cmd = shlex.join(argv)
    console.print()
    console.print(
        Panel(
            f"[bold white]{rendered_cmd}[/bold white]",
            title="[bold green]Generated command[/bold green]",
            border_style="green",
        )
    )
    if thought:
        console.print(f"[dim]reasoning:[/dim] {thought}")
    if summary:
        console.print(f"[cyan]{summary}[/cyan]")
    console.print()

    # Confirmation
    if needs_confirm and not yes:
        click.confirm("Execute?", default=True, abort=True)

    # Execute — replace argv[0] with the actual binary path
    try:
        cmd = [_find_redeploy_bin()] + argv[1:]
        result_proc = subprocess.run(cmd)
        sys.exit(result_proc.returncode)
    except FileNotFoundError as exc:
        raise click.ClickException(f"Cannot run {argv!r}: {exc}") from exc


def _find_redeploy_bin() -> str:
    """Find the redeploy module entry point via current Python interpreter.

    We use `python -m redeploy.cli` style invocation so the correct venv
    Python is always used regardless of cwd.
    """
    import shutil
    # prefer the same executable that's running right now
    if sys.argv and sys.argv[0] and Path(sys.argv[0]).exists():
        return sys.argv[0]
    found = shutil.which("redeploy")
    if found:
        return found
    raise click.ClickException("Cannot locate redeploy binary")

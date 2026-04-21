"""redeploy MCP server — exposes redeploy operations via Model Context Protocol.

Transports:
  stdio  (default, for IDE/Claude Desktop integration)
  sse    (HTTP Server-Sent Events, for remote access)

Run:
  redeploy-mcp                          # stdio (for MCP clients / Claude Desktop)
  redeploy-mcp --transport sse          # SSE on http://0.0.0.0:8811
  redeploy mcp                          # via main CLI
  redeploy mcp --transport sse --port 8811

Tools exposed:
  schema          -- discover specs & workspace state
  plan_spec       -- dry-run a migration spec, return step list
  run_spec        -- apply a migration spec (with confirm option)
  fix_spec        -- self-healing deploy (bump + apply + LLM retry)
  bump_version    -- bump patch/minor/major version
  diagnose        -- run SSH diagnostics on a host
  status          -- show running containers/units on a host
  exec_ssh        -- run an ad-hoc SSH command on a known target
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "redeploy",
    instructions=(
        "redeploy is an infrastructure migration toolkit. "
        "Use schema() first to discover available specs and targets, "
        "then run plan_spec() to preview steps before applying with run_spec() or fix_spec()."
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _redeploy_bin() -> str:
    """Resolve the redeploy binary path (same venv as this process)."""
    import shutil
    if sys.argv and sys.argv[0] and Path(sys.argv[0]).exists():
        return sys.argv[0]
    found = shutil.which("redeploy")
    if found:
        return found
    # fallback: python -m redeploy.cli not needed — just raise
    raise RuntimeError("Cannot locate redeploy binary")


def _run(*args: str, cwd: str | None = None, timeout: int = 120) -> dict:
    """Run a redeploy sub-command, capture stdout+stderr, return result dict."""
    cmd = [_redeploy_bin(), *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd or Path.cwd(),
            timeout=timeout,
        )
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "success": proc.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "stdout": "", "stderr": "Timeout", "success": False}
    except Exception as exc:
        return {"returncode": -1, "stdout": "", "stderr": str(exc), "success": False}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def schema(
    directory: Annotated[str, "Workspace root directory. '.' = current working directory."] = ".",
) -> dict:
    """Discover the workspace: find migration specs, read version, git branch.

    Always call this first to know which specs are available before planning or deploying.
    Returns a JSON dict with: cwd, version, git_branch, specs[], commands{}.
    """
    from redeploy.schema import build_schema
    root = Path(directory).expanduser().resolve()
    return build_schema(root)


@mcp.tool()
def plan_spec(
    spec: Annotated[str, "Path to migration.md / migration.yaml (absolute or relative to cwd)."],
    cwd: Annotated[str, "Working directory to resolve relative paths. Default: current dir."] = ".",
) -> dict:
    """Preview a migration spec: show all steps without executing anything.

    Safe read-only operation. Use this before run_spec or fix_spec to understand
    what will happen.
    """
    result = _run("run", spec, "--dry-run", "--no-heal", cwd=cwd, timeout=30)
    return result


@mcp.tool()
def run_spec(
    spec: Annotated[str, "Path to migration.md / migration.yaml."],
    force: Annotated[bool, "Skip interactive confirmation prompt."] = True,
    dry_run: Annotated[bool, "If True, only show plan without applying."] = False,
    heal: Annotated[bool, "Enable LLM self-healing on step failure."] = True,
    fix_hint: Annotated[str, "Optional problem description to guide LLM healing."] = "",
    cwd: Annotated[str, "Working directory."] = ".",
) -> dict:
    """Apply a migration spec.

    By default runs with --force (no prompt) and --heal enabled.
    Set dry_run=True for a safe preview first.
    """
    args = ["run", spec]
    if force:
        args.append("--force")
    if dry_run:
        args.append("--dry-run")
    if not heal:
        args.append("--no-heal")
    if fix_hint:
        args += ["--fix", fix_hint]
    return _run(*args, cwd=cwd, timeout=600)


@mcp.tool()
def fix_spec(
    spec_or_dir: Annotated[str, "Path to spec file or project directory (e.g. '.' or 'redeploy/pi109/migration.md')."],
    hint: Annotated[str, "Describe the problem to fix, e.g. 'service not starting', 'brak ikon SVG'."] = "",
    bump: Annotated[bool, "Bump version before deploying."] = True,
    retries: Annotated[int, "Max LLM self-healing retries."] = 3,
    dry_run: Annotated[bool, "Plan only, do not apply."] = False,
    cwd: Annotated[str, "Working directory."] = ".",
) -> dict:
    """Self-healing deploy: bump version → apply spec → LLM retry on failure.

    This is the main 'smart deploy' command. It bumps the version, applies the
    migration, and if a step fails, asks an LLM to suggest a fix and retries.
    """
    args = ["fix", spec_or_dir]
    if hint:
        args += ["--hint", hint]
    if not bump:
        args.append("--no-bump")
    args += ["--retries", str(retries)]
    if dry_run:
        args.append("--dry-run")
    return _run(*args, cwd=cwd, timeout=900)


@mcp.tool()
def bump_version(
    spec_or_dir: Annotated[str, "Path to spec or project directory."] = ".",
    level: Annotated[str, "Version component to bump: 'patch' (default), 'minor', 'major'."] = "patch",
    cwd: Annotated[str, "Working directory."] = ".",
) -> dict:
    """Bump the project version and update migration spec header.

    Updates VERSION file and all version references in the migration spec
    (version: field, name: and description: fields containing vX.Y.Z).
    """
    args = ["bump", spec_or_dir]
    if level == "minor":
        args.append("--minor")
    elif level == "major":
        args.append("--major")
    return _run(*args, cwd=cwd, timeout=10)


@mcp.tool()
def diagnose(
    host: Annotated[str, "SSH target, e.g. 'pi@192.168.188.109'."],
) -> dict:
    """Run SSH diagnostics on a deployment target and return system state.

    Checks: running containers, open ports, systemd unit status, recent logs.
    """
    return _run("diagnose", host, timeout=60)


@mcp.tool()
def list_specs(
    directory: Annotated[str, "Root directory to search for migration specs."] = ".",
) -> list[dict]:
    """List all migration specs found in a directory.

    Returns a list of {path, name, version, target, description} dicts.
    Use this for a quick overview without the full command catalogue.
    """
    from redeploy.schema import build_schema
    root = Path(directory).expanduser().resolve()
    s = build_schema(root)
    return s.get("specs", [])


@mcp.tool()
def exec_ssh(
    host: Annotated[str, "SSH target, e.g. 'pi@192.168.188.109'."],
    command: Annotated[str, "Shell command to run on the remote host."],
) -> dict:
    """Run an ad-hoc SSH command on a remote host.

    Returns stdout, stderr and return code.
    CAUTION: this executes arbitrary commands — confirm with user before use.
    """
    try:
        proc = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", host, command],
            capture_output=True, text=True, timeout=60,
        )
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "success": proc.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "stdout": "", "stderr": "SSH timeout", "success": False}
    except Exception as exc:
        return {"returncode": -1, "stdout": "", "stderr": str(exc), "success": False}


@mcp.tool()
def nlp_command(
    instruction: Annotated[str, "Natural language instruction, e.g. 'deploy c2004 to pi109' or 'pokaż plan deployu'."],
    dry_run: Annotated[bool, "Force dry-run on the generated command."] = False,
    cwd: Annotated[str, "Working directory for spec discovery."] = ".",
) -> dict:
    """Translate a natural-language instruction into a redeploy command and run it.

    Uses an LLM (via redeploy prompt) to map the instruction to a CLI command.
    Set dry_run=True to generate the command without executing it.

    Returns: {command: str, stdout: str, stderr: str, returncode: int}
    """
    args = ["prompt", instruction]
    if dry_run:
        args += ["--dry-run"]
    args += ["--yes"]  # non-interactive when called from MCP
    result = _run(*args, cwd=cwd, timeout=120)
    return result


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@mcp.resource("redeploy://spec/{path}")
def get_spec_content(path: str) -> str:
    """Read the raw content of a migration spec file.

    URI example: redeploy://spec/redeploy/pi109/migration.md
    """
    p = Path(path)
    if not p.exists():
        # try relative to cwd
        p = Path.cwd() / path
    if not p.exists():
        return f"# Error\nSpec not found: {path}"
    return p.read_text()


@mcp.resource("redeploy://workspace")
def get_workspace() -> str:
    """Return the workspace schema as JSON string."""
    import json
    from redeploy.schema import build_schema
    return json.dumps(build_schema(), indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def serve(transport: str = "stdio", host: str = "0.0.0.0", port: int = 8811) -> None:
    """Start the MCP server.

    Parameters
    ----------
    transport : 'stdio' | 'sse' | 'streamable-http'
    host      : bind host for SSE/HTTP transports
    port      : bind port for SSE/HTTP transports
    """
    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport == "sse":
        import uvicorn
        app = mcp.sse_app()
        uvicorn.run(app, host=host, port=port)
    elif transport in ("http", "streamable-http"):
        import uvicorn
        app = mcp.streamable_http_app()
        uvicorn.run(app, host=host, port=port)
    else:
        raise ValueError(f"Unknown transport: {transport!r}. Choose: stdio | sse | http")


if __name__ == "__main__":
    serve()

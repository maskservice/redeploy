"""redeploy.schema -- Workspace discovery schema for NLP command routing.

Builds a JSON-serialisable description of the current workspace so that an
LLM can map a natural-language user prompt to a concrete redeploy invocation.

Usage::

    from redeploy.schema import build_schema
    schema = build_schema()          # dict
    import json; print(json.dumps(schema, indent=2))
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Command catalogue — keeps CLI descriptions in one place so the LLM has
# enough context to pick the right command without reading Python source.
# ---------------------------------------------------------------------------

COMMAND_CATALOGUE: dict[str, dict[str, Any]] = {
    "fix": {
        "description": "Self-healing deploy: bump version, apply spec, retry with LLM on failure.",
        "primary_arg": "spec_or_dir (PATH to migration spec or directory)",
        "key_options": [
            "--hint/-m TEXT  -- describe the problem for LLM",
            "--no-bump       -- skip version bump",
            "--retries N     -- max LLM retry attempts (default 3)",
            "--dry-run       -- plan only, do not apply",
        ],
        "example": 'redeploy fix redeploy/pi109/migration.md --hint "service not starting"',
    },
    "run": {
        "description": "Apply a migration spec (with optional LLM heal on failure). Use --dry-run to preview without applying.",
        "primary_arg": "SPEC (path to migration.md or migration.yaml)",
        "key_options": [
            "--heal/--no-heal  -- enable LLM self-healing (default on)",
            "--fix TEXT        -- problem description for LLM",
            "--dry-run         -- plan only, show steps without executing",
            "--force           -- skip confirmation",
        ],
        "example": "redeploy run redeploy/pi109/migration.md --dry-run",
    },
    "plan": {
        "description": "Generate migration-plan.yaml from infra.yaml + target config. NOT for running existing specs — use 'run --dry-run' for that.",
        "primary_arg": "--infra PATH --target PATH",
        "key_options": ["--infra PATH", "--target PATH", "--strategy STR"],
        "example": "redeploy plan --infra infra.yaml --target target.yaml",
    },
    "bump": {
        "description": "Bump the project version (patch/minor/major) and update migration spec header.",
        "primary_arg": "PATH (spec or directory, default='.')",
        "key_options": ["--minor", "--major"],
        "example": "redeploy bump . --minor",
    },
    "detect": {
        "description": "Discover and register deployment targets/devices on the network.",
        "primary_arg": "none",
        "key_options": ["--host HOST"],
        "example": "redeploy detect",
    },
    "status": {
        "description": "Show current status of a deployment target or running containers.",
        "primary_arg": "none (reads redeploy.yaml or device registry)",
        "key_options": [],
        "example": "redeploy status",
    },
    "diagnose": {
        "description": "Run diagnostics (SSH probes) against a deployment target.",
        "primary_arg": "HOST or device-id",
        "key_options": [],
        "example": "redeploy diagnose pi@192.168.188.109",
    },
    "blueprint": {
        "description": "Generate a migration spec from a template/blueprint.",
        "primary_arg": "BLUEPRINT_NAME",
        "key_options": [],
        "example": "redeploy blueprint pi-podman",
    },
    "init": {
        "description": "Initialise a new redeploy project in the current directory.",
        "primary_arg": "none",
        "key_options": [],
        "example": "redeploy init",
    },
    "diff": {
        "description": "Show diff of spec changes since last run.",
        "primary_arg": "SPEC",
        "key_options": [],
        "example": "redeploy diff migration.yaml",
    },
    "audit": {
        "description": "Show the audit/history log for a spec.",
        "primary_arg": "SPEC",
        "key_options": [],
        "example": "redeploy audit migration.yaml",
    },
    "push": {
        "description": "Push / sync local files to a remote deployment target.",
        "primary_arg": "SPEC or device-id",
        "key_options": [],
        "example": "redeploy push redeploy/pi109/migration.md",
    },
    "inspect": {
        "description": "Inspect a spec file, validating structure and listing steps.",
        "primary_arg": "SPEC",
        "key_options": [],
        "example": "redeploy inspect migration.yaml",
    },
}


# ---------------------------------------------------------------------------
# Spec discovery helpers
# ---------------------------------------------------------------------------

def _parse_spec_meta(path: Path) -> dict[str, str]:
    """Extract version, name, target from a migration spec (YAML or Markdown)."""
    meta: dict[str, str] = {}
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return meta

    for key in ("version", "name", "target", "description"):
        m = re.search(rf"^{key}:\s*(.+)", text, re.MULTILINE | re.IGNORECASE)
        if m:
            meta[key] = m.group(1).strip().strip('"').strip("'")

    return meta


def _discover_specs(root: Path, max_specs: int = 20) -> list[dict[str, str]]:
    """Find migration specs starting from *root*.

    Priority order:
    1. root/migration.{md,yaml,yml}  (project root spec)
    2. root/redeploy/<target>/migration.*  (per-target specs)
    3. Any migration.* up to 3 levels deep (fallback)
    """
    found: list[Path] = []
    seen: set[Path] = set()

    def _add(p: Path) -> None:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            found.append(p)

    # 1. direct
    for name in ("migration.md", "migration.yaml", "migration.yml"):
        c = root / name
        if c.exists():
            _add(c)

    # 2. redeploy/<target>/migration.*
    redeploy_dir = root / "redeploy"
    if redeploy_dir.is_dir():
        for sub in sorted(redeploy_dir.iterdir()):
            if sub.is_dir():
                for name in ("migration.md", "migration.yaml", "migration.yml"):
                    c = sub / name
                    if c.exists():
                        _add(c)
                        break

    # 3. recursive fallback (up to max_specs total)
    if len(found) < 3:
        for pattern in ("migration.md", "migration.yaml", "migration.yml"):
            for p in sorted(root.rglob(pattern), key=lambda x: len(x.parts)):
                if len(found) >= max_specs:
                    break
                _add(p)

    specs = []
    for p in found[:max_specs]:
        try:
            rel = str(p.relative_to(root))
        except ValueError:
            rel = str(p)
        entry: dict[str, str] = {"path": rel, "abs": str(p.resolve())}
        entry.update(_parse_spec_meta(p))
        specs.append(entry)

    return specs


def _read_version(root: Path) -> str | None:
    """Walk up from *root* to find VERSION file."""
    cur = root
    for _ in range(4):
        v = cur / "VERSION"
        if v.exists():
            return v.read_text().strip()
        cur = cur.parent
    return None


def _git_branch(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=root, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_schema(root: Path | None = None) -> dict[str, Any]:
    """Build the workspace schema dict.

    Returns
    -------
    dict with keys:
      cwd        -- absolute working directory
      version    -- project version from VERSION file (or None)
      git_branch -- current git branch (or None)
      specs      -- list of discovered migration specs
      commands   -- command catalogue (descriptions + examples)
    """
    if root is None:
        root = Path.cwd()
    root = root.resolve()

    return {
        "cwd": str(root),
        "version": _read_version(root),
        "git_branch": _git_branch(root),
        "specs": _discover_specs(root),
        "commands": COMMAND_CATALOGUE,
    }

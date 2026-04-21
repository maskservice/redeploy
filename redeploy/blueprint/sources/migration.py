"""Parse migration.yaml metadata (version, strategy hints)."""
from __future__ import annotations

from pathlib import Path

import yaml


def parse_migration_meta(path: Path) -> dict:
    """Read *path* and return ``{"version": "…", "strategy": "…"}`` if found."""
    try:
        raw = yaml.safe_load(path.read_text())
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}

    result = {}
    if "version" in raw:
        result["version"] = str(raw["version"])
    if "strategy" in raw:
        result["strategy"] = raw["strategy"]

    # Walk steps looking for deploy action to infer strategy
    for step in raw.get("steps", []):
        action = step.get("action", "")
        if "podman" in action or "quadlet" in action:
            result["strategy"] = "podman_quadlet"
            break
        if "docker" in action:
            result["strategy"] = "docker_compose"
            break

    return result

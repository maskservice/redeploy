"""Load a declarative config file (YAML or JSON)."""
from __future__ import annotations

import json
from pathlib import Path

import yaml


def load_config_file(path: str | Path) -> dict:
    """Read *path* and return a dict (YAML or JSON auto-detected)."""
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    try:
        return yaml.safe_load(raw) or {}
    except Exception:
        return json.loads(raw)

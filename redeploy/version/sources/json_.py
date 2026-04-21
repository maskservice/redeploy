"""Adapter for JSON files (package.json, etc.)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..manifest import SourceConfig
from .base import BaseAdapter


class JsonAdapter(BaseAdapter):
    """Read/write version from JSON files."""

    format_name = "json"

    def read(self, path: Path, config: SourceConfig) -> str:
        if not self._validate_path(path, config):
            return ""
        if not config.key:
            raise ValueError("JSON source requires 'key' (e.g., 'version')")

        data = json.loads(path.read_text(encoding="utf-8"))

        # Navigate dotted key path
        parts = config.key.split(".")
        current = data
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                raise KeyError(f"Key '{config.key}' not found in {path}")
            current = current[part]

        if not isinstance(current, str):
            raise TypeError(f"Version at '{config.key}' is not a string: {current}")

        # Apply value_pattern if specified (e.g., extract from image tag)
        if config.value_pattern:
            match = re.search(config.value_pattern, current)
            if not match:
                raise ValueError(f"value_pattern '{config.value_pattern}' didn't match '{current}'")
            return match.group(1)

        return current

    def stage(self, path: Path, config: SourceConfig, new_version: str) -> Path:
        """Stage JSON update preserving formatting."""
        if not config.key:
            raise ValueError("JSON source requires 'key'")

        original = path.read_text(encoding="utf-8") if path.exists() else "{}"

        # Parse to get structure
        data = json.loads(original)

        # Navigate and update
        parts = config.key.split(".")
        current = data
        for part in parts[:-1]:
            current = current[part]

        final_key = parts[-1]

        # Handle value_pattern/write_pattern for image tags
        if config.write_pattern:
            new_value = config.write_pattern.format(version=new_version)
            current[final_key] = new_value
        else:
            current[final_key] = new_version

        # Serialize back with formatting preservation attempt
        # Use original indentation detection
        indent = self._detect_indent(original)
        updated = json.dumps(data, indent=indent, ensure_ascii=False)

        # Add trailing newline if original had one
        if original.endswith("\n"):
            updated += "\n"

        temp = self._create_temp(path)
        temp.write_text(updated, encoding="utf-8")
        return temp

    def _detect_indent(self, content: str) -> int:
        """Detect indentation from content."""
        lines = content.split("\n")
        for line in lines:
            stripped = line.lstrip()
            if stripped and line != stripped:
                return len(line) - len(stripped)
        return 2  # Default

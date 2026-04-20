"""Adapter for TOML files (pyproject.toml, etc.)."""
from __future__ import annotations

import re
from pathlib import Path

from ..manifest import SourceConfig
from .base import BaseAdapter


class TomlAdapter(BaseAdapter):
    """Read/write version from TOML files using tomllib/tomli."""

    format_name = "toml"

    def _get_toml_lib(self):
        """Import toml lib (tomllib for py3.11+, tomli for older)."""
        try:
            import tomllib
            return tomllib, "r"
        except ImportError:
            try:
                import tomli
                return tomli, "rb"
            except ImportError:
                raise ImportError("Neither tomllib nor tomli available. Install tomli for Python <3.11")

    def read(self, path: Path, config: SourceConfig) -> str:
        if not self._validate_path(path, config):
            return ""
        if not config.key:
            raise ValueError("TOML source requires 'key' (e.g., 'project.version')")

        toml, mode = self._get_toml_lib()
        with open(path, mode) as f:
            data = toml.load(f)

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
            import re
            match = re.search(config.value_pattern, current)
            if not match:
                raise ValueError(f"value_pattern '{config.value_pattern}' didn't match '{current}'")
            return match.group(1)

        return current

    def write(self, path: Path, config: SourceConfig, new_version: str) -> None:
        temp = self.stage(path, config, new_version)
        temp.rename(path)

    def stage(self, path: Path, config: SourceConfig, new_version: str) -> Path:
        """Stage TOML update (preserves formatting with simple regex replace)."""
        if not config.key:
            raise ValueError("TOML source requires 'key'")

        # Read original
        original = path.read_text(encoding="utf-8") if path.exists() else ""

        # Build pattern for key = "value" or key = 'value'
        # Support dotted keys by matching last segment
        key_parts = config.key.split(".")
        final_key = key_parts[-1]

        # Pattern: final_key = "version" (with optional spaces)
        pattern = rf'(^\s*{re.escape(final_key)}\s*=\s*")[^"]+(")'

        replacement = rf'\g<1>{new_version}\g<2>'

        updated, count = re.subn(pattern, replacement, original, count=1, flags=re.MULTILINE)

        if count == 0:
            # Try single quotes
            pattern = rf"(^\s*{re.escape(final_key)}\s*=\s*')[^']+(')"
            updated, count = re.subn(pattern, replacement, original, count=1, flags=re.MULTILINE)

        if count == 0:
            raise ValueError(f"Could not find key '{config.key}' in TOML to update")

        # Handle value_pattern/write_pattern for image tags
        if config.write_pattern:
            new_value = config.write_pattern.format(version=new_version)
            # Replace the full value, not just version
            pattern = rf'(^\s*{re.escape(final_key)}\s*=\s*")[^"]+(")'
            replacement = rf'\g<1>{new_value}\g<2>'
            updated, _ = re.subn(pattern, replacement, updated, count=1, flags=re.MULTILINE)

        # Write to temp
        temp = self._create_temp(path)
        temp.write_text(updated, encoding="utf-8")
        return temp

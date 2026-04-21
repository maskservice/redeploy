"""Adapter for YAML files (Chart.yaml, docker-compose.yml, etc.)."""
from __future__ import annotations

import re
from pathlib import Path

from ..manifest import SourceConfig
from .base import BaseAdapter


class YamlAdapter(BaseAdapter):
    """Read/write version from YAML files."""

    format_name = "yaml"

    def _get_yaml_lib(self):
        """Import PyYAML."""
        try:
            import yaml
            return yaml
        except ImportError:
            raise ImportError("PyYAML required for YAML support. Install: pip install pyyaml")

    def read(self, path: Path, config: SourceConfig) -> str:
        if not self._validate_path(path, config):
            return ""
        if not config.key:
            raise ValueError("YAML source requires 'key' (e.g., 'version' or 'appVersion')")

        yaml = self._get_yaml_lib()
        data = yaml.safe_load(path.read_text(encoding="utf-8"))

        if data is None:
            data = {}

        # Navigate dotted key path
        parts = config.key.split(".")
        current = data
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                raise KeyError(f"Key '{config.key}' not found in {path}")
            current = current[part]

        if not isinstance(current, str):
            raise TypeError(f"Version at '{config.key}' is not a string: {current}")

        # Apply value_pattern if specified (e.g., extract from image:tag)
        if config.value_pattern:
            match = re.search(config.value_pattern, current)
            if not match:
                raise ValueError(f"value_pattern '{config.value_pattern}' didn't match '{current}'")
            return match.group(1)

        return current

    def stage(self, path: Path, config: SourceConfig, new_version: str) -> Path:
        """Stage YAML update preserving formatting."""
        if not config.key:
            raise ValueError("YAML source requires 'key'")

        if not path.exists():
            if config.optional:
                # Skip optional files that don't exist
                raise ValueError(f"Optional file not found: {path} (skipped)")
            raise FileNotFoundError(f"Source file not found: {path}")

        original = path.read_text(encoding="utf-8")

        # For simple keys, use regex replacement to preserve formatting
        key_parts = config.key.split(".")
        final_key = key_parts[-1]

        # Pattern: key: value or key: "value" or key: 'value'
        # Support both quoted and unquoted values
        pattern = rf'(^\s*{re.escape(final_key)}\s*:\s*)"?[^"\n]+"?\s*$'

        def replacer(m):
            prefix = m.group(1)
            if config.write_pattern:
                new_value = config.write_pattern.format(version=new_version)
                # Quote if contains special chars
                if any(c in new_value for c in [':', '#', '{', '}']):
                    return f'{prefix}"{new_value}"'
                return f'{prefix}{new_value}'
            return f'{prefix}"{new_version}"'

        updated, count = re.subn(pattern, replacer, original, count=1, flags=re.MULTILINE)

        if count == 0:
            raise ValueError(f"Could not find key '{config.key}' in YAML to update")

        temp = self._create_temp(path)
        temp.write_text(updated, encoding="utf-8")
        return temp

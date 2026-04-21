"""Adapter for plain VERSION files (entire content is version)."""
from __future__ import annotations

from pathlib import Path

from ..manifest import SourceConfig
from .base import BaseAdapter


class PlainAdapter(BaseAdapter):
    """Read/write version from plain text file."""

    format_name = "plain"

    def read(self, path: Path, config: SourceConfig) -> str:
        if not self._validate_path(path, config):
            return ""  # Optional file not found
        return path.read_text(encoding="utf-8").strip()

    def stage(self, path: Path, config: SourceConfig, new_version: str) -> Path:
        """Create temp file with new version."""
        temp = self._create_temp(path)
        temp.write_text(new_version + "\n", encoding="utf-8")
        return temp

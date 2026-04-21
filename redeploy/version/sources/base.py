"""Base classes and utilities for source adapters."""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

from ..manifest import SourceConfig


class BaseAdapter:
    """Base class for source adapters with common utilities."""

    format_name: str

    def _validate_path(self, path: Path, config: SourceConfig) -> bool:
        """Check if path exists. Returns False only if optional=True."""
        if not path.exists():
            if config.optional:
                return False
            raise FileNotFoundError(f"Source file not found: {path}")
        return True

    def _extract_version(self, content: str, pattern: str) -> str:
        """Extract version using regex pattern (must have capture group)."""
        match = re.search(pattern, content)
        if not match:
            raise ValueError(f"Pattern '{pattern}' did not match content")
        if len(match.groups()) < 1:
            raise ValueError(f"Pattern '{pattern}' has no capture group")
        return match.group(1)

    def _create_temp(self, path: Path) -> Path:
        """Create temp file in same directory for atomic rename."""
        # Use same directory to ensure atomic rename works across filesystems
        dir_ = path.parent if path.parent.exists() else Path(tempfile.gettempdir())
        fd, temp_path = tempfile.mkstemp(dir=dir_, prefix=f".{path.name}.", suffix=".tmp")
        Path(temp_path).chmod(path.stat().st_mode if path.exists() else 0o644)
        return Path(temp_path)

    def _atomic_write(self, temp_path: Path, final_path: Path, content: str) -> None:
        """Write to temp then atomically rename."""
        temp_path.write_text(content, encoding="utf-8")
        temp_path.rename(final_path)  # Atomic on POSIX

    def write(self, path: Path, config: SourceConfig, new_version: str) -> None:
        """Stage and atomically write version to file."""
        temp = self.stage(path, config, new_version)
        temp.rename(path)

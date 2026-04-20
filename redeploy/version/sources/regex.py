"""Adapter for regex-based version extraction (Python, C, JS files, etc.)."""
from __future__ import annotations

import re
from pathlib import Path

from ..manifest import SourceConfig
from .base import BaseAdapter


class RegexAdapter(BaseAdapter):
    r"""Read/write version using regex pattern with capture group.

    Pattern must have exactly one capture group for the version.
    Example patterns:
      - __version__\s*=\s*"([^"]+)"           # Python
      - VERSION\s*=\s*['"]([^'"]+)['"]         # Generic
      - #define\s+FW_VERSION\s+"([^"]+)"       # C header
      - export\s+const\s+VERSION\s*=\s*"([^"]+)" # TypeScript
    """

    format_name = "regex"

    def read(self, path: Path, config: SourceConfig) -> str:
        if not self._validate_path(path, config):
            return ""
        if not config.pattern:
            raise ValueError("Regex source requires 'pattern' with capture group")

        content = path.read_text(encoding="utf-8")
        return self._extract_version(content, config.pattern)

    def write(self, path: Path, config: SourceConfig, new_version: str) -> None:
        temp = self.stage(path, config, new_version)
        temp.rename(path)

    def stage(self, path: Path, config: SourceConfig, new_version: str) -> Path:
        """Stage regex-based update."""
        if not config.pattern:
            raise ValueError("Regex source requires 'pattern'")

        original = path.read_text(encoding="utf-8") if path.exists() else ""

        # Validate pattern has capture group
        if "(" not in config.pattern:
            raise ValueError(f"Pattern must have capture group: {config.pattern}")

        # Build replacement: keep everything outside capture group, replace inside
        # Convert user pattern to replacement pattern
        # Pattern: prefix(group)suffix → replacement: prefix + new_version + suffix

        # Find the capture group position
        pattern = config.pattern

        # Simple approach: replace the matched version string
        def replacer(m):
            # m.group(0) is full match, we need to reconstruct with new version
            full = m.group(0)
            old_ver = m.group(1)
            return full.replace(old_ver, new_version)

        updated, count = re.subn(pattern, replacer, original, count=1, flags=re.MULTILINE)

        if count == 0:
            raise ValueError(f"Pattern '{config.pattern}' did not match content in {path}")

        temp = self._create_temp(path)
        temp.write_text(updated, encoding="utf-8")
        return temp

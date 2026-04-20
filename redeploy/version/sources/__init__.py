"""Source adapters for reading/writing version from different file formats."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from ..manifest import SourceConfig
from .plain import PlainAdapter
from .toml_ import TomlAdapter


@runtime_checkable
class SourceAdapter(Protocol):
    """Protocol for version source adapters."""

    format_name: str

    def read(self, path: Path, config: SourceConfig) -> str:
        """Read version from file."""
        ...

    def write(self, path: Path, config: SourceConfig, new_version: str) -> None:
        """Write version to file (atomic)."""
        ...

    def stage(self, path: Path, config: SourceConfig, new_version: str) -> Path:
        """Stage change to temp file, return temp path."""
        ...


# Registry of adapters
_ADAPTERS: dict[str, SourceAdapter] = {
    "plain": PlainAdapter(),
    "toml": TomlAdapter(),
}


def get_adapter(format_name: str) -> SourceAdapter:
    """Get adapter by format name."""
    if format_name not in _ADAPTERS:
        raise ValueError(f"Unknown source format: {format_name}")
    return _ADAPTERS[format_name]


def register_adapter(format_name: str, adapter: SourceAdapter) -> None:
    """Register custom adapter."""
    _ADAPTERS[format_name] = adapter


__all__ = ["SourceAdapter", "get_adapter", "register_adapter", "PlainAdapter", "TomlAdapter"]

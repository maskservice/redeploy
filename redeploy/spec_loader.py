"""Load deployment specs from supported file formats."""
from __future__ import annotations

from pathlib import Path

from .models import MigrationSpec


class SpecLoaderError(ValueError):
    """Base error raised when a deployment spec cannot be loaded."""


class UnsupportedSpecFormatError(SpecLoaderError):
    """Raised when the spec file uses an unsupported format."""


def load_migration_spec(path: str | Path) -> MigrationSpec:
    """Load a deployment spec from disk.

    Supported today:
    - `.yaml`
    - `.yml`

    Reserved for future support:
    - `.md` markpact/markdown specs
    """
    spec_path = Path(path)
    suffix = spec_path.suffix.lower()

    if suffix in {"", ".yaml", ".yml"}:
        return MigrationSpec.from_file(spec_path)

    if suffix == ".md":
        raise UnsupportedSpecFormatError(
            "Unsupported spec format '.md': markdown/markpact specs are not implemented yet. "
            "Use YAML (.yaml or .yml)."
        )

    raise UnsupportedSpecFormatError(
        f"Unsupported spec format '{suffix}': use YAML (.yaml or .yml)."
    )

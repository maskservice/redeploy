"""Load deployment specs from supported file formats."""
from __future__ import annotations

from pathlib import Path

from .markpact import (
    MarkpactCompileError,
    MarkpactParseError,
    compile_markpact_document,
    parse_markpact_file,
)
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

    Supported markdown subset today:
    - `.md` with markpact:config and markpact:steps blocks only
    """
    spec_path = Path(path)
    suffix = spec_path.suffix.lower()

    if suffix in {"", ".yaml", ".yml"}:
        return MigrationSpec.from_file(spec_path)

    if suffix == ".md":
        try:
            return compile_markpact_document(parse_markpact_file(spec_path))
        except (MarkpactParseError, MarkpactCompileError) as exc:
            raise SpecLoaderError(str(exc)) from exc

    raise UnsupportedSpecFormatError(
        f"Unsupported spec format '{suffix}': use YAML (.yaml or .yml)."
    )

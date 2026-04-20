from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class MarkpactBlock:
    kind: str
    format: str | None
    content: str
    start_line: int
    end_line: int

    @property
    def label(self) -> str:
        fmt = self.format or "yaml"
        return f"markpact:{self.kind} {fmt}".strip()


@dataclass(frozen=True)
class MarkpactDocument:
    path: Path
    blocks: list[MarkpactBlock] = field(default_factory=list)

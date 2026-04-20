from __future__ import annotations

from pathlib import Path

from markdown_it import MarkdownIt

from .models import MarkpactBlock, MarkpactDocument


class MarkpactParseError(ValueError):
    """Raised when a markdown markpact document cannot be parsed."""


def parse_markpact_file(path: str | Path) -> MarkpactDocument:
    file_path = Path(path)
    return parse_markpact_text(file_path.read_text(encoding="utf-8"), path=file_path)


def parse_markpact_text(text: str, *, path: str | Path = "migration.md") -> MarkpactDocument:
    source_path = Path(path)
    parser = MarkdownIt("commonmark")
    tokens = parser.parse(text)
    blocks: list[MarkpactBlock] = []

    for token in tokens:
        if token.type != "fence":
            continue
        parsed = _parse_markpact_fence_info(token.info)
        if parsed is None:
            continue

        kind, format_name = parsed
        start_line = (token.map[0] + 1) if token.map else 1
        end_line = token.map[1] if token.map else start_line
        blocks.append(MarkpactBlock(
            kind=kind,
            format=format_name,
            content=token.content,
            start_line=start_line,
            end_line=end_line,
        ))

    if not blocks:
        raise MarkpactParseError(
            f"No markpact blocks found in {source_path}. Expected fenced blocks like ```markpact:config yaml."
        )

    return MarkpactDocument(path=source_path, blocks=blocks)


def _parse_markpact_fence_info(info: str) -> tuple[str, str | None] | None:
    tokens = [part for part in info.strip().split() if part]
    if not tokens:
        return None

    kind: str | None = None
    format_name: str | None = None

    for token in tokens:
        if token.startswith("markpact:"):
            kind = token.split(":", 1)[1].strip().lower()
            continue
        if format_name is None and "=" not in token:
            format_name = token.lower()

    if not kind:
        return None

    if format_name is None and kind in {"config", "steps", "rollback"}:
        format_name = "yaml"

    return kind, format_name

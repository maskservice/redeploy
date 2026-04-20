"""Global parser registry — pre-populated with built-in parsers.

Import this module to get a ready-to-use ``ParserRegistry`` with all
built-in parsers already registered.

Usage::

    from redeploy.iac.registry import parser_registry, parse_file, parse_dir
    spec = parse_file(Path("docker-compose.yml"))
"""
from __future__ import annotations

from pathlib import Path

from .base import ParsedSpec, ParserRegistry
from .docker_compose import DockerComposeParser


# ── Global registry (singleton) ───────────────────────────────────────────────

parser_registry = ParserRegistry()
parser_registry.register(DockerComposeParser())


# ── Convenience helpers ───────────────────────────────────────────────────────


def parse_file(path: "Path | str") -> ParsedSpec:
    """Parse a single file with auto-detected format."""
    return parser_registry.parse(Path(path))


def parse_dir(root: "Path | str", recursive: bool = True,
              skip_errors: bool = True) -> list[ParsedSpec]:
    """Parse all recognised files under *root*."""
    return parser_registry.parse_dir(Path(root), recursive=recursive,
                                     skip_errors=skip_errors)

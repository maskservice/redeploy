"""Global parser registry — pre-populated with built-in parsers.

Import this module to get a ready-to-use ``ParserRegistry`` with all
built-in parsers already registered.

Usage::

    from redeploy.iac.registry import parser_registry, parse_file, parse_dir
    spec = parse_file(Path("docker-compose.yml"))
"""
from __future__ import annotations

import importlib.util
from importlib.metadata import entry_points
from pathlib import Path

from .base import ParsedSpec, ParserRegistry
from .config_hints import ConfigHintsParser
from .docker_compose import DockerComposeParser


# ── Global registry (singleton) ───────────────────────────────────────────────

parser_registry = ParserRegistry()
parser_registry.register(DockerComposeParser())
parser_registry.register(ConfigHintsParser())


def _load_entrypoint_parsers(registry: ParserRegistry) -> int:
    """Load parser plugins from Python entry points group: redeploy.iac.parsers."""
    loaded = 0
    try:
        eps = entry_points(group="redeploy.iac.parsers")
    except TypeError:
        eps = entry_points().get("redeploy.iac.parsers", [])

    for ep in eps:
        try:
            parser_obj = ep.load()
            parser = parser_obj() if isinstance(parser_obj, type) else parser_obj
            if hasattr(parser, "can_parse") and hasattr(parser, "parse"):
                registry.register(parser)
                loaded += 1
        except Exception:
            # Keep registry robust; plugin failures should not break core parser flow.
            continue
    return loaded


def _load_local_parsers(registry: ParserRegistry) -> int:
    """Load local parser plugins from project and user directories.

    Supported plugin module contract:
    - `PARSERS = [ParserInstanceOrClass, ...]`
    - or `get_parsers() -> list[ParserInstanceOrClass]`
    """
    loaded = 0
    plugin_dirs = [
        Path.cwd() / "redeploy_iac_parsers",
        Path.home() / ".redeploy" / "iac_parsers",
    ]
    for d in plugin_dirs:
        if not d.is_dir():
            continue
        for py_file in sorted(d.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(f"redeploy_iac_{py_file.stem}", py_file)
                if not spec or not spec.loader:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)  # type: ignore[union-attr]

                parser_defs = []
                if hasattr(module, "get_parsers"):
                    parser_defs = list(module.get_parsers())
                elif hasattr(module, "PARSERS"):
                    parser_defs = list(module.PARSERS)

                for parser_obj in parser_defs:
                    parser = parser_obj() if isinstance(parser_obj, type) else parser_obj
                    if hasattr(parser, "can_parse") and hasattr(parser, "parse"):
                        registry.register(parser)
                        loaded += 1
            except Exception:
                continue
    return loaded


_load_entrypoint_parsers(parser_registry)
_load_local_parsers(parser_registry)


# ── Convenience helpers ───────────────────────────────────────────────────────


def parse_file(path: "Path | str") -> ParsedSpec:
    """Parse a single file with auto-detected format."""
    return parser_registry.parse(Path(path))


def parse_dir(root: "Path | str", recursive: bool = True,
              skip_errors: bool = True) -> list[ParsedSpec]:
    """Parse all recognised files under *root*."""
    return parser_registry.parse_dir(Path(root), recursive=recursive,
                                     skip_errors=skip_errors)

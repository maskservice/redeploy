"""redeploy.iac — pluggable IaC/CI-CD parsers (Faza 0, Tier 1–2).

Public API::

    from redeploy.iac import parse_file, parse_dir, parser_registry
    from redeploy.iac import ParsedSpec, ParserRegistry

Each registered parser handles one external format (docker-compose, GitHub
Actions, Kubernetes, …) and returns a ``ParsedSpec`` — a common intermediate
representation that the ``Converter`` can translate into a ``MigrationSpec``.

Zero new runtime dependencies for Tier 1 + Tier 2 parsers (PyYAML already
required by the core package).

Usage example::

    from redeploy.iac import parse_file
    spec = parse_file(Path("docker-compose.yml"))
    print(spec.services)

    # Or let the registry auto-detect format:
    from redeploy.iac import parse_dir
    specs = parse_dir(Path("."))
"""
from .base import (  # noqa: F401
    ParsedSpec,
    Parser,
    ParserRegistry,
    PortInfo,
    ServiceInfo,
    VolumeInfo,
    ConversionWarning,
)
from .registry import parser_registry, parse_file, parse_dir  # noqa: F401

__all__ = [
    "ParsedSpec",
    "Parser",
    "ParserRegistry",
    "PortInfo",
    "ServiceInfo",
    "VolumeInfo",
    "ConversionWarning",
    "parser_registry",
    "parse_file",
    "parse_dir",
]

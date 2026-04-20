"""redeploy.iac.base — Parser protocol and shared data models.

``Parser``
    Protocol each format-specific parser must implement.

``ParsedSpec``
    Common intermediate representation produced by any parser.
    Free of format-specific details so the Converter can handle all.

``ParserRegistry``
    Dispatch file/directory → matching parser.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable


# ── Supporting models ─────────────────────────────────────────────────────────


@dataclass
class PortInfo:
    """A published / exposed port mapping."""
    container: int
    host: Optional[int] = None          # None = not published externally
    protocol: str = "tcp"               # "tcp" | "udp"
    host_ip: str = "0.0.0.0"

    def __str__(self) -> str:
        if self.host:
            return f"{self.host_ip}:{self.host}->{self.container}/{self.protocol}"
        return f"{self.container}/{self.protocol}"


@dataclass
class VolumeInfo:
    """A volume or bind-mount."""
    target: str                          # container path
    source: Optional[str] = None         # host path or named volume
    source_type: str = "volume"          # "bind" | "volume" | "tmpfs"
    read_only: bool = False


@dataclass
class ServiceInfo:
    """One logical service / container / pod / deployment."""
    name: str
    image: Optional[str] = None
    ports: list[PortInfo] = field(default_factory=list)
    volumes: list[VolumeInfo] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    env_files: list[str] = field(default_factory=list)
    networks: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    healthcheck: Optional[str] = None
    restart: Optional[str] = None
    command: Optional[str] = None
    build_context: Optional[str] = None # None = not built locally
    replicas: int = 1
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class ConversionWarning:
    """A warning emitted by a parser or converter about lossy / uncertain data."""
    severity: str       # "info" | "warn" | "error"
    message: str
    source_path: Optional[str] = None
    line: Optional[int] = None

    def __str__(self) -> str:
        loc = f" ({self.source_path}:{self.line})" if self.source_path else ""
        return f"[{self.severity.upper()}]{loc} {self.message}"


# ── ParsedSpec ────────────────────────────────────────────────────────────────


@dataclass
class ParsedSpec:
    """Common intermediate representation from any IaC/CI-CD parser.

    Fields are intentionally broad — not every parser will fill all of them.
    Consumers should check for empty lists / None rather than assuming presence.
    """

    # Source metadata
    source_file: Path
    source_format: str              # "docker-compose" | "github_actions" | …

    # Services / workloads
    services: list[ServiceInfo] = field(default_factory=list)

    # Top-level port/volume/network info (may duplicate per-service)
    ports: list[PortInfo] = field(default_factory=list)
    volumes: list[VolumeInfo] = field(default_factory=list)
    networks: list[str] = field(default_factory=list)

    # Image references (flat list from all services + build steps)
    images: list[str] = field(default_factory=list)

    # Secrets referenced — *names only*, never values
    secrets_referenced: list[str] = field(default_factory=list)

    # Environment variable hints at the global level
    env_vars: dict[str, str] = field(default_factory=dict)
    env_files: list[str] = field(default_factory=list)

    # CI/CD specific
    target_hosts: list[str] = field(default_factory=list)  # SSH targets
    triggers: list[str] = field(default_factory=list)      # push, tag, cron…
    deploy_commands: list[str] = field(default_factory=list)

    # Detected runtime hints (free-form strings)
    runtime_hints: list[str] = field(default_factory=list)

    # Quality indicators
    warnings: list[ConversionWarning] = field(default_factory=list)
    unparseable_blocks: list[str] = field(default_factory=list)
    confidence: float = 1.0          # 0.0–1.0 heuristic quality

    def add_warning(self, msg: str, severity: str = "warn",
                    source_path: Optional[str] = None,
                    line: Optional[int] = None) -> None:
        self.warnings.append(ConversionWarning(severity, msg, source_path, line))

    def all_images(self) -> list[str]:
        """Deduplicated image list from spec-level + per-service."""
        seen: set[str] = set()
        result: list[str] = []
        for img in self.images:
            if img and img not in seen:
                seen.add(img)
                result.append(img)
        for svc in self.services:
            if svc.image and svc.image not in seen:
                seen.add(svc.image)
                result.append(svc.image)
        return result

    def all_ports(self) -> list[PortInfo]:
        """Deduplicated port list from spec-level + per-service."""
        seen: set[str] = set()
        result: list[PortInfo] = []
        for p in self.ports:
            key = str(p)
            if key not in seen:
                seen.add(key)
                result.append(p)
        for svc in self.services:
            for p in svc.ports:
                key = str(p)
                if key not in seen:
                    seen.add(key)
                    result.append(p)
        return result

    def summary(self) -> str:
        n_svc = len(self.services)
        n_ports = len(self.all_ports())
        n_imgs = len(self.all_images())
        n_warn = len(self.warnings)
        return (
            f"{self.source_format} {self.source_file.name}: "
            f"{n_svc} service(s), {n_ports} port(s), {n_imgs} image(s)"
            + (f", {n_warn} warning(s)" if n_warn else "")
            + f" [confidence={self.confidence:.0%}]"
        )


# ── Parser protocol ───────────────────────────────────────────────────────────


@runtime_checkable
class Parser(Protocol):
    """Protocol every format-specific parser must satisfy."""

    #: Short machine-readable name — matches directory key in ParserRegistry
    name: str
    #: Human-readable label shown in --help and reports
    format_label: str
    #: File extensions this parser can handle (lower-case with dot)
    extensions: list[str]
    #: Glob-style path patterns — more specific than extensions alone
    path_patterns: list[str]

    def can_parse(self, path: Path) -> bool:
        """Return True if this parser can handle *path* (fast check only)."""
        ...

    def parse(self, path: Path) -> ParsedSpec:
        """Parse *path* and return a ``ParsedSpec``.

        Must not raise for recoverable errors — use ``spec.add_warning()``
        and lower ``spec.confidence`` instead.  Raise ``ValueError`` only
        for truly unrecoverable input.
        """
        ...


# ── ParserRegistry ────────────────────────────────────────────────────────────


class ParserRegistry:
    """Dispatch file → registered parser.

    Parsers are tried in registration order.  The first one whose
    ``can_parse()`` returns True wins.
    """

    def __init__(self) -> None:
        self._parsers: list[Parser] = []

    def register(self, parser: Parser) -> None:
        """Register a parser instance."""
        self._parsers.append(parser)

    def parser_for(self, path: Path) -> Optional[Parser]:
        """Return the first parser that claims to handle *path*, or None."""
        for p in self._parsers:
            if p.can_parse(path):
                return p
        return None

    def parse(self, path: Path) -> ParsedSpec:
        """Parse *path* with auto-detected parser.

        Raises ``ValueError`` if no registered parser can handle the file.
        """
        parser = self.parser_for(path)
        if not parser:
            raise ValueError(
                f"No parser registered for {path.name!r}. "
                f"Known parsers: {[p.name for p in self._parsers]}"
            )
        return parser.parse(path)

    def parse_dir(self, root: Path,
                  recursive: bool = True,
                  skip_errors: bool = True) -> list[ParsedSpec]:
        """Parse all recognised files under *root*.

        Files that match no parser are silently skipped.
        Parse errors are swallowed and recorded as warnings when
        ``skip_errors=True`` (default).
        """
        results: list[ParsedSpec] = []
        pattern = "**/*" if recursive else "*"
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            parser = self.parser_for(path)
            if not parser:
                continue
            try:
                results.append(parser.parse(path))
            except Exception as exc:
                if not skip_errors:
                    raise
                spec = ParsedSpec(
                    source_file=path,
                    source_format=parser.name,
                    confidence=0.0,
                )
                spec.add_warning(f"Parse error: {exc}", severity="error")
                results.append(spec)
        return results

    @property
    def registered(self) -> list[str]:
        """Names of all registered parsers."""
        return [p.name for p in self._parsers]

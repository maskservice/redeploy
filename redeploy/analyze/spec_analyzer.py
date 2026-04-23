"""Static analysis engine for migration specs.

Scans compiled MigrationSpec + raw markpact blocks for:
- missing local files/paths referenced in steps (src, dst, command, config_file)
- broken command_ref / insert_before references
- docker-compose.yml inconsistencies (missing files, volume paths, build contexts)
- hardcoded absolute paths to external dependencies in commands
- .env / config file references
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from ..markpact.models import MarkpactDocument
from ..models.plan import MigrationStep
from ..models.spec import MigrationSpec


class IssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Issue:
    severity: IssueSeverity
    category: str
    step_id: str | None
    message: str
    suggestion: str | None = None
    line: int | None = None


@dataclass
class AnalysisResult:
    issues: list[Issue] = field(default_factory=list)
    passed: bool = True

    def add(self, severity: IssueSeverity, category: str, message: str,
            step_id: str | None = None, suggestion: str | None = None, line: int | None = None) -> None:
        self.issues.append(Issue(severity, category, step_id, message, suggestion, line))
        if severity == IssueSeverity.ERROR:
            self.passed = False

    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == IssueSeverity.ERROR]

    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == IssueSeverity.WARNING]


class _Checker:
    def check(self, spec: MigrationSpec, document: MarkpactDocument | None,
              base_dir: Path, result: AnalysisResult) -> None:
        raise NotImplementedError


class _PathChecker(_Checker):
    """Validate local file paths referenced by steps."""

    def check(self, spec, document, base_dir, result):
        for step in spec.extra_steps:
            self._check_field(step, "src", base_dir, result)
            self._check_field(step, "dst", base_dir, result)
            self._check_field(step, "config_file", base_dir, result)
            self._check_env_file(step, base_dir, result)

    def _check_field(self, step: dict, field_name: str, base_dir: Path, result: AnalysisResult):
        val = step.get(field_name)
        if not val:
            return
        # Only check local (non-ssh) paths; remote paths often start with ~ or user@host:...
        if re.search(r"^[\w.-]+@", str(val)):
            return
        # dst pointing to remote home (~/) is not a local path to verify
        if field_name == "dst" and str(val).startswith("~/"):
            return
        path = self._resolve(val, base_dir)
        if path and not path.exists():
            result.add(
                IssueSeverity.ERROR, "paths",
                f"Step '{step.get('id')}' references missing {field_name}: {val}",
                step.get("id"),
                suggestion=f"Create file/dir or correct path: {path}"
            )

    def _check_env_file(self, step: dict, base_dir: Path, result: AnalysisResult):
        # Some steps may compose env_file indirectly; we also scan raw commands for .env
        pass

    @staticmethod
    def _resolve(val: str, base_dir: Path) -> Path | None:
        val = val.strip()
        if val.startswith("~/"):
            return Path.home() / val[2:]
        if val.startswith("/"):
            return Path(val)
        # relative -> resolve against base_dir
        return base_dir / val


class _CommandPathChecker(_Checker):
    """Scan command strings for hardcoded absolute paths outside the project."""

    EXTERNAL_RE = re.compile(
        r"(?:^|\s)(/home/\w+/[^\s'\"]+|~/[^\s'\"]+)"
    )

    def check(self, spec, document, base_dir, result):
        for step in spec.extra_steps:
            cmd = step.get("command") or ""
            for match in self.EXTERNAL_RE.finditer(cmd):
                path_str = match.group(1)
                # Ignore paths inside the project tree
                resolved = self._resolve(path_str, base_dir)
                if resolved and self._is_inside(resolved, base_dir):
                    continue
                # Check if exists locally
                if resolved and not resolved.exists():
                    result.add(
                        IssueSeverity.ERROR, "commands",
                        f"Step '{step.get('id')}' command references missing external path: {path_str}",
                        step.get("id"),
                        suggestion="Add rsync/scp step to sync this dependency, or correct the path."
                    )
                else:
                    result.add(
                        IssueSeverity.WARNING, "commands",
                        f"Step '{step.get('id')}' command references external path: {path_str}",
                        step.get("id"),
                        suggestion="Consider adding an explicit sync step for this dependency."
                    )

    @staticmethod
    def _resolve(val: str, base_dir: Path) -> Path | None:
        val = val.strip().rstrip("/")
        if val.startswith("~/"):
            return Path.home() / val[2:]
        if val.startswith("/"):
            return Path(val)
        return base_dir / val

    @staticmethod
    def _is_inside(path: Path, base: Path) -> bool:
        try:
            path.resolve().relative_to(base.resolve())
            return True
        except ValueError:
            return False


class _ReferenceChecker(_Checker):
    """Ensure command_ref and insert_before point to existing things."""

    def check(self, spec, document, base_dir, result):
        step_ids = {s.get("id") for s in spec.extra_steps if s.get("id")}
        ref_ids = set()
        if document:
            for block in document.blocks:
                if block.kind == "ref" and block.ref_id:
                    ref_ids.add(block.ref_id)

        for step in spec.extra_steps:
            sid = step.get("id")
            cref = step.get("command_ref")
            if cref and cref not in ref_ids:
                result.add(
                    IssueSeverity.ERROR, "references",
                    f"Step '{sid}' references unknown command_ref '{cref}'",
                    sid,
                    suggestion=f"Define a ```bash markpact:ref {cref} block or remove command_ref."
                )
            ib = step.get("insert_before")
            if ib and ib not in step_ids:
                result.add(
                    IssueSeverity.ERROR, "references",
                    f"Step '{sid}' insert_before points to unknown step '{ib}'",
                    sid,
                    suggestion=f"Available step ids: {', '.join(sorted(step_ids)) or 'none'}"
                )


class _ComposeChecker(_Checker):
    """Validate docker-compose files declared in spec or found in project."""

    def check(self, spec, document, base_dir, result):
        compose_files = list(spec.target.compose_files or [])
        # Also try to discover common names if none explicitly declared
        if not compose_files:
            for candidate in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
                if (base_dir / candidate).exists():
                    compose_files.append(candidate)
                    break

        for cf in compose_files:
            path = base_dir / cf
            if not path.exists():
                result.add(
                    IssueSeverity.ERROR, "compose",
                    f"Declared compose file not found: {cf}",
                    suggestion=f"Create {path} or remove from target.compose_files."
                )
                continue
            self._scan_compose(path, base_dir, result)

    def _scan_compose(self, path: Path, base_dir: Path, result: AnalysisResult):
        try:
            data = yaml.safe_load(path.read_text()) or {}
        except Exception as exc:
            result.add(IssueSeverity.ERROR, "compose", f"Cannot parse {path}: {exc}")
            return

        services = data.get("services", {})
        for svc_name, svc in services.items():
            if not isinstance(svc, dict):
                continue
            # build.context
            build = svc.get("build")
            if isinstance(build, dict):
                ctx = build.get("context", ".")
                ctx_path = base_dir / ctx if not ctx.startswith("/") else Path(ctx)
                if not ctx_path.exists():
                    result.add(
                        IssueSeverity.ERROR, "compose",
                        f"Service '{svc_name}' build.context missing: {ctx}",
                        suggestion=f"Create directory {ctx_path} or fix context."
                    )
                dockerfile = build.get("dockerfile")
                if dockerfile:
                    df_path = ctx_path / dockerfile
                    if not df_path.exists():
                        result.add(
                            IssueSeverity.ERROR, "compose",
                            f"Service '{svc_name}' Dockerfile missing: {df_path}",
                            suggestion=f"Create {df_path} or correct dockerfile path."
                        )
            # env_file
            env_files = svc.get("env_file", [])
            if isinstance(env_files, str):
                env_files = [env_files]
            for ef in env_files:
                ef_path = base_dir / ef if not str(ef).startswith("/") else Path(ef)
                if not ef_path.exists():
                    result.add(
                        IssueSeverity.WARNING, "compose",
                        f"Service '{svc_name}' env_file missing: {ef}",
                        suggestion=f"Create {ef_path} or remove env_file entry."
                    )
            # volumes
            for vol in svc.get("volumes", []):
                if isinstance(vol, str):
                    if ":" in vol:
                        host_part = vol.split(":", 1)[0]
                        # Skip named volumes and relative paths that exist
                        if host_part.startswith("/"):
                            if not Path(host_part).exists():
                                result.add(
                                    IssueSeverity.WARNING, "compose",
                                    f"Service '{svc_name}' volume host path missing: {host_part}",
                                    suggestion=f"Ensure host path exists before deployment."
                                )
                        elif host_part != "." and "/" in host_part:
                            hp = base_dir / host_part
                            if not hp.exists():
                                result.add(
                                    IssueSeverity.WARNING, "compose",
                                    f"Service '{svc_name}' relative volume path missing: {hp}",
                                    suggestion=f"Create {hp} or mount as named volume."
                                )


class _EnvFileChecker(_Checker):
    """Check that .env referenced by target.env_file exists."""

    def check(self, spec, document, base_dir, result):
        ef = spec.target.env_file or spec.source.env_file
        if ef:
            path = base_dir / ef if not ef.startswith("/") else Path(ef)
            if not path.exists():
                result.add(
                    IssueSeverity.ERROR, "env",
                    f"env_file not found: {ef}",
                    suggestion=f"Create {path} or correct env_file path."
                )


class _BinaryChecker(_Checker):
    """Warn if commands reference binaries not available locally (best-effort)."""

    def check(self, spec, document, base_dir, result):
        for step in spec.extra_steps:
            cmd = step.get("command") or ""
            for word in cmd.split():
                word = word.strip(";|&`'\"()")
                if "/" in word or word in ("if", "then", "else", "fi", "for", "do", "done", "echo", "true", "false"):
                    continue
                if not self._which(word):
                    # Only warn for likely commands (simple words, not variable names)
                    if re.match(r"^[a-zA-Z][a-zA-Z0-9_-]+$", word):
                        result.add(
                            IssueSeverity.WARNING, "binaries",
                            f"Step '{step.get('id')}' command uses binary not found locally: '{word}'",
                            step.get("id"),
                            suggestion=f"Install '{word}' or ensure it exists on target host."
                        )

    @staticmethod
    def _which(cmd: str) -> bool:
        try:
            subprocess.run(["which", cmd], capture_output=True, check=True)
            return True
        except Exception:
            return False


class SpecAnalyzer:
    """Run static checks against a compiled MigrationSpec (and optional raw MarkpactDocument)."""

    DEFAULT_CHECKERS: list[_Checker] = [
        _PathChecker(),
        _CommandPathChecker(),
        _ReferenceChecker(),
        _ComposeChecker(),
        _EnvFileChecker(),
        _BinaryChecker(),
    ]

    def __init__(self, base_dir: Path | None = None,
                 checkers: list[_Checker] | None = None):
        self.base_dir = base_dir or Path.cwd()
        self.checkers = checkers or list(self.DEFAULT_CHECKERS)

    def analyze(self, spec: MigrationSpec,
                document: MarkpactDocument | None = None) -> AnalysisResult:
        result = AnalysisResult()
        for checker in self.checkers:
            checker.check(spec, document, self.base_dir, result)
        return result

    def analyze_file(self, spec_path: Path) -> tuple[MigrationSpec | None, AnalysisResult]:
        """Load spec from file (YAML or markpact) and analyze."""
        from ..markpact.parser import parse_markpact_file
        from ..markpact.compiler import compile_markpact_document, MarkpactCompileError
        from ..models.spec import MigrationSpec as MS

        document = None
        spec = None
        result = AnalysisResult()

        # Try markpact first
        if spec_path.suffix == ".md":
            try:
                document = parse_markpact_file(spec_path)
                spec = compile_markpact_document(document)
            except MarkpactCompileError as exc:
                result.add(IssueSeverity.ERROR, "compile", str(exc))
                return None, result
            except Exception as exc:
                result.add(IssueSeverity.ERROR, "compile", f"Failed to parse markpact: {exc}")
                return None, result
        else:
            try:
                spec = MS.from_file(spec_path)
            except Exception as exc:
                result.add(IssueSeverity.ERROR, "load", f"Failed to load spec: {exc}")
                return None, result

        if spec:
            self.base_dir = spec_path.parent
            result = self.analyze(spec, document)
        return spec, result

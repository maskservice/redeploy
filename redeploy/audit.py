"""Audit a target host against a migration spec.

Given a `MigrationSpec` (loaded from YAML or markpact MD), derive the set of
expectations the spec implies for the target host (binaries, files, ports,
disk space, container images, systemd units, env files, …) and probe the
target via SSH to report what is **missing** or out of spec.

This is non-destructive: it never executes any spec command — only read-only
inspection commands.

Public entrypoints:
    - ``Auditor`` — the analyzer class
    - ``audit_spec(path, host=None)`` — convenience wrapper
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from loguru import logger

from .models import DeployStrategy, MigrationSpec, StepAction
from .spec_loader import load_migration_spec
from .ssh import SshClient


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class AuditCheck:
    """Outcome of a single audit probe."""
    category: str           # "binary" | "file" | "directory" | "port" | "image" | …
    name: str               # human-readable identifier (e.g. "podman", "/etc/foo")
    status: str             # "pass" | "fail" | "warn" | "skip"
    detail: str = ""        # short explanation / observed value
    fix_hint: str = ""      # how to remediate
    source_step: str = ""   # spec step id that introduced this expectation

    @property
    def ok(self) -> bool:
        return self.status == "pass"


@dataclass
class AuditReport:
    spec_path: str
    host: str
    target_strategy: str
    checks: list[AuditCheck] = field(default_factory=list)

    def add(self, check: AuditCheck) -> None:
        self.checks.append(check)

    @property
    def passed(self) -> list[AuditCheck]:
        return [c for c in self.checks if c.status == "pass"]

    @property
    def failed(self) -> list[AuditCheck]:
        return [c for c in self.checks if c.status == "fail"]

    @property
    def warned(self) -> list[AuditCheck]:
        return [c for c in self.checks if c.status == "warn"]

    @property
    def skipped(self) -> list[AuditCheck]:
        return [c for c in self.checks if c.status == "skip"]

    @property
    def ok(self) -> bool:
        return not self.failed

    def summary(self) -> str:
        return (
            f"Audit: {len(self.passed)}/{len(self.checks)} passed, "
            f"{len(self.failed)} missing, {len(self.warned)} warnings, "
            f"{len(self.skipped)} skipped"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": self.spec_path,
            "host": self.host,
            "target_strategy": self.target_strategy,
            "ok": self.ok,
            "summary": self.summary(),
            "checks": [c.__dict__ for c in self.checks],
        }


# ── Expectation extraction ────────────────────────────────────────────────────

@dataclass(frozen=True)
class _Expect:
    category: str
    name: str
    source_step: str = ""
    fix_hint: str = ""
    extra: tuple[tuple[str, str], ...] = ()

    @property
    def extras(self) -> dict[str, str]:
        return dict(self.extra)


# Required base binaries per target strategy.
_STRATEGY_BINARIES: dict[DeployStrategy, tuple[str, ...]] = {
    DeployStrategy.PODMAN_QUADLET: ("podman", "systemctl", "loginctl"),
    DeployStrategy.DOCKER_FULL:    ("docker",),
    DeployStrategy.K3S:            ("kubectl",),
    DeployStrategy.DOCKER_KIOSK:   ("docker",),
}

# Heuristic patterns for extracting expectations from raw shell commands
# embedded in extra_steps.  Conservative — false positives become "warn".
_RE_PODMAN_BUILD_TAG = re.compile(
    r"podman\s+build(?:\s+[-\w]+)*\s+-t\s+([\w\-./:]+)", re.IGNORECASE
)
_RE_DOCKER_BUILD_TAG = re.compile(
    r"docker\s+build(?:\s+[-\w]+)*\s+-t\s+([\w\-./:]+)", re.IGNORECASE
)
_RE_MKDIR = re.compile(r"\bmkdir\s+(?:-[pmv]+\s+)?([^\s&|;><]+)")
_RE_SYSTEMCTL_USER_UNIT = re.compile(r"systemctl\s+--user\s+\w+\s+([\w@\-.]+)")
_RE_PORT_URL = re.compile(r"https?://[^/\s:]+(?::(\d+))?")
_RE_APT_INSTALL = re.compile(
    r"apt(?:-get)?\s+install\s+(?:-[\w-]+\s+)*([\w\-+.\s]+?)(?:[;&|]|$)",
    re.IGNORECASE,
)
_RE_COMMAND_V = re.compile(r"command\s+-v\s+([\w\-]+)")


class _Extractor:
    """Walk a MigrationSpec and emit Expect tuples."""

    def __init__(self, spec: MigrationSpec):
        self.spec = spec
        self._seen: set[tuple[str, str]] = set()

    def collect(self) -> list[_Expect]:
        out: list[_Expect] = []
        out.extend(self._from_target())
        for raw in self.spec.extra_steps:
            out.extend(self._from_step(raw))
        # de-dup preserving order
        unique: list[_Expect] = []
        for exp in out:
            key = (exp.category, exp.name)
            if key in self._seen:
                continue
            self._seen.add(key)
            unique.append(exp)
        return unique

    # ── per-target expectations ─────────────────────────────────────────────
    def _from_target(self) -> Iterable[_Expect]:
        target = self.spec.target
        for binary in _STRATEGY_BINARIES.get(target.strategy, ()):
            yield _Expect(
                category="binary",
                name=binary,
                source_step="target.strategy",
                fix_hint=f"install {binary} on target host",
            )

        if target.remote_dir:
            yield _Expect(
                category="directory",
                name=_normalize_path(target.remote_dir),
                source_step="target.remote_dir",
                fix_hint=f"mkdir -p {target.remote_dir}",
            )

        if target.env_file:
            yield _Expect(
                category="local_file",
                name=target.env_file,
                source_step="target.env_file",
                fix_hint="provide env_file on the controller before running",
            )

        if target.verify_url:
            port = _extract_port(target.verify_url)
            if port:
                yield _Expect(
                    category="port_listening",
                    name=str(port),
                    source_step="target.verify_url",
                    fix_hint=f"start the service exposing port {port}",
                    extra=(("url", target.verify_url),),
                )

        for unit in target.stop_services + target.disable_services:
            yield _Expect(
                category="systemd_unit",
                name=unit,
                source_step="target.stop_services",
                fix_hint=f"unit {unit} should exist or step will be a no-op",
            )

    # ── per-step expectations (heuristic) ───────────────────────────────────
    def _from_step(self, raw: dict) -> Iterable[_Expect]:
        sid = str(raw.get("id", "<extra_step>"))
        action = str(raw.get("action", ""))

        # rsync / scp destinations
        if action in {"rsync", "scp"}:
            dst = raw.get("dst")
            if dst:
                yield _Expect(
                    category="directory",
                    name=_normalize_path(_strip_remote_dir(str(dst))),
                    source_step=sid,
                    fix_hint=f"mkdir -p {dst} on target",
                )
            src = raw.get("src")
            if src and action == "scp":
                yield _Expect(
                    category="local_file",
                    name=str(src),
                    source_step=sid,
                    fix_hint=f"controller-side file {src} must exist",
                )

        # systemctl steps
        if action.startswith("systemctl_"):
            svc = raw.get("service")
            if svc:
                yield _Expect(
                    category="systemd_unit",
                    name=str(svc),
                    source_step=sid,
                )

        # http_check / version_check URLs
        if action in {"http_check", "version_check"}:
            url = raw.get("url")
            if url:
                port = _extract_port(str(url))
                if port:
                    yield _Expect(
                        category="port_listening",
                        name=str(port),
                        source_step=sid,
                        fix_hint=f"port {port} must be open on target",
                        extra=(("url", str(url)),),
                    )

        # raw shell command parsing
        cmd = str(raw.get("command") or "")
        if cmd:
            yield from self._from_command(cmd, sid)

    def _from_command(self, cmd: str, sid: str) -> Iterable[_Expect]:
        for match in _RE_PODMAN_BUILD_TAG.finditer(cmd):
            yield _Expect(
                category="container_image",
                name=match.group(1),
                source_step=sid,
                fix_hint=f"image {match.group(1)} not present (will be built by step)",
            )
        for match in _RE_DOCKER_BUILD_TAG.finditer(cmd):
            yield _Expect(
                category="container_image",
                name=match.group(1),
                source_step=sid,
            )
        for match in _RE_MKDIR.finditer(cmd):
            path = match.group(1).strip("'\"")
            if not path or path.startswith("$"):
                continue
            yield _Expect(
                category="directory",
                name=_normalize_path(path),
                source_step=sid,
                fix_hint=f"mkdir -p {path}",
            )
        for match in _RE_SYSTEMCTL_USER_UNIT.finditer(cmd):
            yield _Expect(
                category="systemd_user_unit",
                name=match.group(1),
                source_step=sid,
            )
        for match in _RE_COMMAND_V.finditer(cmd):
            yield _Expect(
                category="binary",
                name=match.group(1),
                source_step=sid,
            )
        for match in _RE_APT_INSTALL.finditer(cmd):
            for pkg in match.group(1).split():
                pkg = pkg.strip()
                if not pkg or pkg.startswith("-"):
                    continue
                # treat the package name as a binary expectation only if it
                # looks like a single word command name
                if re.fullmatch(r"[\w.+\-]+", pkg) and "." not in pkg:
                    yield _Expect(
                        category="apt_package",
                        name=pkg,
                        source_step=sid,
                        fix_hint=f"sudo apt-get install -y {pkg}",
                    )


def _extract_port(url: str) -> Optional[int]:
    m = _RE_PORT_URL.match(url.strip())
    if not m:
        return None
    raw = m.group(1)
    if raw:
        return int(raw)
    if url.startswith("https://"):
        return 443
    if url.startswith("http://"):
        return 80
    return None


def _normalize_path(path: str) -> str:
    # strip surrounding quotes and trailing slashes
    p = path.strip().strip("'\"")
    if p.endswith("/") and len(p) > 1:
        p = p.rstrip("/")
    return p


def _strip_remote_dir(path: str) -> str:
    # rsync `dst` may include host: prefix when used outside spec semantics
    if ":" in path and not path.startswith("/"):
        # form like "user@host:/path"
        if path.count(":") == 1 and "/" in path.split(":", 1)[1]:
            return path.split(":", 1)[1]
    return path


# ── Probes ────────────────────────────────────────────────────────────────────

class _Probe:
    """Thin wrapper around SshClient with sensible audit timeouts."""

    def __init__(self, client: SshClient):
        self.client = client

    def has_binary(self, name: str) -> tuple[bool, str]:
        r = self.client.run(
            f"command -v {shlex.quote(name)} 2>/dev/null", timeout=10
        )
        return r.ok and bool(r.out), r.out or r.stderr

    def has_path(self, path: str, *, kind: str = "any") -> tuple[bool, str]:
        flag = {"file": "-f", "dir": "-d", "any": "-e"}.get(kind, "-e")
        # try plain test first; if path uses ~, expand on remote shell
        cmd = f"test {flag} {shlex.quote(path)} && echo OK || echo MISSING"
        # `~` inside a single-quoted argument is NOT expanded by the shell —
        # rerun without quoting if path begins with "~"
        if path.startswith("~"):
            cmd = f"test {flag} {path} && echo OK || echo MISSING"
        r = self.client.run(cmd, timeout=10)
        out = r.out
        return out == "OK", out or r.stderr

    def port_listening(self, port: int) -> tuple[bool, str]:
        r = self.client.run(
            f"ss -tlnH 2>/dev/null | awk '{{print $4}}' | "
            f"grep -E ':{port}$' | head -1",
            timeout=10,
        )
        if r.ok and r.out:
            return True, r.out
        # fallback to /proc/net/tcp parsing
        r2 = self.client.run(
            f"awk 'NR>1{{split($2,a,\":\"); printf \"%d\\n\",strtonum(\"0x\"a[2])}}' "
            f"/proc/net/tcp /proc/net/tcp6 2>/dev/null | sort -u | grep -E '^{port}$' | head -1",
            timeout=10,
        )
        return (r2.ok and bool(r2.out)), r2.out

    def has_image(self, ref: str) -> tuple[bool, str]:
        # podman first, fall back to docker
        for engine in ("podman", "docker"):
            r = self.client.run(
                f"{engine} image inspect {shlex.quote(ref)} "
                f"--format '{{{{.Id}}}}' 2>/dev/null", timeout=15,
            )
            if r.ok and r.out:
                return True, f"{engine}:{r.out[:12]}"
        return False, "image not found via podman/docker"

    def has_systemd_unit(self, unit: str, *, user: bool = False) -> tuple[bool, str]:
        scope = "--user " if user else ""
        r = self.client.run(
            f"systemctl {scope}list-unit-files --no-legend "
            f"{shlex.quote(unit)} 2>/dev/null | head -1",
            timeout=10,
        )
        return (r.ok and bool(r.out)), r.out or r.stderr

    def apt_package(self, name: str) -> tuple[bool, str]:
        r = self.client.run(
            f"dpkg-query -W -f='${{Status}}' {shlex.quote(name)} 2>/dev/null",
            timeout=10,
        )
        return (r.ok and "install ok installed" in r.out), r.out or r.stderr

    def disk_free_gib(self, path: str = "~") -> Optional[float]:
        r = self.client.run(
            f"df -P {path} 2>/dev/null | awk 'NR==2{{print $4}}'", timeout=10,
        )
        if not (r.ok and r.out.isdigit()):
            return None
        return int(r.out) / (1024 * 1024)


# ── Auditor ───────────────────────────────────────────────────────────────────

class Auditor:
    """Compare a MigrationSpec's expectations against a live target host."""

    # heuristic: builds touch ~6 GiB scratch space; warn under this
    MIN_FREE_GIB = 5.0

    def __init__(
        self,
        spec: MigrationSpec,
        spec_path: str | Path = "<spec>",
        *,
        host: Optional[str] = None,
        ssh_key: Optional[str] = None,
    ):
        self.spec = spec
        self.spec_path = str(spec_path)
        self.host = host or spec.target.host or spec.source.host or "local"
        client = SshClient(host=self.host, key=ssh_key)
        self.probe = _Probe(client)

    def run(self) -> AuditReport:
        report = AuditReport(
            spec_path=self.spec_path,
            host=self.host,
            target_strategy=str(self.spec.target.strategy.value),
        )

        if not self.probe.client.is_reachable(timeout=10):
            report.add(AuditCheck(
                category="connectivity",
                name=self.host,
                status="fail",
                detail="SSH unreachable",
                fix_hint="check network, SSH key, and BatchMode auth",
            ))
            return report
        report.add(AuditCheck(
            category="connectivity",
            name=self.host,
            status="pass",
            detail="ssh ok",
        ))

        # disk-free advisory check (always runs for build-heavy specs)
        free = self.probe.disk_free_gib("~")
        if free is None:
            report.add(AuditCheck(
                category="disk",
                name="~",
                status="warn",
                detail="could not read disk usage",
            ))
        else:
            if free < self.MIN_FREE_GIB:
                report.add(AuditCheck(
                    category="disk",
                    name="~",
                    status="fail",
                    detail=f"only {free:.1f} GiB free (need ≥ {self.MIN_FREE_GIB:.1f} GiB)",
                    fix_hint="prune images / clean /var/tmp / expand storage",
                ))
            else:
                report.add(AuditCheck(
                    category="disk",
                    name="~",
                    status="pass",
                    detail=f"{free:.1f} GiB free",
                ))

        # spec-derived checks
        for exp in _Extractor(self.spec).collect():
            self._dispatch(exp, report)

        logger.info(report.summary())
        return report

    def _dispatch(self, exp: _Expect, report: AuditReport) -> None:
        check = self._probe_one(exp)
        report.add(check)

    def _probe_one(self, exp: _Expect) -> AuditCheck:
        cat = exp.category
        if cat == "binary":
            return self._probe_binary(exp)
        elif cat == "directory":
            return self._probe_directory(exp)
        elif cat == "file":
            return self._probe_file(exp)
        elif cat == "local_file":
            return self._probe_local_file(exp)
        elif cat == "port_listening":
            return self._probe_port_listening(exp)
        elif cat == "container_image":
            return self._probe_container_image(exp)
        elif cat == "systemd_unit":
            return self._probe_systemd_unit(exp, user=False)
        elif cat == "systemd_user_unit":
            return self._probe_systemd_unit(exp, user=True)
        elif cat == "apt_package":
            return self._probe_apt_package(exp)
        else:
            return AuditCheck(
                category=cat, name=exp.name,
                status="skip", detail=f"unknown category {cat}",
                source_step=exp.source_step,
            )

    def _probe_binary(self, exp: _Expect) -> AuditCheck:
        ok, detail = self.probe.has_binary(exp.name)
        return AuditCheck(
            category=exp.category, name=exp.name,
            status="pass" if ok else "fail",
            detail=detail or ("present" if ok else "missing"),
            fix_hint=exp.fix_hint, source_step=exp.source_step,
        )

    def _probe_directory(self, exp: _Expect) -> AuditCheck:
        ok, detail = self.probe.has_path(exp.name, kind="dir")
        return AuditCheck(
            category=exp.category, name=exp.name,
            status="pass" if ok else "fail",
            detail=detail or ("present" if ok else "missing"),
            fix_hint=exp.fix_hint, source_step=exp.source_step,
        )

    def _probe_file(self, exp: _Expect) -> AuditCheck:
        ok, detail = self.probe.has_path(exp.name, kind="file")
        return AuditCheck(
            category=exp.category, name=exp.name,
            status="pass" if ok else "fail",
            detail=detail or ("present" if ok else "missing"),
            fix_hint=exp.fix_hint, source_step=exp.source_step,
        )

    def _probe_local_file(self, exp: _Expect) -> AuditCheck:
        local_ok = Path(exp.name).expanduser().exists()
        return AuditCheck(
            category=exp.category, name=exp.name,
            status="pass" if local_ok else "fail",
            detail="present" if local_ok else "missing on controller",
            fix_hint=exp.fix_hint, source_step=exp.source_step,
        )

    def _probe_port_listening(self, exp: _Expect) -> AuditCheck:
        ok, detail = self.probe.port_listening(int(exp.name))
        return AuditCheck(
            category=exp.category, name=exp.name,
            status="pass" if ok else "fail",
            detail=detail or ("present" if ok else "missing"),
            fix_hint=exp.fix_hint, source_step=exp.source_step,
        )

    def _probe_container_image(self, exp: _Expect) -> AuditCheck:
        ok, detail = self.probe.has_image(exp.name)
        # built-by-spec images: missing = "warn" not "fail"
        return AuditCheck(
            category=exp.category, name=exp.name,
            status="pass" if ok else "warn",
            detail=detail or ("present" if ok else "will be built by step"),
            fix_hint=exp.fix_hint, source_step=exp.source_step,
        )

    def _probe_systemd_unit(self, exp: _Expect, user: bool) -> AuditCheck:
        ok, detail = self.probe.has_systemd_unit(exp.name, user=user)
        return AuditCheck(
            category=exp.category, name=exp.name,
            status="pass" if ok else "fail",
            detail=detail or ("present" if ok else "missing"),
            fix_hint=exp.fix_hint, source_step=exp.source_step,
        )

    def _probe_apt_package(self, exp: _Expect) -> AuditCheck:
        ok, detail = self.probe.apt_package(exp.name)
        return AuditCheck(
            category=exp.category, name=exp.name,
            status="pass" if ok else "fail",
            detail=detail or ("present" if ok else "missing"),
            fix_hint=exp.fix_hint, source_step=exp.source_step,
        )


def audit_spec(
    spec_path: str | Path,
    *,
    host: Optional[str] = None,
    ssh_key: Optional[str] = None,
) -> AuditReport:
    """Convenience: load spec from file and run an audit."""
    spec = load_migration_spec(spec_path)
    return Auditor(spec, spec_path=spec_path, host=host, ssh_key=ssh_key).run()

"""Detection templates — scored pattern matching for device + environment + strategy.

Each ``DetectionTemplate`` defines a *signature*: a set of conditions that must
be satisfied by ``InfraState`` + ``ProbeResult`` data.  The template with the
highest cumulative score wins and drives:
  - strategy selection
  - environment classification (prod / dev / kiosk / staging)
  - suggested ``redeploy.yaml`` environments block
  - suggested migration spec template name

Architecture::

    InfraState ──┐
    ProbeResult ──┼──► TemplateEngine.score_all() ──► ranked [TemplateMatch]
    ProjectManifest ──┘                                     │
                                                            ▼
                                                   best match → DetectionResult
                                                            │
                                                            ▼
                                              generated redeploy.yaml snippet
                                              generated migration.yaml template
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..models import DeployStrategy


# ── Condition primitives ──────────────────────────────────────────────────────

ConditionFn = Callable[[dict], bool]   # ctx dict with keys from DetectionContext


@dataclass
class Condition:
    """A single scoreable condition."""
    description: str
    fn: ConditionFn
    weight: float = 1.0                # contribution to total score if True


# ── Template ──────────────────────────────────────────────────────────────────

@dataclass
class DetectionTemplate:
    """Named template for a device+environment+strategy combination.

    Fields
    ------
    id:           Unique template id (e.g. "rpi-systemd-kiosk")
    name:         Human label shown in CLI output
    strategy:     Target DeployStrategy this template produces
    environment:  Suggested environment label (prod/dev/rpi/staging/kiosk)
    conditions:   List of weighted Condition — all evaluated, scores summed
    required:     Conditions that MUST be True (else template is disqualified)
    spec_template: Name of migration spec template to suggest
    notes:        Human notes appended to generated YAML
    """
    id: str
    name: str
    strategy: DeployStrategy
    environment: str                   # prod | dev | kiosk | staging | local
    conditions: list[Condition] = field(default_factory=list)
    required: list[Condition] = field(default_factory=list)
    spec_template: str = "migration.yaml"
    notes: list[str] = field(default_factory=list)

    def score(self, ctx: dict) -> float:
        """Return weighted score [0..N] for this context, or -1 if disqualified."""
        # Hard-fail on required conditions
        for req in self.required:
            if not req.fn(ctx):
                return -1.0
        # Sum soft conditions
        total = sum(c.weight * (1.0 if c.fn(ctx) else 0.0) for c in self.conditions)
        return total

    @property
    def max_score(self) -> float:
        return sum(c.weight for c in self.conditions)


# ── Context builder ───────────────────────────────────────────────────────────

def build_context(
    state: Any,                        # InfraState
    probe: Optional[Any] = None,       # ProbeResult (from auto_probe)
    manifest: Optional[Any] = None,    # ProjectManifest
) -> dict:
    """Flatten InfraState + ProbeResult into a flat dict for condition evaluation."""
    rt = state.runtime
    svcs = state.services

    all_svc_names = (
        [s.name for s in svcs.get("docker", [])]
        + [s.name for s in svcs.get("k3s", [])]
        + [s.name for s in svcs.get("systemd", [])]
        + [s.name for s in svcs.get("podman", [])]
        + (probe.running_services if probe else [])
    )
    all_svc_lower = [s.lower() for s in all_svc_names]

    ctx: dict = {
        # runtime presence
        "has_docker":   bool(rt.docker),
        "has_k3s":      bool(rt.k3s),
        "has_podman":   bool(rt.podman),
        "has_systemd":  bool(rt.systemd),
        "docker_active": bool(svcs.get("docker")),
        "k3s_active":   bool(svcs.get("k3s")),
        "systemd_active": bool(svcs.get("systemd")),

        # arch / OS
        "arch":         rt.arch or (probe.arch if probe else ""),
        "is_arm":       (rt.arch or "").startswith(("aarch64", "arm")),
        "is_x86":       (rt.arch or "").startswith(("x86_64", "amd64")),
        "os_info":      rt.os or (probe.os_info if probe else ""),
        "is_debian":    "debian" in (rt.os or "").lower(),
        "is_ubuntu":    "ubuntu" in (rt.os or "").lower(),
        "is_raspberry": "raspberr" in (rt.os or (probe.os_info if probe else "")).lower()
                        or (rt.arch or "").startswith("aarch64"),

        # services
        "all_services": all_svc_lower,
        "has_nginx":    any("nginx" in s for s in all_svc_lower),
        "has_chromium": (probe.has_chromium if probe else False)
                        or any("chromium" in s for s in all_svc_lower),
        "has_kiosk_svc": any("kiosk" in s for s in all_svc_lower),
        "has_app_svc":  any(state.app.lower() in s for s in all_svc_lower),

        # ports
        "ports":        list(state.ports.keys()),
        "port_80":      80 in state.ports,
        "port_443":     443 in state.ports,
        "port_8000":    8000 in state.ports,
        "port_8080":    8080 in state.ports,
        "port_8100":    8100 in state.ports,

        # health
        "has_health":   any(h.healthy for h in state.health),
        "has_version":  bool(state.current_version),
        "version":      state.current_version or "",

        # conflicts
        "has_conflicts":    bool(state.conflicts),
        "dual_runtime":     any(c.type == "dual_runtime" for c in state.conflicts),
        "port_steal":       any(c.type == "port_steal" for c in state.conflicts),

        # probe extras
        "probe_strategy":   probe.strategy if probe else "",
        "probe_app":        probe.app if probe else "",

        # host
        "host":             state.host,
        "is_local":         state.host in ("local", "localhost", "127.0.0.1"),
        "ssh_user":         (probe.ssh_user if probe else "")
                            or state.host.split("@")[0] if "@" in state.host else "",

        # manifest envs
        "manifest_envs":    list(manifest.environments.keys()) if manifest else [],
        "app":              state.app,
    }
    return ctx


# ── Built-in templates ────────────────────────────────────────────────────────

def _svc(name: str) -> ConditionFn:
    """Service name fragment present in any known service."""
    return lambda ctx: any(name in s for s in ctx["all_services"])


def _port(p: int) -> ConditionFn:
    return lambda ctx: p in ctx["ports"]


def _build_templates() -> list[DetectionTemplate]:
    return [

        # ── RPi kiosk (native systemd + Chromium, no Docker) ─────────────────
        DetectionTemplate(
            id="rpi-native-kiosk",
            name="RPi Kiosk (systemd + Chromium, no Docker)",
            strategy=DeployStrategy.NATIVE_KIOSK,
            environment="kiosk",
            spec_template="04-rpi-kiosk/migration-rpi5.yaml",
            conditions=[
                Condition("aarch64 arch",    lambda ctx: ctx["is_arm"],        2.0),
                Condition("no Docker",        lambda ctx: not ctx["has_docker"], 2.0),
                Condition("Chromium present", lambda ctx: ctx["has_chromium"],  2.0),
                Condition("kiosk service",    lambda ctx: ctx["has_kiosk_svc"], 1.5),
                Condition("nginx present",    lambda ctx: ctx["has_nginx"],     1.0),
                Condition("port 8100",        _port(8100),                      1.0),
                Condition("systemd active",   lambda ctx: ctx["systemd_active"],1.0),
                Condition("Raspberry OS",     lambda ctx: ctx["is_raspberry"],  1.0),
                Condition("pi ssh user",      lambda ctx: ctx["ssh_user"] == "pi", 1.0),
            ],
            notes=[
                "RPi Kiosk: systemd + uvicorn + nginx + Chromium (Wayland)",
                "Sync: rsync --exclude db venv node_modules",
                "Service: c2004-services.service",
            ],
        ),

        # ── RPi systemd (no kiosk / no Chromium) ─────────────────────────────
        DetectionTemplate(
            id="rpi-systemd",
            name="RPi systemd backend (no GUI)",
            strategy=DeployStrategy.SYSTEMD,
            environment="rpi5",
            spec_template="04-rpi-kiosk/migration-rpi5.yaml",
            conditions=[
                Condition("aarch64 arch",   lambda ctx: ctx["is_arm"],         2.0),
                Condition("no Docker",       lambda ctx: not ctx["has_docker"], 2.0),
                Condition("no Chromium",     lambda ctx: not ctx["has_chromium"],1.0),
                Condition("systemd active",  lambda ctx: ctx["systemd_active"], 1.0),
                Condition("port 8000",       _port(8000),                       1.0),
                Condition("pi ssh user",     lambda ctx: ctx["ssh_user"] == "pi", 1.0),
            ],
            notes=[
                "RPi systemd backend: uvicorn on :8000 via systemd unit",
                "No X/Wayland — headless mode",
            ],
        ),

        # ── VPS Docker production ─────────────────────────────────────────────
        DetectionTemplate(
            id="vps-docker-prod",
            name="VPS Docker production",
            strategy=DeployStrategy.DOCKER_FULL,
            environment="prod",
            spec_template="01-vps-version-bump/migration.yaml",
            conditions=[
                Condition("Docker running",  lambda ctx: ctx["docker_active"],  3.0),
                Condition("x86_64",          lambda ctx: ctx["is_x86"],         2.0),
                Condition("port 80/443",     lambda ctx: ctx["port_80"] or ctx["port_443"], 2.0),
                Condition("no k3s",          lambda ctx: not ctx["has_k3s"],    1.0),
                Condition("root ssh user",   lambda ctx: ctx["ssh_user"] == "root", 1.0),
                Condition("Ubuntu/Debian",   lambda ctx: ctx["is_ubuntu"] or ctx["is_debian"], 1.0),
                Condition("health endpoint", lambda ctx: ctx["has_health"],     1.0),
            ],
            notes=[
                "VPS Docker: docker compose up --build -d",
                "Verify: curl https://{domain}/api/v1/health",
            ],
        ),

        # ── VPS k3s ───────────────────────────────────────────────────────────
        DetectionTemplate(
            id="vps-k3s",
            name="VPS k3s Kubernetes",
            strategy=DeployStrategy.K3S,
            environment="prod",
            spec_template="03-k3s-migration/migration.yaml",
            conditions=[
                Condition("k3s running",    lambda ctx: ctx["k3s_active"],    3.0),
                Condition("x86_64",         lambda ctx: ctx["is_x86"],        1.5),
                Condition("port 80/443",    lambda ctx: ctx["port_80"] or ctx["port_443"], 1.5),
                Condition("port steal",     lambda ctx: ctx["port_steal"],    1.0),
            ],
            notes=[
                "k3s: kubectl apply or helm upgrade",
                "Check iptables DNAT rules if port conflicts",
            ],
        ),

        # ── VPS Docker + k3s conflict ─────────────────────────────────────────
        DetectionTemplate(
            id="vps-dual-runtime-conflict",
            name="VPS dual runtime conflict (Docker + k3s)",
            strategy=DeployStrategy.DOCKER_FULL,
            environment="prod",
            spec_template="02-k3s-to-docker/migration.yaml",
            conditions=[
                Condition("dual runtime",   lambda ctx: ctx["dual_runtime"],   5.0),
                Condition("Docker present", lambda ctx: ctx["docker_active"],  2.0),
                Condition("k3s present",    lambda ctx: ctx["k3s_active"],     2.0),
                Condition("port steal",     lambda ctx: ctx["port_steal"],     2.0),
            ],
            required=[
                Condition("dual runtime required", lambda ctx: ctx["dual_runtime"], 1.0),
            ],
            notes=[
                "CONFLICT: k3s + Docker both running, port DNAT may intercept traffic",
                "Plan: stop k3s → migrate services to docker compose",
                "Spec: examples/02-k3s-to-docker/migration.yaml",
            ],
        ),

        # ── Podman Quadlet ────────────────────────────────────────────────────
        DetectionTemplate(
            id="podman-quadlet",
            name="Podman Quadlet (rootless containers)",
            strategy=DeployStrategy.PODMAN_QUADLET,
            environment="staging",
            spec_template="05-podman-quadlet/migration.yaml",
            conditions=[
                Condition("Podman installed", lambda ctx: ctx["has_podman"],  3.0),
                Condition("no Docker",        lambda ctx: not ctx["has_docker"], 2.0),
                Condition("systemd active",   lambda ctx: ctx["systemd_active"], 1.0),
                Condition("x86_64",           lambda ctx: ctx["is_x86"],      1.0),
            ],
            notes=[
                "Podman Quadlet: .container units in ~/.config/containers/systemd/",
                "Deploy: systemctl --user daemon-reload && systemctl --user restart app.service",
            ],
        ),

        # ── Local dev ─────────────────────────────────────────────────────────
        DetectionTemplate(
            id="local-dev",
            name="Local development (docker compose)",
            strategy=DeployStrategy.DOCKER_FULL,
            environment="dev",
            spec_template="migration.yaml",
            required=[
                Condition("is local host", lambda ctx: ctx["is_local"], 1.0),
            ],
            conditions=[
                Condition("is local host", lambda ctx: ctx["is_local"],       5.0),
                Condition("Docker running", lambda ctx: ctx["docker_active"],  2.0),
                Condition("port 8000",     _port(8000),                        1.0),
            ],
            notes=[
                "Local dev: docker compose up (no SSH)",
                "env_file: .env.local",
            ],
        ),

        # ── Generic systemd (unknown device) ─────────────────────────────────
        DetectionTemplate(
            id="generic-systemd",
            name="Generic systemd (unknown device)",
            strategy=DeployStrategy.SYSTEMD,
            environment="device",
            spec_template="migration.yaml",
            conditions=[
                Condition("systemd present",  lambda ctx: ctx["has_systemd"],  2.0),
                Condition("no Docker",        lambda ctx: not ctx["has_docker"], 1.0),
                Condition("no k3s",           lambda ctx: not ctx["has_k3s"],  1.0),
                Condition("app service",      lambda ctx: ctx["has_app_svc"],  1.0),
            ],
            notes=[
                "Generic systemd — check unit file names with: systemctl list-units",
            ],
        ),
    ]


TEMPLATES: list[DetectionTemplate] = _build_templates()


# ── Scoring engine ────────────────────────────────────────────────────────────

@dataclass
class TemplateMatch:
    """Scored template match."""
    template: DetectionTemplate
    score: float
    max_score: float
    matched_conditions: list[str]
    failed_conditions: list[str]

    @property
    def confidence(self) -> float:
        """Normalised [0..1] confidence."""
        return self.score / self.max_score if self.max_score > 0 else 0.0

    @property
    def confidence_label(self) -> str:
        c = self.confidence
        if c >= 0.85:
            return "high"
        if c >= 0.55:
            return "medium"
        return "low"


@dataclass
class DetectionResult:
    """Full result of template-based detection."""
    best: TemplateMatch
    ranked: list[TemplateMatch]           # all templates, best first
    ctx: dict                             # raw context used for scoring

    @property
    def strategy(self) -> DeployStrategy:
        return self.best.template.strategy

    @property
    def environment(self) -> str:
        return self.best.template.environment

    @property
    def spec_template(self) -> str:
        return self.best.template.spec_template

    def generated_env_block(self, app: str = "", host: str = "") -> str:
        """Generate a redeploy.yaml environments block snippet for this result."""
        t = self.best.template
        env_name = t.environment
        h = host or self.ctx.get("host", "HOST")
        a = app or self.ctx.get("app", "app")
        lines = [
            f"environments:",
            f"  {env_name}:",
            f"    host: {h}",
            f"    strategy: {t.strategy.value}",
            f"    app: {a}",
        ]
        if self.ctx.get("has_health"):
            port = 8000 if self.ctx.get("port_8000") else (8080 if self.ctx.get("port_8080") else 8000)
            ip = h.split("@")[-1] if "@" in h else h
            lines.append(f"    verify_url: http://{ip}:{port}/api/v1/health")
        return "\n".join(lines)

    def generated_notes(self) -> list[str]:
        return self.best.template.notes


class TemplateEngine:
    """Score all templates against a context and return ranked matches."""

    def __init__(self, templates: Optional[list[DetectionTemplate]] = None):
        self.templates = templates or TEMPLATES

    def score_all(self, ctx: dict) -> list[TemplateMatch]:
        """Score every template, return sorted best-first (disqualified = score -1 excluded)."""
        matches: list[TemplateMatch] = []
        for t in self.templates:
            raw_score = t.score(ctx)
            if raw_score < 0:
                continue            # disqualified by required condition
            matched = [c.description for c in t.conditions if c.fn(ctx)]
            failed  = [c.description for c in t.conditions if not c.fn(ctx)]
            matches.append(TemplateMatch(
                template=t,
                score=raw_score,
                max_score=t.max_score,
                matched_conditions=matched,
                failed_conditions=failed,
            ))
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches

    def detect(
        self,
        state: Any,
        probe: Optional[Any] = None,
        manifest: Optional[Any] = None,
    ) -> Optional[DetectionResult]:
        """Full pipeline: build context → score → return best match."""
        ctx = build_context(state, probe, manifest)
        ranked = self.score_all(ctx)
        if not ranked:
            return None
        return DetectionResult(best=ranked[0], ranked=ranked, ctx=ctx)

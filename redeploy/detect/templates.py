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

import yaml
from dataclasses import dataclass, field
from pathlib import Path
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

# ── Fact extractors ──────────────────────────────────────────────────────────

FactFn = Callable[[Any, Optional[Any], Optional[Any], dict], Any]


@dataclass(frozen=True)
class FactExtractor:
    """Extract a single key/value pair into the context dict.

    The callable receives ``(state, probe, manifest, ctx)`` where *ctx* is the
    partially-built dictionary (earlier extractors are already present).
    """

    key: str
    fn: FactFn

    def __call__(
        self,
        state: Any,
        probe: Optional[Any],
        manifest: Optional[Any],
        ctx: dict,
    ) -> None:
        ctx[self.key] = self.fn(state, probe, manifest, ctx)


def _all_services(state: Any, probe: Optional[Any]) -> list[str]:
    svcs = state.services
    names = (
        [s.name for s in svcs.get("docker", [])]
        + [s.name for s in svcs.get("k3s", [])]
        + [s.name for s in svcs.get("systemd", [])]
        + [s.name for s in svcs.get("podman", [])]
        + (probe.running_services if probe else [])
    )
    return [n.lower() for n in names]


# Ordered list of extractors.  Dependent extractors must appear *after* the
# facts they read from *ctx*.
EXTRACTORS: list[FactExtractor] = [
    # runtime presence
    FactExtractor("has_docker", lambda s, p, m, c: bool(s.runtime.docker)),
    FactExtractor("has_k3s", lambda s, p, m, c: bool(s.runtime.k3s)),
    FactExtractor("has_podman", lambda s, p, m, c: bool(s.runtime.podman)),
    FactExtractor("has_systemd", lambda s, p, m, c: bool(s.runtime.systemd)),
    FactExtractor("docker_active", lambda s, p, m, c: bool(s.services.get("docker"))),
    FactExtractor("k3s_active", lambda s, p, m, c: bool(s.services.get("k3s"))),
    FactExtractor("systemd_active", lambda s, p, m, c: bool(s.services.get("systemd"))),

    # arch / OS
    FactExtractor("arch", lambda s, p, m, c: s.runtime.arch or (p.arch if p else "")),
    FactExtractor("is_arm", lambda s, p, m, c: (s.runtime.arch or "").startswith(("aarch64", "arm"))),
    FactExtractor("is_x86", lambda s, p, m, c: (s.runtime.arch or "").startswith(("x86_64", "amd64"))),
    FactExtractor("os_info", lambda s, p, m, c: s.runtime.os or (p.os_info if p else "")),
    FactExtractor("is_debian", lambda s, p, m, c: "debian" in (s.runtime.os or "").lower()),
    FactExtractor("is_ubuntu", lambda s, p, m, c: "ubuntu" in (s.runtime.os or "").lower()),
    FactExtractor(
        "is_raspberry",
        lambda s, p, m, c: (
            "raspberr" in (s.runtime.os or (p.os_info if p else "")).lower()
            or (s.runtime.arch or "").startswith("aarch64")
        ),
    ),

    # services (depends on nothing in ctx)
    FactExtractor("all_services", lambda s, p, m, c: _all_services(s, p)),
    FactExtractor("has_nginx", lambda s, p, m, c: any("nginx" in svc for svc in c["all_services"])),
    FactExtractor(
        "has_chromium",
        lambda s, p, m, c: (
            bool(s.runtime.chromium)
            or (p.has_chromium if p else False)
            or any("chromium" in svc for svc in c["all_services"])
        ),
    ),
    FactExtractor("has_kiosk_svc", lambda s, p, m, c: any("kiosk" in svc for svc in c["all_services"])),
    FactExtractor("has_app_svc", lambda s, p, m, c: any(s.app.lower() in svc for svc in c["all_services"])),

    # ports
    FactExtractor("ports", lambda s, p, m, c: list(s.ports.keys())),
    FactExtractor("port_80", lambda s, p, m, c: 80 in s.ports),
    FactExtractor("port_443", lambda s, p, m, c: 443 in s.ports),
    FactExtractor("port_8000", lambda s, p, m, c: 8000 in s.ports),
    FactExtractor("port_8080", lambda s, p, m, c: 8080 in s.ports),
    FactExtractor("port_8100", lambda s, p, m, c: 8100 in s.ports),

    # health
    FactExtractor("has_health", lambda s, p, m, c: any(h.healthy for h in s.health)),
    FactExtractor("has_version", lambda s, p, m, c: bool(s.current_version)),
    FactExtractor("version", lambda s, p, m, c: s.current_version or ""),

    # conflicts
    FactExtractor("has_conflicts", lambda s, p, m, c: bool(s.conflicts)),
    FactExtractor("dual_runtime", lambda s, p, m, c: any(c.type == "dual_runtime" for c in s.conflicts)),
    FactExtractor("port_steal", lambda s, p, m, c: any(c.type == "port_steal" for c in s.conflicts)),

    # probe extras
    FactExtractor("probe_strategy", lambda s, p, m, c: p.strategy if p else ""),
    FactExtractor("probe_app", lambda s, p, m, c: p.app if p else ""),

    # host
    FactExtractor("host", lambda s, p, m, c: s.host),
    FactExtractor("is_local", lambda s, p, m, c: s.host in ("local", "localhost", "127.0.0.1")),
    FactExtractor(
        "ssh_user",
        lambda s, p, m, c: (p.ssh_user if p else "") or (s.host.split("@")[0] if "@" in s.host else ""),
    ),

    # manifest envs
    FactExtractor("manifest_envs", lambda s, p, m, c: list(m.environments.keys()) if m else []),
    FactExtractor("app", lambda s, p, m, c: s.app),
]


def build_context(
    state: Any,                        # InfraState
    probe: Optional[Any] = None,       # ProbeResult (from auto_probe)
    manifest: Optional[Any] = None,    # ProjectManifest
) -> dict:
    """Flatten InfraState + ProbeResult into a flat dict for condition evaluation."""
    ctx: dict = {}
    for extractor in EXTRACTORS:
        extractor(state, probe, manifest, ctx)
    return ctx


# ── Built-in templates ────────────────────────────────────────────────────────

def _svc(name: str) -> ConditionFn:
    """Service name fragment present in any known service."""
    return lambda ctx: any(name in s for s in ctx["all_services"])


def _port(p: int) -> ConditionFn:
    return lambda ctx: p in ctx["ports"]


def _load_templates_from_yaml() -> list[DetectionTemplate]:
    """Load templates from builtin/templates.yaml."""
    yaml_path = Path(__file__).parent / "builtin" / "templates.yaml"
    if not yaml_path.exists():
        return []

    data = yaml.safe_load(yaml_path.read_text())
    templates: list[DetectionTemplate] = []

    # Condition function registry (inline lambdas for compactness)
    _COND_FNS: dict[str, ConditionFn] = {
        "is_arm": lambda ctx: ctx["is_arm"],
        "not has_docker": lambda ctx: not ctx["has_docker"],
        "has_chromium": lambda ctx: ctx["has_chromium"],
        "has_kiosk_svc": lambda ctx: ctx["has_kiosk_svc"],
        "has_nginx": lambda ctx: ctx["has_nginx"],
        "port_8100": lambda ctx: 8100 in ctx["ports"],
        "systemd_active": lambda ctx: ctx["systemd_active"],
        "is_raspberry": lambda ctx: ctx["is_raspberry"],
        "ssh_user_pi": lambda ctx: ctx["ssh_user"] == "pi",
        "not has_chromium": lambda ctx: not ctx["has_chromium"],
        "port_8000": lambda ctx: 8000 in ctx["ports"],
        "docker_active": lambda ctx: ctx["docker_active"],
        "is_x86": lambda ctx: ctx["is_x86"],
        "port_80_or_443": lambda ctx: ctx["port_80"] or ctx["port_443"],
        "not has_k3s": lambda ctx: not ctx["has_k3s"],
        "ssh_user_root": lambda ctx: ctx["ssh_user"] == "root",
        "is_ubuntu_or_debian": lambda ctx: ctx["is_ubuntu"] or ctx["is_debian"],
        "has_health": lambda ctx: ctx["has_health"],
        "k3s_active": lambda ctx: ctx["k3s_active"],
        "port_steal": lambda ctx: ctx["port_steal"],
        "dual_runtime": lambda ctx: ctx["dual_runtime"],
        "has_podman": lambda ctx: ctx["has_podman"],
        "is_local": lambda ctx: ctx["is_local"],
        "has_systemd": lambda ctx: ctx["has_systemd"],
        "has_app_svc": lambda ctx: ctx["has_app_svc"],
    }

    for tmpl_data in data.get("templates", []):
        conditions = []
        for cond_data in tmpl_data.get("conditions", []):
            fn_name = cond_data["fn"]
            fn = _COND_FNS.get(fn_name)
            if fn is None:
                raise ValueError(f"Unknown condition function: {fn_name}")
            conditions.append(Condition(
                description=cond_data["description"],
                fn=fn,
                weight=cond_data.get("weight", 1.0),
            ))

        required = []
        for req_data in tmpl_data.get("required", []):
            fn_name = req_data["fn"]
            fn = _COND_FNS.get(fn_name)
            if fn is None:
                raise ValueError(f"Unknown condition function: {fn_name}")
            required.append(Condition(
                description=req_data["description"],
                fn=fn,
                weight=req_data.get("weight", 1.0),
            ))

        strategy_str = tmpl_data["strategy"]
        strategy = DeployStrategy(strategy_str)

        templates.append(DetectionTemplate(
            id=tmpl_data["id"],
            name=tmpl_data["name"],
            strategy=strategy,
            environment=tmpl_data["environment"],
            conditions=conditions,
            required=required,
            spec_template=tmpl_data.get("spec_template", "migration.yaml"),
            notes=tmpl_data.get("notes", []),
        ))

    return templates


def _build_templates() -> list[DetectionTemplate]:
    """Load templates from YAML file."""
    return _load_templates_from_yaml()


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

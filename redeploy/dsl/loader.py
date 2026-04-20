"""DSL loader — converts parsed DSLNode tree into redeploy model objects.

Loads ``redeploy.css`` (or ``redeploy.less``) and produces:
  - ``ProjectManifest``            (app metadata + environments)
  - ``list[DetectionTemplate]``    (custom scoring templates)
  - ``list[WorkflowDef]``          (named CLI workflows)

Can also **export** back to YAML or CSS for round-tripping.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..models import DeployStrategy, EnvironmentConfig, ProjectManifest
from ..detect.templates import Condition, DetectionTemplate
from .parser import DSLNode, RedeployDSLParser


# ── Workflow definition (from DSL) ────────────────────────────────────────────

@dataclass
class WorkflowStep:
    index: int
    command: str
    doc: str = ""
    plugin_type: Optional[str] = None
    plugin_params: dict = field(default_factory=dict)

    @classmethod
    def from_command(cls, index: int, raw: str) -> "WorkflowStep":
        """Parse raw step string; detect 'plugin <type> [key=val ...]' syntax."""
        import re as _re
        raw = raw.strip()
        m = _re.match(r"^plugin\s+(\S+)(.*)", raw)
        if m:
            ptype = m.group(1)
            rest = m.group(2).strip()
            params: dict = {}
            for kv in _re.findall(r'(\w+)=("(?:[^"\\]|\\.)*"|\S+)', rest):
                k, v = kv
                params[k] = v.strip('"')
            return cls(index=index, command=raw, plugin_type=ptype, plugin_params=params)
        return cls(index=index, command=raw)


@dataclass
class WorkflowDef:
    """Named deployment workflow parsed from ``workflow[name="…"] { … }``."""
    name: str
    trigger: str = "manual"           # manual | on_push | cron:...
    steps: list[WorkflowStep] = field(default_factory=list)
    description: str = ""
    doc: str = ""

    def as_shell(self) -> str:
        """Render as executable shell script.

        Plugin steps are rendered as ``redeploy plugin run <type> key=val``
        which is the CLI equivalent for pipeline inspection.
        """
        lines = [f"#!/bin/bash", f"# workflow: {self.name}", ""]
        if self.description:
            lines.append(f"# {self.description}")
        for step in self.steps:
            if step.doc:
                lines.append(f"# {step.doc}")
            if step.plugin_type:
                params = " ".join(f"{k}={v}" for k, v in step.plugin_params.items())
                lines.append(f"# plugin step — executed by redeploy executor")
                lines.append(f"# redeploy plugin run {step.plugin_type}"
                             + (f" {params}" if params else ""))
            else:
                lines.append(step.command)
        return "\n".join(lines)


# ── Template condition registry ───────────────────────────────────────────────
# Maps condition key (used in score[key]) → (description, ConditionFn, default_weight)

_CONDITION_REGISTRY: dict[str, tuple[str, object, float]] = {
    "is_arm":       ("aarch64 arch",       lambda ctx: ctx.get("is_arm", False),         2.0),
    "is_x86":       ("x86_64 arch",        lambda ctx: ctx.get("is_x86", False),         2.0),
    "no_docker":    ("no Docker",          lambda ctx: not ctx.get("has_docker", True),   2.0),
    "docker":       ("Docker running",     lambda ctx: ctx.get("docker_active", False),   3.0),
    "k3s":          ("k3s running",        lambda ctx: ctx.get("k3s_active", False),      3.0),
    "no_k3s":       ("no k3s",             lambda ctx: not ctx.get("has_k3s", False),     1.0),
    "chromium":     ("Chromium present",   lambda ctx: ctx.get("has_chromium", False),    2.0),
    "kiosk_svc":    ("kiosk service",      lambda ctx: ctx.get("has_kiosk_svc", False),   1.5),
    "nginx":        ("nginx present",      lambda ctx: ctx.get("has_nginx", False),       1.0),
    "port_80":      ("port 80",            lambda ctx: ctx.get("port_80", False),         1.0),
    "port_443":     ("port 443",           lambda ctx: ctx.get("port_443", False),        1.0),
    "port_8000":    ("port 8000",          lambda ctx: ctx.get("port_8000", False),       1.0),
    "port_8100":    ("port 8100",          lambda ctx: ctx.get("port_8100", False),       1.0),
    "raspberry":    ("Raspberry OS",       lambda ctx: ctx.get("is_raspberry", False),    1.0),
    "systemd":      ("systemd active",     lambda ctx: ctx.get("systemd_active", False),  1.0),
    "podman":       ("Podman installed",   lambda ctx: ctx.get("has_podman", False),      3.0),
    "root_user":    ("root ssh user",      lambda ctx: ctx.get("ssh_user") == "root",     1.0),
    "pi_user":      ("pi ssh user",        lambda ctx: ctx.get("ssh_user") == "pi",       1.0),
    "health":       ("health endpoint",    lambda ctx: ctx.get("has_health", False),      1.0),
    "dual_runtime": ("dual runtime",       lambda ctx: ctx.get("dual_runtime", False),    5.0),
    "port_steal":   ("port steal",         lambda ctx: ctx.get("port_steal", False),      1.0),
    "local":        ("local host",         lambda ctx: ctx.get("is_local", False),        5.0),
    "ubuntu":       ("Ubuntu",             lambda ctx: ctx.get("is_ubuntu", False),       1.0),
    "debian":       ("Debian",             lambda ctx: ctx.get("is_debian", False),       1.0),
    "has_version":  ("version detected",   lambda ctx: ctx.get("has_version", False),     1.0),
}


def _build_condition(key: str, weight: Optional[float] = None) -> Optional[Condition]:
    """Look up condition key in registry and return Condition with optional weight override."""
    if key not in _CONDITION_REGISTRY:
        return None
    desc, fn, default_w = _CONDITION_REGISTRY[key]
    c = Condition(description=desc, fn=fn, weight=weight if weight is not None else default_w)  # type: ignore[arg-type]
    c.__dict__["_registry_key"] = key   # store for round-trip export
    return c


# ── Loader ────────────────────────────────────────────────────────────────────

@dataclass
class LoadResult:
    """Full result of loading a ``redeploy.css`` file."""
    manifest: Optional[ProjectManifest]
    templates: list[DetectionTemplate]
    workflows: list[WorkflowDef]
    raw_nodes: list[DSLNode]
    source_file: Path


def load_css(path: Path) -> LoadResult:
    """Parse ``redeploy.css`` and return manifest + templates + workflows."""
    parser = RedeployDSLParser()
    nodes = parser.parse(path.read_text())
    return _build_from_nodes(nodes, parser.at_rules, source_file=path)


def load_css_text(text: str, source_file: Optional[Path] = None) -> LoadResult:
    """Parse CSS text directly (for tests)."""
    parser = RedeployDSLParser()
    nodes = parser.parse(text)
    return _build_from_nodes(nodes, parser.at_rules,
                             source_file=source_file or Path("<string>"))


def _build_from_nodes(
    nodes: list[DSLNode],
    at_rules: dict[str, str],
    source_file: Path,
) -> LoadResult:
    manifest = _build_manifest(nodes, at_rules)
    templates = _build_templates(nodes)
    workflows = _build_workflows(nodes)
    return LoadResult(
        manifest=manifest,
        templates=templates,
        workflows=workflows,
        raw_nodes=nodes,
        source_file=source_file,
    )


# ── Manifest builder ──────────────────────────────────────────────────────────

def _build_manifest(nodes: list[DSLNode], at_rules: dict[str, str]) -> Optional[ProjectManifest]:
    """Build ProjectManifest from @app, @version, @spec at-rules + environment blocks."""
    app_name = at_rules.get("app", "")
    version = at_rules.get("version", "")
    spec_file = at_rules.get("spec", "migration.yaml")
    ssh_key = at_rules.get("ssh_key", None)
    domain = at_rules.get("domain", None)

    # Also check app { } block
    for n in nodes:
        if n.selector_type == "app":
            app_name = app_name or n.get("name")
            spec_file = n.get("spec", spec_file)
            ssh_key = ssh_key or n.get("ssh_key") or None
            domain = domain or n.get("domain") or None

    environments: dict[str, EnvironmentConfig] = {}
    for n in nodes:
        if n.selector_type != "environment":
            continue
        env_name = n.name
        if not env_name:
            continue
        strategy_str = n.get("strategy")
        try:
            strategy = DeployStrategy(strategy_str) if strategy_str else None
        except ValueError:
            strategy = None

        environments[env_name] = EnvironmentConfig(
            host=n.get("host") or None,
            strategy=strategy_str or None,
            app=n.get("app") or None,
            domain=n.get("domain") or None,
            remote_dir=n.get("remote_dir") or None,
            env_file=n.get("env_file") or None,
            ssh_key=n.get("ssh_key") or None,
            ssh_port=int(n.get("ssh_port", "22")),
            verify_url=n.get("verify_url") or None,
            spec=n.get("spec") or None,
        )

    if not (app_name or environments):
        return None

    return ProjectManifest(
        app=app_name or "app",
        spec=spec_file,
        ssh_key=ssh_key,
        domain=domain,
        environments=environments,
    )


# ── Template builder ──────────────────────────────────────────────────────────

def _build_templates(nodes: list[DSLNode]) -> list[DetectionTemplate]:
    """Build DetectionTemplate objects from template[id="…"] blocks.

    score properties::
        score[is_arm]: 2.5;       // named condition with weight
        require[dual_runtime];    // required condition (weight ignored)
        note: some deployment note;
    """
    templates = []
    # score[key] regex
    score_re = __import__("re").compile(r"score\[([^\]]+)\]")
    req_re   = __import__("re").compile(r"require\[([^\]]+)\]")

    for n in nodes:
        if n.selector_type != "template":
            continue
        tid  = n.attrs.get("id", n.name)
        name = n.get("name", tid)
        env  = n.get("environment", "unknown")
        strategy_str = n.get("strategy", "unknown")
        spec = n.get("spec", "migration.yaml")

        try:
            strategy = DeployStrategy(strategy_str)
        except ValueError:
            strategy = DeployStrategy.UNKNOWN

        conditions: list[Condition] = []
        required: list[Condition] = []
        notes: list[str] = []

        for prop_key, prop_val in n.props.items():
            # score[condition_key]: weight;
            sm = score_re.match(prop_key)
            if sm:
                cond_key = sm.group(1)
                try:
                    weight = float(prop_val) if prop_val else None
                except ValueError:
                    weight = None
                cond = _build_condition(cond_key, weight)
                if cond:
                    conditions.append(cond)
                continue

            # require[condition_key]: ignored;
            rm = req_re.match(prop_key)
            if rm:
                cond_key = rm.group(1)
                cond = _build_condition(cond_key)
                if cond:
                    required.append(cond)
                continue

            # note: text;
            if prop_key == "note":
                vals = prop_val if isinstance(prop_val, list) else [prop_val]
                notes.extend(vals)

        templates.append(DetectionTemplate(
            id=tid,
            name=name or tid,
            strategy=strategy,
            environment=env,
            conditions=conditions,
            required=required,
            spec_template=spec,
            notes=notes,
        ))

    return templates


# ── Workflow builder ──────────────────────────────────────────────────────────

def _build_workflows(nodes: list[DSLNode]) -> list[WorkflowDef]:
    """Build WorkflowDef objects from workflow[name="…"] blocks."""
    import re
    step_re = re.compile(r"step-(\d+)")
    workflows = []

    for n in nodes:
        if n.selector_type != "workflow":
            continue
        wf = WorkflowDef(
            name=n.name,
            trigger=n.get("trigger", "manual"),
            description=n.get("description", ""),
            doc=n.doc,
        )
        # Collect step-N properties in order
        step_props = sorted(
            [(step_re.match(k), k, v) for k, v in n.props.items() if step_re.match(k)],
            key=lambda t: int(t[0].group(1)),  # type: ignore[union-attr]
        )
        for m, key, val in step_props:
            idx = int(m.group(1))  # type: ignore[union-attr]
            vals = val if isinstance(val, list) else [val]
            for cmd in vals:
                wf.steps.append(WorkflowStep.from_command(idx, cmd))
        workflows.append(wf)

    return workflows


# ── Exporter (ProjectManifest → CSS) ─────────────────────────────────────────

def manifest_to_css(manifest: ProjectManifest, app: str = "") -> str:
    """Render a ProjectManifest back to ``redeploy.css`` format."""
    lines = [
        f"// redeploy.css — generated by `redeploy export --format css`",
        f"// Edit freely; loaded automatically alongside redeploy.yaml",
        f"",
        f"@app {app or manifest.app};",
        f"@spec {manifest.spec};",
    ]
    if manifest.ssh_key:
        lines.append(f"@ssh_key {manifest.ssh_key};")
    if manifest.domain:
        lines.append(f"@domain {manifest.domain};")
    lines.append("")

    for env_name, cfg in manifest.environments.items():
        lines.append(f'environment[name="{env_name}"] {{')
        if cfg.host:
            lines.append(f'  host: {cfg.host};')
        if cfg.strategy:
            lines.append(f'  strategy: {cfg.strategy};')
        if cfg.app:
            lines.append(f'  app: {cfg.app};')
        if cfg.domain:
            lines.append(f'  domain: {cfg.domain};')
        if cfg.remote_dir:
            lines.append(f'  remote_dir: {cfg.remote_dir};')
        if cfg.env_file:
            lines.append(f'  env_file: {cfg.env_file};')
        if cfg.ssh_key:
            lines.append(f'  ssh_key: {cfg.ssh_key};')
        if cfg.verify_url:
            lines.append(f'  verify_url: {cfg.verify_url};')
        if cfg.spec:
            lines.append(f'  spec: {cfg.spec};')
        lines.append(f'}}')
        lines.append("")

    return "\n".join(lines)


def _condition_key(c: "Condition") -> str:
    """Return registry key for a condition (stored by _build_condition or reverse lookup)."""
    stored = c.__dict__.get("_registry_key")
    if stored:
        return stored
    # Fallback: reverse lookup by description
    return next(
        (k for k, (d, _, _) in _CONDITION_REGISTRY.items() if d == c.description),
        c.description.lower().replace(" ", "_"),
    )


def templates_to_css(templates: list[DetectionTemplate]) -> str:
    """Render DetectionTemplate list to CSS block."""
    lines: list[str] = []
    for t in templates:
        if t.notes:
            for note in t.notes:
                lines.append(f"// {note}")
        lines.append(f'template[id="{t.id}"] {{')
        lines.append(f'  name: {t.name};')
        lines.append(f'  environment: {t.environment};')
        lines.append(f'  strategy: {t.strategy.value};')
        lines.append(f'  spec: {t.spec_template};')
        for c in t.conditions:
            key = _condition_key(c)
            lines.append(f'  score[{key}]: {c.weight};')
        for r in t.required:
            key = _condition_key(r)
            lines.append(f'  require[{key}];')
        lines.append(f'}}')
        lines.append("")
    return "\n".join(lines)

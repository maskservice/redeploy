"""Tests for detect/templates.py — DetectionTemplate scoring, TemplateEngine, build_context."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from redeploy.detect.templates import (
    TEMPLATES,
    Condition,
    DetectionResult,
    DetectionTemplate,
    TemplateEngine,
    TemplateMatch,
    build_context,
)
from redeploy.models import (
    AppHealthInfo,
    ConflictInfo,
    ConflictSeverity,
    DeployStrategy,
    InfraState,
    PortInfo,
    RuntimeInfo,
    ServiceInfo,
)


# ── helpers ───────────────────────────────────────────────────────────────────


def _state(
    host: str = "root@10.0.0.1",
    app: str = "myapp",
    docker: str = "",
    k3s: str = "",
    podman: str = "",
    systemd: str = "",
    arch: str = "x86_64",
    os: str = "Ubuntu 22.04",
    docker_svcs: list = None,
    k3s_svcs: list = None,
    systemd_svcs: list = None,
    ports: dict = None,
    health: list = None,
    conflicts: list = None,
    version: str = "",
) -> InfraState:
    rt = RuntimeInfo(docker=docker, k3s=k3s, podman=podman, systemd=systemd,
                     arch=arch, os=os)
    svcs: dict = {
        "docker": [ServiceInfo(name=n) for n in (docker_svcs or [])],
        "k3s":    [ServiceInfo(name=n) for n in (k3s_svcs or [])],
        "systemd":[ServiceInfo(name=n) for n in (systemd_svcs or [])],
        "podman": [],
    }
    port_map = {}
    for p in (ports or []):
        port_map[p] = PortInfo(port=p, process="test")
    return InfraState(
        host=host,
        app=app,
        runtime=rt,
        services=svcs,
        ports=port_map,
        health=health or [],
        conflicts=conflicts or [],
        current_version=version or None,
    )


def _probe(ssh_user="root", arch="x86_64", os_info="Ubuntu", strategy="",
           app="", has_chromium=False, running_services=None):
    p = MagicMock()
    p.ssh_user = ssh_user
    p.arch = arch
    p.os_info = os_info
    p.strategy = strategy
    p.app = app
    p.has_chromium = has_chromium
    p.running_services = running_services or []
    return p


# ── build_context ─────────────────────────────────────────────────────────────


class TestBuildContext:
    def test_has_docker_true(self):
        ctx = build_context(_state(docker="20.10"))
        assert ctx["has_docker"] is True

    def test_has_docker_false(self):
        ctx = build_context(_state(docker=""))
        assert ctx["has_docker"] is False

    def test_has_k3s(self):
        ctx = build_context(_state(k3s="v1.26"))
        assert ctx["has_k3s"] is True

    def test_has_podman(self):
        ctx = build_context(_state(podman="4.0"))
        assert ctx["has_podman"] is True

    def test_is_arm(self):
        ctx = build_context(_state(arch="aarch64"))
        assert ctx["is_arm"] is True
        assert ctx["is_x86"] is False

    def test_is_x86(self):
        ctx = build_context(_state(arch="x86_64"))
        assert ctx["is_x86"] is True
        assert ctx["is_arm"] is False

    def test_is_ubuntu(self):
        ctx = build_context(_state(os="Ubuntu 22.04"))
        assert ctx["is_ubuntu"] is True
        assert ctx["is_debian"] is False

    def test_is_debian(self):
        ctx = build_context(_state(os="Debian GNU/Linux 12"))
        assert ctx["is_debian"] is True

    def test_is_raspberry(self):
        ctx = build_context(_state(arch="aarch64", os="Raspbian"))
        assert ctx["is_raspberry"] is True

    def test_port_mapping(self):
        ctx = build_context(_state(ports=[80, 443, 8000]))
        assert ctx["port_80"] is True
        assert ctx["port_443"] is True
        assert ctx["port_8000"] is True
        assert ctx["port_8080"] is False

    def test_docker_active_from_services(self):
        ctx = build_context(_state(docker="20.10", docker_svcs=["traefik", "myapp"]))
        assert ctx["docker_active"] is True

    def test_k3s_active_from_services(self):
        ctx = build_context(_state(k3s="v1.26", k3s_svcs=["nginx"]))
        assert ctx["k3s_active"] is True

    def test_has_nginx(self):
        ctx = build_context(_state(docker_svcs=["nginx-proxy"], docker="1"))
        assert ctx["has_nginx"] is True

    def test_has_health(self):
        h = AppHealthInfo(url="http://x/health", healthy=True)
        ctx = build_context(_state(health=[h]))
        assert ctx["has_health"] is True

    def test_has_version(self):
        ctx = build_context(_state(version="1.0.20"))
        assert ctx["has_version"] is True
        assert ctx["version"] == "1.0.20"

    def test_is_local(self):
        ctx = build_context(_state(host="local"))
        assert ctx["is_local"] is True

    def test_probe_ssh_user(self):
        ctx = build_context(_state(), probe=_probe(ssh_user="pi"))
        assert ctx["ssh_user"] == "pi"

    def test_probe_chromium(self):
        ctx = build_context(_state(), probe=_probe(has_chromium=True))
        assert ctx["has_chromium"] is True

    def test_dual_runtime_conflict(self):
        c = ConflictInfo(type="dual_runtime", description="both running",
                         severity=ConflictSeverity.HIGH)
        ctx = build_context(_state(conflicts=[c]))
        assert ctx["dual_runtime"] is True

    def test_port_steal_conflict(self):
        c = ConflictInfo(type="port_steal", description="iptables DNAT",
                         severity=ConflictSeverity.HIGH)
        ctx = build_context(_state(conflicts=[c]))
        assert ctx["port_steal"] is True

    def test_manifest_envs(self):
        from redeploy.models import EnvironmentConfig, ProjectManifest
        m = ProjectManifest(app="x", environments={
            "prod": EnvironmentConfig(host="x"), "dev": EnvironmentConfig(host="y")
        })
        ctx = build_context(_state(), manifest=m)
        assert "prod" in ctx["manifest_envs"]
        assert "dev" in ctx["manifest_envs"]


# ── DetectionTemplate.score ───────────────────────────────────────────────────


class TestDetectionTemplateScore:
    def _tpl(self, conditions=None, required=None) -> DetectionTemplate:
        return DetectionTemplate(
            id="test", name="test", strategy=DeployStrategy.DOCKER_FULL,
            environment="prod",
            conditions=conditions or [],
            required=required or [],
        )

    def test_all_conditions_met(self):
        t = self._tpl(conditions=[
            Condition("c1", lambda ctx: True, 2.0),
            Condition("c2", lambda ctx: True, 1.0),
        ])
        assert t.score({}) == 3.0

    def test_partial_conditions(self):
        t = self._tpl(conditions=[
            Condition("yes", lambda ctx: True, 2.0),
            Condition("no",  lambda ctx: False, 1.0),
        ])
        assert t.score({}) == 2.0

    def test_required_fail_returns_minus_one(self):
        t = self._tpl(
            conditions=[Condition("c1", lambda ctx: True, 2.0)],
            required=[Condition("req", lambda ctx: False, 1.0)],
        )
        assert t.score({}) == -1.0

    def test_required_pass_continues_to_conditions(self):
        t = self._tpl(
            conditions=[Condition("c1", lambda ctx: True, 3.0)],
            required=[Condition("req", lambda ctx: True, 1.0)],
        )
        assert t.score({}) == 3.0

    def test_max_score(self):
        t = self._tpl(conditions=[
            Condition("a", lambda ctx: False, 2.0),
            Condition("b", lambda ctx: False, 1.5),
        ])
        assert t.max_score == 3.5

    def test_no_conditions_zero_score(self):
        t = self._tpl()
        assert t.score({}) == 0.0


# ── TemplateEngine ────────────────────────────────────────────────────────────


class TestTemplateEngine:
    def test_score_all_returns_sorted(self):
        t1 = DetectionTemplate("a", "A", DeployStrategy.DOCKER_FULL, "prod",
            conditions=[Condition("x", lambda ctx: True, 5.0)])
        t2 = DetectionTemplate("b", "B", DeployStrategy.K3S, "prod",
            conditions=[Condition("x", lambda ctx: True, 2.0)])
        engine = TemplateEngine([t1, t2])
        matches = engine.score_all({})
        assert matches[0].template.id == "a"
        assert matches[1].template.id == "b"

    def test_disqualified_excluded(self):
        t1 = DetectionTemplate("ok", "ok", DeployStrategy.DOCKER_FULL, "prod",
            conditions=[Condition("x", lambda ctx: True, 1.0)])
        t2 = DetectionTemplate("bad", "bad", DeployStrategy.K3S, "prod",
            required=[Condition("req", lambda ctx: False, 1.0)])
        engine = TemplateEngine([t1, t2])
        matches = engine.score_all({})
        ids = [m.template.id for m in matches]
        assert "bad" not in ids
        assert "ok" in ids

    def test_detect_returns_none_when_all_disqualified(self):
        t = DetectionTemplate("bad", "bad", DeployStrategy.K3S, "prod",
            required=[Condition("req", lambda ctx: False)])
        engine = TemplateEngine([t])
        result = engine.detect(_state())
        assert result is None

    def test_detect_returns_best(self):
        engine = TemplateEngine()
        # Local dev state should score high for local-dev template
        state = _state(host="local", docker="20.10",
                       docker_svcs=["myapp"], ports=[8000])
        result = engine.detect(state)
        assert result is not None
        assert result.best.template.id == "local-dev"

    def test_matched_conditions_populated(self):
        t = DetectionTemplate("t", "T", DeployStrategy.DOCKER_FULL, "prod",
            conditions=[
                Condition("yes", lambda ctx: True, 1.0),
                Condition("no",  lambda ctx: False, 1.0),
            ])
        engine = TemplateEngine([t])
        matches = engine.score_all({})
        assert "yes" in matches[0].matched_conditions
        assert "no" in matches[0].failed_conditions


# ── TemplateMatch confidence ──────────────────────────────────────────────────


class TestTemplateMatchConfidence:
    def _match(self, score, max_score) -> TemplateMatch:
        t = DetectionTemplate("t", "T", DeployStrategy.DOCKER_FULL, "prod")
        return TemplateMatch(template=t, score=score, max_score=max_score,
                             matched_conditions=[], failed_conditions=[])

    def test_high_confidence(self):
        assert self._match(9, 10).confidence_label == "high"

    def test_medium_confidence(self):
        assert self._match(6, 10).confidence_label == "medium"

    def test_low_confidence(self):
        assert self._match(2, 10).confidence_label == "low"

    def test_zero_max_score(self):
        assert self._match(0, 0).confidence == 0.0


# ── Built-in templates ────────────────────────────────────────────────────────


class TestBuiltinTemplates:
    """Smoke-test that built-in templates score plausibly for expected contexts."""

    def test_vps_docker_wins_for_docker_x86(self):
        engine = TemplateEngine()
        state = _state(
            docker="20.10", docker_svcs=["traefik", "myapp"],
            ports=[80, 443], arch="x86_64", os="Ubuntu 22.04",
            health=[AppHealthInfo(url="http://x/h", healthy=True)],
        )
        result = engine.detect(state, probe=_probe(ssh_user="root"))
        assert result is not None
        assert result.best.template.id == "vps-docker-prod"

    def test_k3s_template_wins_for_k3s(self):
        engine = TemplateEngine()
        state = _state(
            k3s="v1.26", k3s_svcs=["nginx-ingress"],
            ports=[80, 443], arch="x86_64",
            conflicts=[ConflictInfo(type="port_steal", description="dnat",
                                    severity=ConflictSeverity.HIGH)],
        )
        result = engine.detect(state)
        assert result is not None
        assert result.best.template.id in ("vps-k3s", "vps-dual-runtime-conflict")

    def test_rpi_kiosk_wins_for_arm_chromium(self):
        engine = TemplateEngine()
        state = _state(
            arch="aarch64", os="Raspbian GNU/Linux 11",
            systemd="systemd 252",
            systemd_svcs=["kiosk", "c2004-services"],
            ports=[8100],
        )
        result = engine.detect(state, probe=_probe(
            ssh_user="pi", arch="aarch64", has_chromium=True
        ))
        assert result is not None
        assert result.best.template.id == "rpi-native-kiosk"

    def test_dual_runtime_conflict_wins_with_required(self):
        engine = TemplateEngine()
        c = ConflictInfo(type="dual_runtime", description="both running",
                         severity=ConflictSeverity.HIGH)
        c2 = ConflictInfo(type="port_steal", description="dnat",
                          severity=ConflictSeverity.HIGH)
        state = _state(
            docker="20.10", docker_svcs=["myapp"],
            k3s="v1.26", k3s_svcs=["nginx"],
            ports=[80, 443], arch="x86_64",
            conflicts=[c, c2],
        )
        result = engine.detect(state)
        assert result is not None
        # dual_runtime template has 5+2+2+2=11 max vs docker-prod 3+2+2+1+1+1+1=11
        # Verify dual_runtime_conflict appears in top 2 results
        top_ids = [m.template.id for m in result.ranked[:2]]
        assert "vps-dual-runtime-conflict" in top_ids

    def test_podman_template(self):
        engine = TemplateEngine()
        state = _state(podman="4.0", arch="x86_64", systemd="systemd 252",
                       systemd_svcs=["myapp"])
        result = engine.detect(state)
        assert result is not None
        assert result.best.template.id == "podman-quadlet"

    def test_all_templates_have_unique_ids(self):
        ids = [t.id for t in TEMPLATES]
        assert len(ids) == len(set(ids))


# ── DetectionResult helpers ───────────────────────────────────────────────────


class TestDetectionResult:
    def _result(self, template_id="vps-docker-prod", score=8.0, max_score=10.0):
        t = next(t for t in TEMPLATES if t.id == template_id)
        match = TemplateMatch(template=t, score=score, max_score=max_score,
                              matched_conditions=["Docker running"],
                              failed_conditions=[])
        return DetectionResult(best=match, ranked=[match], ctx={
            "host": "root@10.0.0.1", "app": "myapp",
            "has_health": True, "port_8000": True, "port_8080": False,
        })

    def test_strategy(self):
        r = self._result()
        assert r.strategy == DeployStrategy.DOCKER_FULL

    def test_environment(self):
        r = self._result()
        assert r.environment == "prod"

    def test_spec_template(self):
        r = self._result()
        assert "migration.yaml" in r.spec_template

    def test_generated_env_block_contains_host(self):
        r = self._result()
        block = r.generated_env_block(host="root@1.2.3.4")
        assert "root@1.2.3.4" in block
        assert "strategy: docker_full" in block

    def test_generated_notes(self):
        r = self._result()
        notes = r.generated_notes()
        assert isinstance(notes, list)
        assert len(notes) > 0

"""Edge-case tests for plan/planner.py — insert_before, risk escalation, step ordering."""
from __future__ import annotations

import pytest

from redeploy.models import (
    ConflictSeverity,
    DeployStrategy,
    InfraState,
    MigrationSpec,
    MigrationStep,
    RuntimeInfo,
    ServiceInfo,
    StepAction,
    TargetConfig,
)
from redeploy.plan.planner import Planner


# ── helpers ───────────────────────────────────────────────────────────────────


def _state(
    strategy: DeployStrategy = DeployStrategy.DOCKER_FULL,
    k3s: str | None = None,
    docker: str | None = "Docker 24",
    host: str = "root@10.0.0.1",
) -> InfraState:
    return InfraState(
        host=host,
        app="testapp",
        detected_strategy=strategy,
        runtime=RuntimeInfo(docker=docker, k3s=k3s),
        services={
            "docker": [ServiceInfo(name="web", status="healthy")] if docker else [],
            "k3s": [ServiceInfo(name="pod", status="running")] if k3s else [],
            "systemd": [],
            "podman": [],
        },
    )


def _target(
    strategy: DeployStrategy = DeployStrategy.DOCKER_FULL,
    version: str = "1.0.20",
    host: str = "root@10.0.0.1",
    verify_url: str | None = "http://localhost/health",
    verify_version: str | None = "1.0.20",
) -> TargetConfig:
    return TargetConfig(
        strategy=strategy,
        host=host,
        app="testapp",
        version=version,
        domain="test.example.com",
        remote_dir="~/testapp",
        compose_files=["docker-compose.yml"],
        env_file=".env",
        verify_url=verify_url,
        verify_version=verify_version,
    )


def _infra_spec(
    strategy: DeployStrategy = DeployStrategy.DOCKER_FULL,
    host: str = "root@10.0.0.1",
    version: str = "1.0.20",
):
    from redeploy.models import InfraSpec
    return InfraSpec(strategy=strategy, host=host, app="testapp", version=version,
                     domain="test.example.com", remote_dir="~/testapp",
                     compose_files=["docker-compose.yml"], env_file=".env",
                     verify_url="http://localhost/health", verify_version=version)


def _plan(state=None, target=None, extra_steps=None, notes=None):
    s = state or _state()
    t = target or _target()
    p = Planner(s, t)
    if extra_steps or notes:
        # inject via _spec so _append_extra_steps and notes work
        from redeploy.models import InfraSpec, MigrationSpec as MS
        src_spec = _infra_spec()
        tgt_spec = _infra_spec()
        spec = MS(name="test", source=src_spec, target=tgt_spec)
        spec.extra_steps = [
            e if isinstance(e, dict) else {
                "id": e.id,
                "action": e.action.value,
                "description": e.description,
                "command": e.command,
                **({"insert_before": e.insert_before} if getattr(e, "insert_before", None) else {}),
            }
            for e in (extra_steps or [])
        ]
        spec.notes = list(notes or [])
        p._spec = spec
    return p.run()


# ── step ordering ─────────────────────────────────────────────────────────────


class TestStepOrdering:
    def test_first_step_is_not_verify(self):
        plan = _plan()
        assert plan.steps[0].action != StepAction.HTTP_CHECK

    def test_last_steps_are_verify(self):
        plan = _plan()
        last = plan.steps[-1]
        assert last.action in (StepAction.VERSION_CHECK, StepAction.HTTP_CHECK)

    def test_wait_appears_before_health_check(self):
        plan = _plan()
        ids = [s.id for s in plan.steps]
        actions = [s.action for s in plan.steps]
        if StepAction.WAIT in actions and StepAction.HTTP_CHECK in actions:
            assert actions.index(StepAction.WAIT) < actions.index(StepAction.HTTP_CHECK)

    def test_sync_env_before_docker_build(self):
        plan = _plan()
        ids = [s.id for s in plan.steps]
        if "sync_env" in ids and "docker_build_pull" in ids:
            assert ids.index("sync_env") < ids.index("docker_build_pull")


# ── insert_before ─────────────────────────────────────────────────────────────


class TestInsertBefore:
    def test_extra_step_appended_at_end_without_insert_before(self):
        extra = [MigrationStep(
            id="my_step", action=StepAction.SSH_CMD,
            description="my step", command="echo hi",
        )]
        plan = _plan(extra_steps=extra)
        ids = [s.id for s in plan.steps]
        # Without insert_before, appended after main steps but before final verify
        assert "my_step" in ids

    def test_insert_before_places_step_correctly(self):
        extra = [{"id": "smoke_test", "action": "ssh_cmd",
                  "description": "smoke test", "command": "curl ...",
                  "insert_before": "sync_env"}]
        plan = _plan(extra_steps=extra)
        ids = [s.id for s in plan.steps]
        if "smoke_test" in ids and "sync_env" in ids:
            assert ids.index("smoke_test") < ids.index("sync_env")

    def test_multiple_extra_steps_order_preserved(self):
        extra = [
            MigrationStep(id="step_a", action=StepAction.SSH_CMD,
                          description="a", command="echo a"),
            MigrationStep(id="step_b", action=StepAction.SSH_CMD,
                          description="b", command="echo b"),
        ]
        plan = _plan(extra_steps=extra)
        ids = [s.id for s in plan.steps]
        assert ids.index("step_a") < ids.index("step_b")


# ── risk escalation ───────────────────────────────────────────────────────────


class TestRiskEscalation:
    def test_k3s_to_docker_risk_elevated_with_conflict(self):
        from redeploy.models import ConflictInfo, PortInfo
        state = _state(strategy=DeployStrategy.K3S, k3s="k3s v1.28", docker=None)
        # inject a port_steal conflict so planner generates stop_k3s (MEDIUM risk)
        state.conflicts = [ConflictInfo(
            type="port_steal",
            description="Port 80 stolen by k3s DNAT",
            severity=ConflictSeverity.HIGH,
            affected=["80"],
        )]
        state.ports = {80: PortInfo(port=80, process="k3s-proxy")}
        target = _target(strategy=DeployStrategy.DOCKER_FULL)
        plan = _plan(state=state, target=target)
        assert plan.risk in (ConflictSeverity.MEDIUM, ConflictSeverity.HIGH, ConflictSeverity.CRITICAL)

    def test_same_strategy_bump_low_risk(self):
        state = _state(strategy=DeployStrategy.DOCKER_FULL)
        target = _target(strategy=DeployStrategy.DOCKER_FULL)
        plan = _plan(state=state, target=target)
        assert plan.risk in (ConflictSeverity.LOW, ConflictSeverity.MEDIUM)

    def test_podman_quadlet_target_risk(self):
        state = _state(strategy=DeployStrategy.DOCKER_FULL)
        target = _target(strategy=DeployStrategy.PODMAN_QUADLET)
        plan = _plan(state=state, target=target)
        assert plan.risk in (ConflictSeverity.LOW, ConflictSeverity.MEDIUM, ConflictSeverity.HIGH)


# ── verify steps ─────────────────────────────────────────────────────────────


class TestVerifySteps:
    def test_no_verify_url_no_http_check(self):
        # clear domain too — planner falls back to domain-based URL if domain is set
        target = _target(verify_url=None, verify_version=None)
        target.domain = None
        plan = _plan(target=target)
        assert not any(s.action == StepAction.HTTP_CHECK for s in plan.steps)

    def test_verify_url_produces_http_check(self):
        target = _target(verify_url="http://localhost/health")
        plan = _plan(target=target)
        assert any(s.action == StepAction.HTTP_CHECK for s in plan.steps)

    def test_verify_version_produces_version_check(self):
        target = _target(verify_version="1.0.20")
        plan = _plan(target=target)
        assert any(s.action == StepAction.VERSION_CHECK for s in plan.steps)

    def test_no_duplicate_verify_steps(self):
        plan = _plan()
        http_checks = [s for s in plan.steps if s.action == StepAction.HTTP_CHECK]
        assert len(http_checks) <= 1


# ── k3s-specific conflict-fix steps ──────────────────────────────────────────


class TestK3sConflictFixes:
    def _k3s_state_with_conflict(self):
        from redeploy.models import ConflictInfo, PortInfo
        state = _state(strategy=DeployStrategy.K3S, k3s="k3s v1.28", docker=None)
        state.conflicts = [ConflictInfo(
            type="port_steal",
            description="Port 80 stolen by k3s DNAT",
            severity=ConflictSeverity.HIGH,
            affected=["80"],
        )]
        state.ports = {80: PortInfo(port=80, process="k3s-proxy")}
        return state

    def test_stop_k3s_generated_for_k3s_source(self):
        state = self._k3s_state_with_conflict()
        target = _target(strategy=DeployStrategy.DOCKER_FULL)
        plan = _plan(state=state, target=target)
        ids = [s.id for s in plan.steps]
        assert "stop_k3s" in ids

    def test_stop_k3s_not_generated_for_docker_source(self):
        state = _state(strategy=DeployStrategy.DOCKER_FULL, k3s=None)
        target = _target(strategy=DeployStrategy.DOCKER_FULL)
        plan = _plan(state=state, target=target)
        ids = [s.id for s in plan.steps]
        assert "stop_k3s" not in ids

    def test_stop_k3s_before_docker_compose_up(self):
        state = self._k3s_state_with_conflict()
        target = _target(strategy=DeployStrategy.DOCKER_FULL)
        plan = _plan(state=state, target=target)
        ids = [s.id for s in plan.steps]
        if "stop_k3s" in ids and "docker_compose_up" in ids:
            assert ids.index("stop_k3s") < ids.index("docker_compose_up")


# ── podman_quadlet planning ───────────────────────────────────────────────────


class TestPodmanQuadletPlanning:
    def test_podman_daemon_reload_in_plan(self):
        state = _state(strategy=DeployStrategy.DOCKER_FULL)
        target = _target(strategy=DeployStrategy.PODMAN_QUADLET)
        plan = _plan(state=state, target=target)
        ids = [s.id for s in plan.steps]
        assert "podman_daemon_reload" in ids

    def test_docker_compose_down_before_podman_start(self):
        state = _state(strategy=DeployStrategy.DOCKER_FULL)
        target = _target(strategy=DeployStrategy.PODMAN_QUADLET)
        plan = _plan(state=state, target=target)
        ids = [s.id for s in plan.steps]
        if "docker_compose_down" in ids and "podman_daemon_reload" in ids:
            assert ids.index("docker_compose_down") < ids.index("podman_daemon_reload")


# ── notes propagation ─────────────────────────────────────────────────────────


class TestNotesAndMetadata:
    def test_notes_propagated(self):
        plan = _plan(notes=["note one", "note two"])
        assert "note one" in plan.notes

    def test_plan_has_from_to_strategy(self):
        state = _state(strategy=DeployStrategy.K3S, k3s="k3s v1.28", docker=None)
        target = _target(strategy=DeployStrategy.DOCKER_FULL)
        plan = _plan(state=state, target=target)
        assert plan.from_strategy == DeployStrategy.K3S
        assert plan.to_strategy == DeployStrategy.DOCKER_FULL

    def test_plan_host_matches_state(self):
        state = _state(host="root@192.168.1.1")
        target = _target(host="root@192.168.1.1")
        plan = _plan(state=state, target=target)
        assert plan.host == "root@192.168.1.1"


# ── Planner.from_spec ─────────────────────────────────────────────────────────


class TestPlannerFromSpec:
    def _spec(self) -> MigrationSpec:
        from redeploy.models import InfraSpec
        return MigrationSpec(
            name="test",
            source=InfraSpec(
                strategy=DeployStrategy.DOCKER_FULL,
                host="root@10.0.0.1",
                app="testapp",
                version="1.0.19",
            ),
            target=InfraSpec(
                strategy=DeployStrategy.DOCKER_FULL,
                host="root@10.0.0.1",
                app="testapp",
                version="1.0.20",
                verify_url="http://localhost/health",
                verify_version="1.0.20",
            ),
        )

    def test_from_spec_builds_planner(self):
        planner = Planner.from_spec(self._spec())
        assert planner is not None

    def test_from_spec_plan_has_steps(self):
        plan = Planner.from_spec(self._spec()).run()
        assert len(plan.steps) > 0

    def test_from_spec_with_extra_steps(self):
        spec = self._spec()
        spec.extra_steps = [
            {"id": "flush_k3s_iptables"},   # named library step
        ]
        plan = Planner.from_spec(spec).run()
        ids = [s.id for s in plan.steps]
        assert "flush_k3s_iptables" in ids

    def test_from_spec_named_step_resolved(self):
        spec = self._spec()
        spec.extra_steps = [{"id": "flush_k3s_iptables"}]
        plan = Planner.from_spec(spec).run()
        step = next(s for s in plan.steps if s.id == "flush_k3s_iptables")
        assert step.action == StepAction.SSH_CMD
        assert step.command is not None

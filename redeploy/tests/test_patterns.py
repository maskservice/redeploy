"""Tests for redeploy.patterns — BlueGreenPattern, CanaryPattern, RollbackOnFailurePattern."""
from __future__ import annotations

import pytest

import redeploy
from redeploy.patterns import (
    BlueGreenPattern,
    CanaryPattern,
    RollbackOnFailurePattern,
    get_pattern,
    list_patterns,
    pattern_registry,
)
from redeploy.models import StepAction, StepStatus


# ── registry ──────────────────────────────────────────────────────────────────


def test_list_patterns():
    names = list_patterns()
    assert "blue_green" in names
    assert "canary" in names
    assert "rollback_on_failure" in names


def test_get_pattern_known():
    cls = get_pattern("blue_green")
    assert cls is BlueGreenPattern


def test_get_pattern_unknown():
    assert get_pattern("nonexistent") is None


def test_pattern_registry_keys():
    assert set(pattern_registry.keys()) == {"blue_green", "canary", "rollback_on_failure"}


# ── BlueGreenPattern ──────────────────────────────────────────────────────────


class TestBlueGreen:
    def _pattern(self, **kw):
        return BlueGreenPattern(
            app="myapp", remote_dir="~/myapp",
            verify_url="http://localhost:8080",
            **kw,
        )

    def test_expand_returns_steps(self):
        steps = self._pattern().expand()
        assert len(steps) > 0

    def test_step_ids_present(self):
        ids = [s.id for s in self._pattern().expand()]
        assert "bg_clone_green" in ids
        assert "bg_deploy_green" in ids
        assert "bg_health_green" in ids
        assert "bg_swap_labels" in ids
        assert "bg_verify_main" in ids
        assert "bg_retire_blue" in ids

    def test_with_env_file_adds_scp_step(self):
        steps = self._pattern(env_file=".env").expand()
        ids = [s.id for s in steps]
        assert "bg_sync_env" in ids
        scp = next(s for s in steps if s.id == "bg_sync_env")
        assert scp.action == StepAction.SCP

    def test_without_env_file_no_scp(self):
        steps = self._pattern().expand()
        ids = [s.id for s in steps]
        assert "bg_sync_env" not in ids

    def test_green_dir_suffix(self):
        p = self._pattern(green_suffix="-green")
        steps = p.expand()
        clone = next(s for s in steps if s.id == "bg_clone_green")
        assert "~/myapp-green" in clone.command

    def test_swap_step_has_rollback(self):
        steps = self._pattern().expand()
        swap = next(s for s in steps if s.id == "bg_swap_labels")
        assert swap.rollback_command is not None
        assert "~/myapp" in swap.rollback_command

    def test_deploy_step_timeout(self):
        steps = self._pattern().expand()
        deploy = next(s for s in steps if s.id == "bg_deploy_green")
        assert deploy.timeout == 1800

    def test_all_steps_pending(self):
        for step in self._pattern().expand():
            assert step.status == StepStatus.PENDING

    def test_repr(self):
        p = self._pattern()
        assert "myapp" in repr(p)


# ── CanaryPattern ─────────────────────────────────────────────────────────────


class TestCanary:
    def _pattern(self, **kw):
        return CanaryPattern(
            app="myapp", remote_dir="~/myapp",
            verify_url="http://localhost:8080",
            **kw,
        )

    def test_expand_returns_steps(self):
        steps = self._pattern().expand()
        assert len(steps) > 0

    def test_default_stages(self):
        p = self._pattern()
        assert p.stages == [10, 25, 50, 100]

    def test_health_check_per_stage(self):
        steps = self._pattern(stages=[10, 100]).expand()
        ids = [s.id for s in steps]
        assert "canary_health_10pct" in ids
        assert "canary_health_100pct" in ids

    def test_wait_between_stages(self):
        steps = self._pattern(stages=[10, 100], stage_wait_seconds=15).expand()
        ids = [s.id for s in steps]
        assert "canary_wait_10pct" in ids
        assert "canary_wait_100pct" not in ids  # no wait after final stage

    def test_no_wait_when_zero(self):
        steps = self._pattern(stages=[10, 50, 100], stage_wait_seconds=0).expand()
        ids = [s.id for s in steps]
        assert not any("wait" in i for i in ids)

    def test_promote_step_present(self):
        steps = self._pattern().expand()
        ids = [s.id for s in steps]
        assert "canary_promote" in ids

    def test_promote_has_rollback(self):
        steps = self._pattern().expand()
        promote = next(s for s in steps if s.id == "canary_promote")
        assert promote.rollback_command is not None

    def test_canary_clone_step(self):
        steps = self._pattern().expand()
        clone = next(s for s in steps if s.id == "canary_clone")
        assert "~/myapp-canary" in clone.command

    def test_custom_suffix(self):
        steps = self._pattern(canary_suffix="-v2").expand()
        clone = next(s for s in steps if s.id == "canary_clone")
        assert "~/myapp-v2" in clone.command

    def test_retire_old_step(self):
        ids = [s.id for s in self._pattern().expand()]
        assert "canary_retire_old" in ids


# ── RollbackOnFailurePattern ──────────────────────────────────────────────────


class TestRollbackOnFailure:
    def _pattern(self, **kw):
        return RollbackOnFailurePattern(
            app="myapp", remote_dir="~/myapp",
            verify_url="http://localhost:8080",
            **kw,
        )

    def test_expand_returns_steps(self):
        assert len(self._pattern().expand()) > 0

    def test_step_ids(self):
        ids = [s.id for s in self._pattern().expand()]
        assert "rob_snapshot" in ids
        assert "rob_deploy" in ids
        assert "rob_health" in ids
        assert "rob_cleanup_snapshot" in ids

    def test_snapshot_step_tees_to_file(self):
        steps = self._pattern().expand()
        snap = next(s for s in steps if s.id == "rob_snapshot")
        assert ".deploy-snapshot" in snap.command

    def test_custom_snapshot_file(self):
        steps = self._pattern(snapshot_file=".snap").expand()
        snap = next(s for s in steps if s.id == "rob_snapshot")
        assert ".snap" in snap.command

    def test_deploy_step_has_rollback(self):
        steps = self._pattern().expand()
        deploy = next(s for s in steps if s.id == "rob_deploy")
        assert deploy.rollback_command is not None

    def test_cleanup_is_last(self):
        steps = self._pattern().expand()
        assert steps[-1].id == "rob_cleanup_snapshot"


# ── Planner integration ───────────────────────────────────────────────────────


class TestPlannerPatternIntegration:
    def _make_state(self):
        from redeploy.models import InfraState, RuntimeInfo, DeployStrategy
        return InfraState(
            host="root@10.0.0.1", app="myapp",
            runtime=RuntimeInfo(docker="24.0"),
            detected_strategy=DeployStrategy.DOCKER_FULL,
        )

    def test_blue_green_via_planner(self):
        state = self._make_state()
        target = redeploy.TargetConfig(
            strategy="docker_full", app="myapp",
            remote_dir="~/myapp", pattern="blue_green",
            verify_url="http://localhost:8080",
        )
        plan = redeploy.Planner(state, target).run()
        ids = [s.id for s in plan.steps]
        assert "bg_clone_green" in ids
        assert "bg_deploy_green" in ids
        assert "bg_retire_blue" in ids
        assert any("Deploy pattern: blue_green" in n for n in plan.notes)

    def test_canary_via_planner(self):
        state = self._make_state()
        target = redeploy.TargetConfig(
            strategy="docker_full", app="myapp",
            remote_dir="~/myapp", pattern="canary",
            verify_url="http://localhost:8080",
        )
        plan = redeploy.Planner(state, target).run()
        ids = [s.id for s in plan.steps]
        assert "canary_clone" in ids
        assert "canary_promote" in ids

    def test_rollback_pattern_via_planner(self):
        state = self._make_state()
        target = redeploy.TargetConfig(
            strategy="docker_full", app="myapp",
            remote_dir="~/myapp", pattern="rollback_on_failure",
            verify_url="http://localhost:8080",
        )
        plan = redeploy.Planner(state, target).run()
        ids = [s.id for s in plan.steps]
        assert "rob_snapshot" in ids
        assert "rob_deploy" in ids

    def test_unknown_pattern_falls_back(self):
        state = self._make_state()
        target = redeploy.TargetConfig(
            strategy="docker_full", app="myapp",
            remote_dir="~/myapp", pattern="does_not_exist",
        )
        plan = redeploy.Planner(state, target).run()
        assert any("Unknown pattern" in n for n in plan.notes)
        assert any("docker_compose_up" == s.id or "docker_build_pull" == s.id
                   for s in plan.steps)

    def test_no_pattern_uses_standard_deploy(self):
        state = self._make_state()
        target = redeploy.TargetConfig(
            strategy="docker_full", app="myapp", remote_dir="~/myapp",
        )
        plan = redeploy.Planner(state, target).run()
        ids = [s.id for s in plan.steps]
        assert "docker_build_pull" in ids
        assert "docker_compose_up" in ids

    def test_pattern_config_passed_through(self):
        state = self._make_state()
        target = redeploy.TargetConfig(
            strategy="docker_full", app="myapp",
            remote_dir="~/myapp", pattern="blue_green",
            pattern_config={"traefik_network": "my_net"},
            verify_url="http://localhost:8080",
        )
        plan = redeploy.Planner(state, target).run()
        swap = next((s for s in plan.steps if s.id == "bg_swap_labels"), None)
        assert swap is not None
        assert "my_net" in swap.command

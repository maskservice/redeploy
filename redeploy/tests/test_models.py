"""Unit tests for models and planner logic (no SSH required)."""
from __future__ import annotations

import pytest

from redeploy.models import (
    ConflictInfo, ConflictSeverity, DeployStrategy, InfraState,
    MigrationStep, RuntimeInfo, ServiceInfo, StepAction, TargetConfig,
)
from redeploy.plan.planner import Planner


def _make_state(
    strategy: DeployStrategy = DeployStrategy.K3S,
    conflicts: list[ConflictInfo] | None = None,
    k3s: bool = True,
    docker: bool = True,
) -> InfraState:
    return InfraState(
        host="root@1.2.3.4",
        app="c2004",
        runtime=RuntimeInfo(
            docker="Docker version 27.0" if docker else None,
            k3s="k3s version v1.31" if k3s else None,
        ),
        services={
            "docker": [ServiceInfo(name="c2004-backend", status="healthy")] if docker else [],
            "k3s": [ServiceInfo(name="backend", namespace="c2004")] if k3s else [],
            "systemd": [],
            "podman": [],
        },
        conflicts=conflicts or [],
        detected_strategy=strategy,
    )


def test_plan_k3s_to_docker_generates_stop_k3s():
    state = _make_state(
        strategy=DeployStrategy.K3S,
        conflicts=[ConflictInfo(
            type="dual_runtime",
            description="k3s and Docker both running",
            severity=ConflictSeverity.HIGH,
        )],
    )
    target = TargetConfig(
        strategy=DeployStrategy.DOCKER_FULL,
        compose_files=["docker-compose.vps.yml"],
        domain="c2004.mask.services",
        verify_version="1.0.19",
    )
    planner = Planner(state, target)
    migration = planner.run()

    step_ids = [s.id for s in migration.steps]
    assert "stop_k3s" in step_ids, "Must stop k3s when migrating away from it"
    assert "disable_k3s" in step_ids
    assert "docker_compose_up" in step_ids
    assert "version_check" in step_ids


def test_plan_no_conflicts_no_stop_k3s():
    state = _make_state(strategy=DeployStrategy.DOCKER_FULL, k3s=False)
    target = TargetConfig(strategy=DeployStrategy.DOCKER_FULL, domain="c2004.mask.services")
    planner = Planner(state, target)
    migration = planner.run()

    step_ids = [s.id for s in migration.steps]
    assert "stop_k3s" not in step_ids


def test_plan_risk_elevated_when_stop_steps():
    state = _make_state(
        conflicts=[ConflictInfo(
            type="port_steal", description="k3s DNAT",
            severity=ConflictSeverity.HIGH,
        )],
    )
    target = TargetConfig(strategy=DeployStrategy.DOCKER_FULL)
    migration = Planner(state, target).run()
    assert migration.risk in (ConflictSeverity.MEDIUM, ConflictSeverity.HIGH)


def test_plan_downtime_includes_wait():
    state = _make_state(k3s=False, docker=True, strategy=DeployStrategy.DOCKER_FULL)
    target = TargetConfig(strategy=DeployStrategy.DOCKER_FULL, domain="x.example.com")
    migration = Planner(state, target).run()
    # wait step contributes to downtime estimate
    assert "s" in migration.estimated_downtime


def test_infra_state_serializes():
    state = _make_state()
    data = state.model_dump(mode="json")
    restored = InfraState(**data)
    assert restored.host == state.host
    assert restored.detected_strategy == state.detected_strategy


def test_migration_plan_step_count_sane():
    state = _make_state(
        strategy=DeployStrategy.K3S,
        conflicts=[ConflictInfo(
            type="dual_runtime", description="k3s+docker",
            severity=ConflictSeverity.HIGH,
        )],
    )
    target = TargetConfig(
        strategy=DeployStrategy.DOCKER_FULL,
        compose_files=["docker-compose.vps.yml"],
        env_file="envs/vps.env",
        domain="c2004.mask.services",
        verify_version="1.0.19",
    )
    migration = Planner(state, target).run()
    assert len(migration.steps) >= 4   # delete_ingress, stop, disable, compose_up, verify
    # No duplicate step IDs
    ids = [s.id for s in migration.steps]
    assert len(ids) == len(set(ids)), "Duplicate step IDs"

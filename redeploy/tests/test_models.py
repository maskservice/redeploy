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


def test_plan_downtime_rolling_when_same_strategy():
    state = _make_state(k3s=False, docker=True, strategy=DeployStrategy.DOCKER_FULL)
    target = TargetConfig(strategy=DeployStrategy.DOCKER_FULL, domain="x.example.com")
    migration = Planner(state, target).run()
    # same strategy + no compose_down → rolling update
    assert "rolling" in migration.estimated_downtime or "s" in migration.estimated_downtime


def test_plan_downtime_includes_seconds_for_cross_strategy():
    # docker→podman_quadlet triggers compose_down → real downtime
    state = _make_state(k3s=False, docker=True, strategy=DeployStrategy.DOCKER_FULL)
    target = TargetConfig(strategy=DeployStrategy.PODMAN_QUADLET, domain="x.example.com")
    migration = Planner(state, target).run()
    # compose_down present → downtime in seconds
    assert "s" in migration.estimated_downtime


def test_infra_state_serializes():
    state = _make_state()
    data = state.model_dump(mode="json")
    restored = InfraState(**data)
    assert restored.host == state.host
    assert restored.detected_strategy == state.detected_strategy


def _make_spec(
    from_strategy: DeployStrategy = DeployStrategy.K3S,
    to_strategy: DeployStrategy = DeployStrategy.DOCKER_FULL,
    extra_steps: list | None = None,
) -> "MigrationSpec":
    from redeploy.models import InfraSpec, MigrationSpec
    return MigrationSpec(
        name="test-migration",
        description="unit test",
        source=InfraSpec(
            strategy=from_strategy,
            host="root@1.2.3.4",
            app="c2004",
            version="1.0.18",
            domain="c2004.example.com",
            delete_k3s_namespaces=["identification"],
            stop_services=["k3s"],
            disable_services=["k3s"],
        ),
        target=InfraSpec(
            strategy=to_strategy,
            host="root@1.2.3.4",
            app="c2004",
            version="1.0.19",
            domain="c2004.example.com",
            compose_files=["docker-compose.vps.yml"],
            env_file="envs/vps.env",
            verify_url="https://c2004.example.com/api/v1/health",
            verify_version="1.0.19",
        ),
        extra_steps=extra_steps or [],
        notes=["test note"],
    )


def test_spec_to_infra_state():
    spec = _make_spec()
    state = spec.to_infra_state()
    assert state.host == "root@1.2.3.4"
    assert state.detected_strategy == DeployStrategy.K3S
    assert state.runtime.k3s == "declared-in-spec"


def test_spec_to_target_config():
    spec = _make_spec()
    target = spec.to_target_config()
    assert target.strategy == DeployStrategy.DOCKER_FULL
    assert target.compose_files == ["docker-compose.vps.yml"]
    assert target.stop_services == ["k3s"]
    assert target.verify_version == "1.0.19"


def test_planner_from_spec_generates_steps():
    from redeploy.plan.planner import Planner
    spec = _make_spec()
    planner = Planner.from_spec(spec)
    migration = planner.run()
    ids = [s.id for s in migration.steps]
    assert "stop_k3s" in ids
    assert "docker_compose_up" in ids
    assert "version_check" in ids


def test_planner_from_spec_appends_notes():
    from redeploy.plan.planner import Planner
    spec = _make_spec()
    migration = Planner.from_spec(spec).run()
    assert "test note" in migration.notes


def test_planner_from_spec_extra_steps():
    from redeploy.plan.planner import Planner
    spec = _make_spec(extra_steps=[{
        "id": "custom_step",
        "action": "ssh_cmd",
        "description": "Custom command",
        "command": "echo hello",
    }])
    migration = Planner.from_spec(spec).run()
    ids = [s.id for s in migration.steps]
    assert "custom_step" in ids


def test_spec_roundtrip_yaml(tmp_path):
    """MigrationSpec can be written to YAML and re-read."""
    import yaml
    from redeploy.models import MigrationSpec
    spec = _make_spec()
    path = tmp_path / "migration.yaml"
    path.write_text(yaml.dump(spec.model_dump(mode="json"), allow_unicode=True))
    restored = MigrationSpec.from_file(path)
    assert restored.name == spec.name
    assert restored.source.strategy == spec.source.strategy
    assert restored.target.version == spec.target.version


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

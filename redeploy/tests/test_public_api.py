"""Smoke tests for the public API — all names in __all__ must be importable
and functional. These tests guard against accidental removal or rename.
"""
from __future__ import annotations

import redeploy


# ── __all__ completeness ──────────────────────────────────────────────────────


def test_all_names_importable():
    for name in redeploy.__all__:
        assert hasattr(redeploy, name), f"redeploy.{name} missing from package"


def test_version_string():
    assert isinstance(redeploy.__version__, str)
    parts = redeploy.__version__.split(".")
    assert len(parts) >= 2
    assert parts[0] == "0"
    assert int(parts[1]) >= 2


# ── Core models ────────────────────────────────────────────────────────────────


def test_deploy_strategy_values():
    DS = redeploy.DeployStrategy
    assert DS.DOCKER_FULL.value == "docker_full"
    assert DS.PODMAN_QUADLET.value == "podman_quadlet"
    assert DS.KIOSK_APPLIANCE.value == "kiosk_appliance"
    assert DS.K3S.value == "k3s"
    assert DS.SYSTEMD.value == "systemd"
    assert DS.UNKNOWN.value == "unknown"


def test_step_action_values():
    SA = redeploy.StepAction
    assert SA.SSH_CMD.value == "ssh_cmd"
    assert SA.HTTP_CHECK.value == "http_check"
    assert SA.RSYNC.value == "rsync"
    assert SA.WAIT.value == "wait"


def test_step_status_values():
    SS = redeploy.StepStatus
    assert SS.PENDING.value == "pending"
    assert SS.DONE.value == "done"
    assert SS.FAILED.value == "failed"


def test_conflict_severity_values():
    CS = redeploy.ConflictSeverity
    assert CS.LOW.value == "low"
    assert CS.CRITICAL.value == "critical"


def test_migration_step_construct():
    step = redeploy.MigrationStep(
        id="test", action=redeploy.StepAction.SSH_CMD,
        description="echo hello", command="echo hello",
        risk=redeploy.ConflictSeverity.LOW,
    )
    assert step.id == "test"
    assert step.status == redeploy.StepStatus.PENDING


def test_target_config_defaults():
    t = redeploy.TargetConfig()
    assert t.strategy == redeploy.DeployStrategy.DOCKER_FULL
    assert t.app == ""
    assert t.remote_dir == ""


def test_target_config_strategy_alias_docker_compose():
    t = redeploy.TargetConfig(strategy="docker-compose")
    assert t.strategy == redeploy.DeployStrategy.DOCKER_FULL


def test_target_config_strategy_alias_kiosk_appliance():
    t = redeploy.TargetConfig(strategy="kiosk-appliance")
    assert t.strategy == redeploy.DeployStrategy.KIOSK_APPLIANCE


def test_target_config_strategy_alias_quadlet():
    t = redeploy.TargetConfig(strategy="quadlet")
    assert t.strategy == redeploy.DeployStrategy.PODMAN_QUADLET


def test_target_config_strategy_alias_kubernetes():
    t = redeploy.TargetConfig(strategy="kubernetes")
    assert t.strategy == redeploy.DeployStrategy.K3S


def test_target_config_strategy_alias_k8s():
    t = redeploy.TargetConfig(strategy="k8s")
    assert t.strategy == redeploy.DeployStrategy.K3S


def test_target_config_strategy_canonical_passthrough():
    t = redeploy.TargetConfig(strategy="docker_full")
    assert t.strategy == redeploy.DeployStrategy.DOCKER_FULL


def test_infra_state_construct():
    state = redeploy.InfraState(
        host="root@1.2.3.4", app="myapp",
        detected_strategy=redeploy.DeployStrategy.DOCKER_FULL,
    )
    assert state.host == "root@1.2.3.4"
    assert state.detected_strategy == redeploy.DeployStrategy.DOCKER_FULL


def test_migration_plan_construct():
    plan = redeploy.MigrationPlan(
        host="local", app="myapp",
        from_strategy=redeploy.DeployStrategy.K3S,
        to_strategy=redeploy.DeployStrategy.DOCKER_FULL,
    )
    assert plan.host == "local"
    assert plan.steps == []


# ── Pipeline classes importable and instantiable ───────────────────────────────


def test_planner_importable():
    assert callable(redeploy.Planner)


def test_executor_importable():
    assert callable(redeploy.Executor)


def test_detector_importable():
    assert callable(redeploy.Detector)


def test_ssh_client_local():
    client = redeploy.SshClient("local")
    r = client.run("echo ok")
    assert r.ok
    assert r.out == "ok"


def test_ssh_result_ok():
    r = redeploy.SshResult(0, "out", "")
    assert r.ok
    assert r.out == "out"


def test_ssh_result_fail():
    r = redeploy.SshResult(1, "", "err")
    assert not r.ok


# ── Fleet / registry ──────────────────────────────────────────────────────────


def test_device_registry_empty():
    reg = redeploy.DeviceRegistry()
    assert reg.devices == []
    assert reg.get("nonexistent") is None


def test_known_device_construct():
    d = redeploy.KnownDevice(id="pi1", host="pi@192.168.1.5", tags=["kiosk"])
    assert d.id == "pi1"
    assert "kiosk" in d.tags


def test_fleet_config_importable():
    assert callable(redeploy.FleetConfig)


def test_step_library_importable():
    assert callable(redeploy.StepLibrary.get)
    ids = redeploy.StepLibrary.list()
    assert len(ids) > 5


# ── Planner + KIOSK_APPLIANCE ─────────────────────────────────────────────────


def test_planner_kiosk_appliance_generates_steps():
    from redeploy.models import RuntimeInfo, InfraState
    state = InfraState(
        host="pi@192.168.1.5", app="kiosk-station",
        runtime=RuntimeInfo(),
        detected_strategy=redeploy.DeployStrategy.NATIVE_KIOSK,
    )
    target = redeploy.TargetConfig(
        strategy="kiosk-appliance",   # alias
        app="kiosk-station",
        remote_dir="~/kiosk-station",
        verify_url="http://localhost:8080",
    )
    plan = redeploy.Planner(state, target).run()
    step_ids = [s.id for s in plan.steps]
    assert "sync_build" in step_ids
    assert "run_kiosk_installer" in step_ids
    assert "install_kiosk_service" in step_ids
    assert "enable_kiosk_service" in step_ids
    assert "wait_kiosk_start" in step_ids
    assert "http_health_check" in step_ids


def test_planner_docker_compose_alias():
    from redeploy.models import RuntimeInfo, InfraState
    state = InfraState(
        host="local", app="myapp",
        runtime=RuntimeInfo(docker="24.0"),
        detected_strategy=redeploy.DeployStrategy.DOCKER_FULL,
    )
    target = redeploy.TargetConfig(strategy="docker-compose", app="myapp")
    plan = redeploy.Planner(state, target).run()
    assert plan.to_strategy == redeploy.DeployStrategy.DOCKER_FULL

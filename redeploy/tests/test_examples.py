"""Tests that parse and validate all examples/ scenarios.

Each migration.yaml is parsed through the full detect→plan pipeline
(without actual SSH). fleet.yaml files are parsed via FleetConfig.from_file().
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from redeploy.fleet import FleetConfig, Stage, DeviceExpectation
from redeploy.models import MigrationSpec, DeployStrategy, StepAction
from redeploy.plan.planner import Planner
from redeploy.steps import StepLibrary

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"

MIGRATION_YAMLS = sorted(EXAMPLES_DIR.glob("*/migration.yaml"))
FLEET_YAMLS = sorted(EXAMPLES_DIR.glob("*/fleet.yaml"))


# ── helpers ───────────────────────────────────────────────────────────────────


def _load_spec(path: Path) -> MigrationSpec:
    return MigrationSpec.from_file(path)


def _plan_from_spec(spec: MigrationSpec):
    planner = Planner.from_spec(spec)
    return planner.run()


# ── parametrize every migration.yaml ─────────────────────────────────────────


@pytest.mark.parametrize("yaml_path", MIGRATION_YAMLS, ids=lambda p: p.parent.name)
class TestMigrationYaml:
    def test_parses_without_error(self, yaml_path):
        spec = _load_spec(yaml_path)
        assert spec.name

    def test_has_source_and_target(self, yaml_path):
        spec = _load_spec(yaml_path)
        assert spec.source.strategy != DeployStrategy.UNKNOWN or spec.source.host
        assert spec.target.strategy is not None

    def test_plan_generates_steps(self, yaml_path):
        spec = _load_spec(yaml_path)
        plan = _plan_from_spec(spec)
        assert len(plan.steps) > 0, f"{yaml_path.parent.name}: plan has 0 steps"

    def test_plan_has_no_duplicate_step_ids(self, yaml_path):
        spec = _load_spec(yaml_path)
        plan = _plan_from_spec(spec)
        ids = [s.id for s in plan.steps]
        assert len(ids) == len(set(ids)), f"Duplicate step ids: {ids}"

    def test_all_steps_have_valid_action(self, yaml_path):
        spec = _load_spec(yaml_path)
        plan = _plan_from_spec(spec)
        valid_actions = {a.value for a in StepAction}
        for step in plan.steps:
            assert step.action.value in valid_actions, \
                f"Step '{step.id}' has invalid action: {step.action}"

    def test_has_readme(self, yaml_path):
        readme = yaml_path.parent / "README.md"
        assert readme.exists(), f"Missing README.md in {yaml_path.parent.name}"

    def test_readme_has_run_section(self, yaml_path):
        readme = yaml_path.parent / "README.md"
        content = readme.read_text()
        assert "## Run" in content or "## run" in content.lower(), \
            f"{yaml_path.parent.name}/README.md missing ## Run section"


# ── scenario-specific checks ──────────────────────────────────────────────────


class TestScenario01VpsVersionBump:
    def _spec(self):
        return _load_spec(EXAMPLES_DIR / "01-vps-version-bump" / "migration.yaml")

    def test_same_strategy(self):
        spec = self._spec()
        assert spec.source.strategy == DeployStrategy.DOCKER_FULL
        assert spec.target.strategy == DeployStrategy.DOCKER_FULL

    def test_version_bumped(self):
        spec = self._spec()
        assert spec.source.version != spec.target.version

    def test_plan_has_health_check(self):
        plan = _plan_from_spec(self._spec())
        actions = {s.action for s in plan.steps}
        assert StepAction.HTTP_CHECK in actions

    def test_plan_has_version_check(self):
        plan = _plan_from_spec(self._spec())
        actions = {s.action for s in plan.steps}
        assert StepAction.VERSION_CHECK in actions

    def test_flush_iptables_in_plan(self):
        plan = _plan_from_spec(self._spec())
        ids = [s.id for s in plan.steps]
        assert "flush_k3s_iptables" in ids

    def test_flush_iptables_resolved_from_library(self):
        plan = _plan_from_spec(self._spec())
        step = next(s for s in plan.steps if s.id == "flush_k3s_iptables")
        assert step.action == StepAction.SSH_CMD
        assert "CNI-HOSTPORT-DNAT" in step.command


class TestScenario02K3sToDocker:
    def _spec(self):
        return _load_spec(EXAMPLES_DIR / "02-k3s-to-docker" / "migration.yaml")

    def test_strategy_change(self):
        spec = self._spec()
        assert spec.source.strategy == DeployStrategy.K3S
        assert spec.target.strategy == DeployStrategy.DOCKER_FULL

    def test_plan_has_stop_k3s(self):
        plan = _plan_from_spec(self._spec())
        ids = [s.id for s in plan.steps]
        assert "stop_k3s" in ids

    def test_plan_has_disable_k3s(self):
        plan = _plan_from_spec(self._spec())
        ids = [s.id for s in plan.steps]
        assert "disable_k3s" in ids

    def test_plan_has_docker_compose_up(self):
        plan = _plan_from_spec(self._spec())
        actions = {s.action for s in plan.steps}
        assert StepAction.DOCKER_COMPOSE_UP in actions

    def test_plan_risk_is_medium_or_higher(self):
        from redeploy.models import ConflictSeverity
        plan = _plan_from_spec(self._spec())
        assert plan.risk in (ConflictSeverity.MEDIUM, ConflictSeverity.HIGH, ConflictSeverity.CRITICAL)


class TestScenario03DockerToQuadlet:
    def _spec(self):
        return _load_spec(EXAMPLES_DIR / "03-docker-to-podman-quadlet" / "migration.yaml")

    def test_strategy_change(self):
        spec = self._spec()
        assert spec.source.strategy == DeployStrategy.DOCKER_FULL
        assert spec.target.strategy == DeployStrategy.PODMAN_QUADLET

    def test_plan_has_daemon_reload(self):
        plan = _plan_from_spec(self._spec())
        ids = [s.id for s in plan.steps]
        assert "podman_daemon_reload" in ids

    def test_plan_has_wait(self):
        plan = _plan_from_spec(self._spec())
        actions = {s.action for s in plan.steps}
        assert StepAction.WAIT in actions

    def test_extra_steps_present(self):
        plan = _plan_from_spec(self._spec())
        ids = [s.id for s in plan.steps]
        assert "copy_quadlet_files" in ids or "enable_linger" in ids


class TestScenario07StagingToProd:
    def _spec(self):
        return _load_spec(EXAMPLES_DIR / "07-staging-to-prod" / "migration.yaml")

    def test_insert_before_smoke_test(self):
        plan = _plan_from_spec(self._spec())
        ids = [s.id for s in plan.steps]
        # smoke_test_staging must appear before sync_env
        if "smoke_test_staging" in ids and "sync_env" in ids:
            assert ids.index("smoke_test_staging") < ids.index("sync_env")

    def test_notify_steps_present(self):
        plan = _plan_from_spec(self._spec())
        ids = [s.id for s in plan.steps]
        assert "notify_deploy_start" in ids
        assert "notify_deploy_done" in ids


class TestScenario08Rollback:
    def _spec(self):
        return _load_spec(EXAMPLES_DIR / "08-rollback" / "migration.yaml")

    def test_version_goes_down(self):
        spec = self._spec()
        # source version > target version (rollback)
        from packaging.version import Version
        assert Version(spec.source.version) > Version(spec.target.version)

    def test_plan_has_version_check(self):
        plan = _plan_from_spec(self._spec())
        assert any(s.action == StepAction.VERSION_CHECK for s in plan.steps)


# ── fleet.yaml tests ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("yaml_path", FLEET_YAMLS, ids=lambda p: p.parent.name)
class TestFleetYaml:
    def test_parses_without_error(self, yaml_path):
        config = FleetConfig.from_file(yaml_path)
        assert len(config.devices) > 0

    def test_all_devices_have_id(self, yaml_path):
        config = FleetConfig.from_file(yaml_path)
        for d in config.devices:
            assert d.id, f"Device without id in {yaml_path}"

    def test_all_devices_have_stage(self, yaml_path):
        config = FleetConfig.from_file(yaml_path)
        for d in config.devices:
            assert d.stage in Stage, f"Invalid stage for {d.id}"

    def test_all_devices_have_expectations(self, yaml_path):
        config = FleetConfig.from_file(yaml_path)
        for d in config.devices:
            assert isinstance(d.expectations, list)


class TestScenario09FleetYaml:
    def _config(self):
        return FleetConfig.from_file(EXAMPLES_DIR / "09-fleet-yaml" / "fleet.yaml")

    def test_prod_devices_have_no_k3s_expectation(self):
        config = self._config()
        for d in config.prod_devices():
            if d.strategy == "docker_full":
                assert DeviceExpectation.NO_K3S in d.expectations, \
                    f"{d.id} (prod, docker_full) missing NO_K3S expectation"

    def test_by_tag(self):
        config = self._config()
        vps = config.by_tag("vps")
        assert len(vps) >= 1

    def test_by_stage(self):
        config = self._config()
        prod = config.by_stage(Stage.PROD)
        assert len(prod) >= 1

    def test_local_device_has_no_ssh_host(self):
        config = self._config()
        local = config.get_device("docker-local")
        assert local is not None
        assert local.is_local

    def test_iot_node_has_disk_ok_expectation(self):
        config = self._config()
        iot = config.get_device("iot-node-42")
        assert iot is not None
        assert DeviceExpectation.DISK_OK in iot.expectations

    def test_has_readme(self):
        readme = EXAMPLES_DIR / "09-fleet-yaml" / "README.md"
        assert readme.exists()


# ── StepLibrary completeness ──────────────────────────────────────────────────


class TestStepLibraryCompleteness:
    def test_all_named_steps_in_examples_are_in_library(self):
        """Every id used without 'action' in any example must be in StepLibrary."""
        missing = []
        for yaml_path in EXAMPLES_DIR.glob("*/migration.yaml"):
            with yaml_path.open() as f:
                raw = yaml.safe_load(f) or {}
            for step in raw.get("extra_steps", []):
                if "action" not in step and step.get("id"):
                    if StepLibrary.get(step["id"]) is None:
                        missing.append(f"{yaml_path.parent.name}: {step['id']}")
        assert missing == [], f"Steps used without action but not in library:\n" + "\n".join(missing)

    def test_library_step_commands_are_non_empty(self):
        for step_id, step in StepLibrary.all().items():
            if step.command is not None:
                assert step.command.strip(), f"Step '{step_id}' has empty command"

    def test_library_has_expected_ids(self):
        ids = StepLibrary.list()
        expected = [
            "flush_k3s_iptables", "stop_k3s", "disable_k3s",
            "stop_nginx", "restart_traefik", "docker_prune",
            "wait_startup", "http_health_check", "version_check", "sync_env",
        ]
        for e in expected:
            assert e in ids, f"'{e}' missing from StepLibrary"

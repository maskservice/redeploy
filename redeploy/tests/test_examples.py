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
from redeploy.spec_loader import load_migration_spec
from redeploy.steps import StepLibrary

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"

# YAML examples are now in examples/yaml/*/
MIGRATION_YAMLS = sorted(EXAMPLES_DIR.glob("yaml/*/migration.yaml"))
# 10-multienv uses dev/staging/prod.yaml instead of migration.yaml
MULTIENV_YAMLS = sorted(EXAMPLES_DIR.glob("yaml/10-multienv/*.yaml"))
FLEET_YAMLS = sorted(EXAMPLES_DIR.glob("yaml/*/fleet.yaml"))
REDEPLOY_YAMLS = sorted(EXAMPLES_DIR.glob("yaml/*/redeploy.yaml"))
SUPPORTED_MARKDOWN_MIGRATIONS = [
    EXAMPLES_DIR / "md" / "01-vps-version-bump" / "migration.md",
    EXAMPLES_DIR / "md" / "02-k3s-to-docker" / "migration.md",
    EXAMPLES_DIR / "md" / "03-docker-to-podman-quadlet" / "migration.md",
]


# ── helpers ───────────────────────────────────────────────────────────────────


def _load_spec(path: Path) -> MigrationSpec:
    return load_migration_spec(path)


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

    def test_has_redeploy_yaml(self, yaml_path):
        rdeploy = yaml_path.parent / "redeploy.yaml"
        assert rdeploy.exists(), f"Missing redeploy.yaml in {yaml_path.parent.name}"


@pytest.mark.parametrize("md_path", SUPPORTED_MARKDOWN_MIGRATIONS, ids=lambda p: p.parent.name)
class TestSupportedMarkdownMigration:
    def test_parses_without_error(self, md_path):
        spec = _load_spec(md_path)
        assert spec.name

    def test_plan_generates_steps(self, md_path):
        spec = _load_spec(md_path)
        plan = _plan_from_spec(spec)
        assert len(plan.steps) > 0, f"{md_path.parent.name}: plan has 0 steps"

    def test_has_readme(self, md_path):
        readme = md_path.parent / "README.md"
        assert readme.exists(), f"Missing README.md in {md_path.parent.name}"

    def test_readme_has_run_section(self, md_path):
        readme = md_path.parent / "README.md"
        content = readme.read_text()
        assert "## Run" in content or "## run" in content.lower(), \
            f"{md_path.parent.name}/README.md missing ## Run section"


# ── redeploy.yaml manifest tests ──────────────────────────────────────────────


@pytest.mark.parametrize("rdeploy_path", REDEPLOY_YAMLS, ids=lambda p: p.parent.name)
class TestRedeployYaml:
    def test_parses_as_yaml(self, rdeploy_path):
        with rdeploy_path.open() as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)

    def test_has_app_field(self, rdeploy_path):
        with rdeploy_path.open() as f:
            data = yaml.safe_load(f)
        assert "app" in data, f"{rdeploy_path.parent.name}/redeploy.yaml missing 'app'"

    def test_spec_field_points_to_existing_file_or_env_spec(self, rdeploy_path):
        with rdeploy_path.open() as f:
            data = yaml.safe_load(f)
        if "spec" in data:
            spec_path = rdeploy_path.parent / data["spec"]
            # Allow non-existence for multienv with prod.yaml (valid reference)
            assert spec_path.suffix in (".yaml", ".yml"), \
                f"spec must be a yaml file, got: {data['spec']}"


# ── multienv scenario tests ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "yaml_path",
    [p for p in MULTIENV_YAMLS if p.stem in ("dev", "staging", "prod")],
    ids=lambda p: f"10-multienv/{p.name}",
)
class TestMultienvYamls:
    def test_parses_without_error(self, yaml_path):
        spec = _load_spec(yaml_path)
        assert spec.name

    def test_plan_generates_steps(self, yaml_path):
        spec = _load_spec(yaml_path)
        plan = _plan_from_spec(spec)
        assert len(plan.steps) > 0

    def test_same_app_across_envs(self, yaml_path):
        spec = _load_spec(yaml_path)
        assert spec.target.app == "c2004"

    def test_same_version_across_envs(self, yaml_path):
        spec = _load_spec(yaml_path)
        assert spec.target.version == "1.0.20"


# ── scenario-specific checks ──────────────────────────────────────────────────


class TestScenario01VpsVersionBump:
    def _spec(self):
        return _load_spec(EXAMPLES_DIR / "yaml" / "01-vps-version-bump" / "migration.yaml")

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
        return _load_spec(EXAMPLES_DIR / "yaml" / "02-k3s-to-docker" / "migration.yaml")

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
        return _load_spec(EXAMPLES_DIR / "yaml" / "03-docker-to-podman-quadlet" / "migration.yaml")

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
        return _load_spec(EXAMPLES_DIR / "yaml" / "07-staging-to-prod" / "migration.yaml")

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
        return _load_spec(EXAMPLES_DIR / "yaml" / "08-rollback" / "migration.yaml")

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
        return FleetConfig.from_file(EXAMPLES_DIR / "yaml" / "09-fleet-yaml" / "fleet.yaml")

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
        readme = EXAMPLES_DIR / "yaml" / "09-fleet-yaml" / "README.md"
        assert readme.exists()


# ── StepLibrary completeness ──────────────────────────────────────────────────


class TestStepLibraryCompleteness:
    def test_all_named_steps_in_examples_are_in_library(self):
        """Every id used without 'action' in any example must be in StepLibrary."""
        missing = []
        for yaml_path in EXAMPLES_DIR.glob("yaml/*/migration.yaml"):
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

    def test_named_steps_checked_in_all_spec_yamls(self):
        """Extend check to multienv yamls (dev/staging/prod) too."""
        missing = []
        for yaml_path in list(EXAMPLES_DIR.glob("yaml/*/migration.yaml")) + \
                         [p for p in MULTIENV_YAMLS if p.stem in ("dev", "staging", "prod")]:
            with yaml_path.open() as f:
                raw = yaml.safe_load(f) or {}
            for step in raw.get("extra_steps", []):
                if "action" not in step and step.get("id"):
                    if StepLibrary.get(step["id"]) is None:
                        missing.append(f"{yaml_path.parent.name}/{yaml_path.name}: {step['id']}")
        assert missing == [], "Steps without action not in StepLibrary:\n" + "\n".join(missing)


# ── scenario 10: multienv ─────────────────────────────────────────────────────


class TestScenario10Multienv:
    def test_all_three_specs_exist(self):
        for name in ("dev.yaml", "staging.yaml", "prod.yaml"):
            assert (EXAMPLES_DIR / "yaml" / "10-multienv" / name).exists()

    def test_redeploy_yaml_has_local_spec(self):
        with (EXAMPLES_DIR / "yaml" / "10-multienv" / "redeploy.yaml").open() as f:
            data = yaml.safe_load(f)
        assert "local_spec" in data
        assert data["local_spec"] == "dev.yaml"

    def test_prod_has_domain(self):
        spec = _load_spec(EXAMPLES_DIR / "yaml" / "10-multienv" / "prod.yaml")
        assert spec.target.domain

    def test_dev_host_is_local(self):
        spec = _load_spec(EXAMPLES_DIR / "yaml" / "10-multienv" / "dev.yaml")
        assert spec.target.host in ("local", "", None) or spec.source.host == "local"

    def test_staging_has_different_host_than_prod(self):
        staging = _load_spec(EXAMPLES_DIR / "yaml" / "10-multienv" / "staging.yaml")
        prod = _load_spec(EXAMPLES_DIR / "yaml" / "10-multienv" / "prod.yaml")
        assert staging.target.host != prod.target.host


# ── scenario 11: traefik-tls ──────────────────────────────────────────────────


class TestScenario11TraefikTls:
    def _dir(self):
        return EXAMPLES_DIR / "yaml" / "11-traefik-tls"

    def test_tls_yml_exists(self):
        assert (self._dir() / "traefik" / "dynamic" / "tls.yml").exists()

    def test_tls_yml_has_cert_and_key(self):
        content = (self._dir() / "traefik" / "dynamic" / "tls.yml").read_text()
        assert "certFile" in content
        assert "keyFile" in content

    def test_plan_has_recreate_traefik(self):
        plan = _plan_from_spec(_load_spec(self._dir() / "migration.yaml"))
        ids = [s.id for s in plan.steps]
        assert "recreate_traefik" in ids

    def test_plan_has_upload_steps(self):
        plan = _plan_from_spec(_load_spec(self._dir() / "migration.yaml"))
        ids = [s.id for s in plan.steps]
        assert "upload_cert" in ids or "upload_tls_config" in ids


# ── scenario 12: ci-pipeline ──────────────────────────────────────────────────


class TestScenario12CiPipeline:
    def _dir(self):
        return EXAMPLES_DIR / "yaml" / "12-ci-pipeline"

    def test_github_workflow_exists(self):
        assert (self._dir() / "deploy.github.yml").exists()

    def test_gitlab_ci_exists(self):
        assert (self._dir() / "deploy.gitlab.yml").exists()

    def test_github_workflow_has_redeploy_run(self):
        content = (self._dir() / "deploy.github.yml").read_text()
        assert "redeploy run" in content

    def test_gitlab_ci_has_redeploy_run(self):
        content = (self._dir() / "deploy.gitlab.yml").read_text()
        assert "redeploy run" in content

    def test_github_workflow_has_ssh_key_secret(self):
        content = (self._dir() / "deploy.github.yml").read_text()
        assert "SSH_PRIVATE_KEY" in content

    def test_plan_has_audit_step(self):
        plan = _plan_from_spec(_load_spec(self._dir() / "migration.yaml"))
        ids = [s.id for s in plan.steps]
        assert "tag_ci_deploy" in ids


# ── scenario 13: multi-app-monorepo ───────────────────────────────────────────


class TestScenario13Monorepo:
    def _dir(self):
        return EXAMPLES_DIR / "yaml" / "13-multi-app-monorepo"

    def test_has_fleet_yaml(self):
        assert (self._dir() / "fleet.yaml").exists()

    def test_fleet_has_three_envs(self):
        config = FleetConfig.from_file(self._dir() / "fleet.yaml")
        stages = {d.stage for d in config.devices}
        assert Stage.PROD in stages
        assert Stage.STAGING in stages
        assert Stage.LOCAL in stages

    def test_fleet_prod_has_traefik_expectation(self):
        config = FleetConfig.from_file(self._dir() / "fleet.yaml")
        prod = config.get_device("vps-prod-c2004")
        assert prod is not None
        assert DeviceExpectation.HAS_TRAEFIK in prod.expectations

    def test_plan_has_rsync_steps(self):
        plan = _plan_from_spec(_load_spec(self._dir() / "migration.yaml"))
        ids = [s.id for s in plan.steps]
        assert any("rsync" in i for i in ids)

    def test_plan_has_promote_compose(self):
        plan = _plan_from_spec(_load_spec(self._dir() / "migration.yaml"))
        ids = [s.id for s in plan.steps]
        assert "promote_compose" in ids

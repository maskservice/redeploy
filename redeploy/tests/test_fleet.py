"""Tests for redeploy.fleet and redeploy.steps."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from redeploy.fleet import (
    DeviceExpectation,
    FleetConfig,
    FleetDevice,
    Stage,
    STAGE_DEFAULT_EXPECTATIONS,
)
from redeploy.steps import StepLibrary
from redeploy.models import StepAction


# ── FleetDevice ───────────────────────────────────────────────────────────────


class TestFleetDevice:
    def test_basic(self):
        d = FleetDevice(id="test", name="Test", ssh_host="root@1.2.3.4")
        assert d.ssh_user == "root"
        assert d.ssh_ip == "1.2.3.4"
        assert not d.is_local

    def test_local_device(self):
        d = FleetDevice(id="local", ssh_host="")
        assert d.is_local

    def test_is_prod_via_stage(self):
        d = FleetDevice(id="p", stage=Stage.PROD)
        assert d.is_prod

    def test_is_prod_via_tag(self):
        d = FleetDevice(id="p", tags=["prod", "vps"])
        assert d.is_prod

    def test_has_tag(self):
        d = FleetDevice(id="p", tags=["rpi", "kiosk"])
        assert d.has_tag("rpi")
        assert not d.has_tag("vps")

    def test_has_expectation(self):
        d = FleetDevice(id="p", expectations=[DeviceExpectation.HAS_DOCKER])
        assert d.has_expectation(DeviceExpectation.HAS_DOCKER)
        assert not d.has_expectation(DeviceExpectation.HAS_K3S)

    def test_verify_expectations_pass(self):
        class FakeRuntime:
            docker = "Docker 29"
            docker_compose = "v2.x"
            podman = None
            k3s = None

        class FakeState:
            runtime = FakeRuntime()
            ports = {}
            health = []
            services = {}

        d = FleetDevice(
            id="p",
            expectations=[DeviceExpectation.HAS_DOCKER, DeviceExpectation.HAS_DOCKER_COMPOSE],
        )
        failures = d.verify_expectations(FakeState())
        assert failures == []

    def test_verify_expectations_fail_docker(self):
        class FakeRuntime:
            docker = None
            docker_compose = None
            podman = None
            k3s = None

        class FakeState:
            runtime = FakeRuntime()
            ports = {}
            health = []
            services = {}

        d = FleetDevice(id="p", expectations=[DeviceExpectation.HAS_DOCKER])
        failures = d.verify_expectations(FakeState())
        assert any("has_docker" in f for f in failures)

    def test_verify_expectations_no_k3s_fail(self):
        class FakeRuntime:
            k3s = "k3s v1.34"

        class FakeState:
            runtime = FakeRuntime()
            ports = {}
            health = []
            services = {}

        d = FleetDevice(id="p", expectations=[DeviceExpectation.NO_K3S])
        failures = d.verify_expectations(FakeState())
        assert any("no_k3s" in f for f in failures)


# ── Stage defaults ────────────────────────────────────────────────────────────


class TestStageDefaults:
    def test_prod_has_no_k3s(self):
        exps = STAGE_DEFAULT_EXPECTATIONS[Stage.PROD]
        assert DeviceExpectation.NO_K3S in exps

    def test_local_minimal(self):
        exps = STAGE_DEFAULT_EXPECTATIONS[Stage.LOCAL]
        assert DeviceExpectation.HAS_DOCKER in exps
        assert DeviceExpectation.SSH_REACHABLE not in exps


# ── FleetConfig.from_file ─────────────────────────────────────────────────────


class TestFleetConfigFromFile:
    def test_load_deploy_fleet_yaml(self, tmp_path):
        yaml_content = textwrap.dedent("""\
            devices:
              - id: vps-prod
                name: "VPS Production"
                arch: amd64
                strategy: docker_full
                ssh_host: "root@1.2.3.4"
                remote_dir: "~/c2004"
                version: "latest"
                env_file: "envs/vps.env"
                domain: "c2004.mask.services"
                compose_files: ["docker-compose.vps.yml"]
                apps: [c2004]
                tags: [prod, vps]
                color: "#f59e0b"

              - id: rpi3-lab
                name: "RPi3 Lab"
                arch: rpi3
                strategy: native_kiosk
                ssh_host: "tom@192.168.1.10"
                remote_dir: "/home/pi/c2004"
                version: "latest"
                env_file: "envs/rpi3.env"
                apps: [c2004]
                tags: [test, rpi]
                debug: true
                color: "#ef4444"
        """)
        f = tmp_path / "fleet.yaml"
        f.write_text(yaml_content)

        config = FleetConfig.from_file(f)
        assert len(config.devices) == 2

        vps = config.get_device("vps-prod")
        assert vps is not None
        assert vps.stage == Stage.PROD
        assert vps.is_prod
        assert DeviceExpectation.NO_K3S in vps.expectations
        assert DeviceExpectation.HTTPS_REACHABLE in vps.expectations

        rpi = config.get_device("rpi3-lab")
        assert rpi is not None
        assert rpi.stage == Stage.DEV
        assert not rpi.is_prod

    def test_by_tag(self, tmp_path):
        yaml_content = textwrap.dedent("""\
            devices:
              - id: a
                name: A
                arch: amd64
                strategy: docker_full
                tags: [prod, vps]
              - id: b
                name: B
                arch: rpi3
                strategy: native_kiosk
                tags: [test, rpi]
        """)
        f = tmp_path / "fleet.yaml"
        f.write_text(yaml_content)

        config = FleetConfig.from_file(f)
        assert len(config.by_tag("prod")) == 1
        assert len(config.by_tag("rpi")) == 1
        assert len(config.by_stage(Stage.PROD)) == 1

    def test_by_strategy(self, tmp_path):
        yaml_content = textwrap.dedent("""\
            devices:
              - id: a
                name: A
                arch: amd64
                strategy: docker_full
                tags: [prod]
              - id: b
                name: B
                arch: rpi3
                strategy: docker_full
                tags: [dev]
        """)
        f = tmp_path / "fleet.yaml"
        f.write_text(yaml_content)
        config = FleetConfig.from_file(f)
        assert len(config.by_strategy("docker_full")) == 2


# ── StepLibrary ───────────────────────────────────────────────────────────────


class TestStepLibrary:
    def test_list(self):
        ids = StepLibrary.list()
        assert "flush_k3s_iptables" in ids
        assert "stop_k3s" in ids
        assert "http_health_check" in ids
        assert "sync_env" in ids

    def test_get_known(self):
        step = StepLibrary.get("flush_k3s_iptables")
        assert step is not None
        assert step.id == "flush_k3s_iptables"
        assert step.action == StepAction.SSH_CMD
        assert "CNI-HOSTPORT-DNAT" in step.command

    def test_get_unknown(self):
        assert StepLibrary.get("nonexistent_step") is None

    def test_get_with_overrides(self):
        step = StepLibrary.get("http_health_check", url="https://example.com/health", expect="ok")
        assert step.url == "https://example.com/health"
        assert step.expect == "ok"
        assert step.action == StepAction.HTTP_CHECK

    def test_get_returns_copy(self):
        s1 = StepLibrary.get("stop_k3s")
        s2 = StepLibrary.get("stop_k3s")
        s1.description = "modified"
        assert s2.description != "modified"

    def test_resolve_from_spec_with_library_match(self):
        raw = {"id": "flush_k3s_iptables"}
        step = StepLibrary.resolve_from_spec(raw)
        assert step.action == StepAction.SSH_CMD
        assert "iptables" in step.command

    def test_resolve_from_spec_override_action(self):
        raw = {"id": "flush_k3s_iptables", "action": "ssh_cmd", "command": "echo custom"}
        step = StepLibrary.resolve_from_spec(raw)
        assert step.command == "echo custom"

    def test_resolve_from_spec_unknown_uses_raw(self):
        raw = {
            "id": "my_custom_step",
            "action": "ssh_cmd",
            "description": "Custom step",
            "command": "echo hello",
        }
        step = StepLibrary.resolve_from_spec(raw)
        assert step.id == "my_custom_step"
        assert step.command == "echo hello"

    def test_all_returns_copies(self):
        lib = StepLibrary.all()
        assert len(lib) > 5
        lib["stop_k3s"].description = "modified"
        assert StepLibrary.get("stop_k3s").description != "modified"

    def test_new_steps_registered(self):
        ids = StepLibrary.list()
        for expected in ["stop_podman", "enable_podman_unit",
                         "systemctl_restart", "systemctl_daemon_reload", "git_pull"]:
            assert expected in ids, f"Missing step: {expected}"

    def test_stop_podman_has_rollback(self):
        s = StepLibrary.get("stop_podman")
        assert s is not None
        assert s.rollback_command is not None
        assert "start" in s.rollback_command

    def test_git_pull_has_rollback(self):
        s = StepLibrary.get("git_pull")
        assert s is not None
        assert "reset" in s.rollback_command
        assert "ff-only" in s.command

    def test_systemctl_restart_action(self):
        s = StepLibrary.get("systemctl_restart")
        assert s is not None
        assert s.action == StepAction.SYSTEMCTL_START

    def test_systemctl_daemon_reload_command(self):
        s = StepLibrary.get("systemctl_daemon_reload")
        assert s is not None
        assert "daemon-reload" in s.command

    def test_enable_podman_unit_command(self):
        s = StepLibrary.get("enable_podman_unit")
        assert s is not None
        assert "enable" in s.command
        assert "daemon-reload" in s.command


# ── TargetConfig.host + Planner ───────────────────────────────────────────────


class TestTargetConfigHost:
    def _make_planner(self, target_host=None, state_host="root@10.0.0.1"):
        from redeploy.models import (
            DeployStrategy, InfraState, RuntimeInfo, TargetConfig,
        )
        from redeploy.plan import Planner

        state = InfraState(
            host=state_host,
            app="myapp",
            runtime=RuntimeInfo(docker="20.10"),
            detected_strategy=DeployStrategy.DOCKER_FULL,
        )
        target = TargetConfig(
            strategy=DeployStrategy.DOCKER_FULL,
            app="myapp",
            host=target_host,
        )
        return Planner(state, target)

    def test_uses_state_host_when_target_host_none(self):
        p = self._make_planner(target_host=None, state_host="root@1.2.3.4")
        plan = p.run()
        assert plan.host == "root@1.2.3.4"

    def test_target_host_overrides_state_host(self):
        p = self._make_planner(target_host="root@9.9.9.9", state_host="root@1.2.3.4")
        plan = p.run()
        assert plan.host == "root@9.9.9.9"

    def test_app_fallback_from_state(self):
        from redeploy.models import (
            DeployStrategy, InfraState, RuntimeInfo, TargetConfig,
        )
        from redeploy.plan import Planner
        state = InfraState(
            host="root@1.2.3.4",
            app="from_state",
            runtime=RuntimeInfo(docker="20.10"),
            detected_strategy=DeployStrategy.DOCKER_FULL,
        )
        target = TargetConfig(
            strategy=DeployStrategy.DOCKER_FULL,
            app="",      # empty → falls back to state.app
        )
        plan = Planner(state, target).run()
        assert plan.app == "from_state"

    def test_target_app_used_when_set(self):
        p = self._make_planner()
        plan = p.run()
        assert plan.app == "myapp"


# ── Fleet (unified first-class view) ─────────────────────────────────────────


class TestFleet:
    def _yaml(self, tmp_path: Path, content: str) -> Path:
        p = tmp_path / "fleet.yaml"
        p.write_text(textwrap.dedent(content))
        return p

    def test_from_file_basic(self, tmp_path):
        from redeploy.fleet import Fleet
        path = self._yaml(tmp_path, """
            devices:
              - id: pi1
                name: Pi One
                ssh_host: pi@192.168.1.10
                strategy: docker_full
                tags: [prod]
              - id: pi2
                ssh_host: pi@192.168.1.11
                strategy: podman_quadlet
                tags: [dev]
        """)
        fleet = Fleet.from_file(path)
        assert len(fleet) == 2
        assert fleet.get("pi1") is not None
        assert fleet.get("missing") is None

    def test_from_file_iter(self, tmp_path):
        from redeploy.fleet import Fleet
        path = self._yaml(tmp_path, """
            devices:
              - id: d1
                ssh_host: root@10.0.0.1
              - id: d2
                ssh_host: root@10.0.0.2
        """)
        fleet = Fleet.from_file(path)
        ids = [d.id for d in fleet]
        assert ids == ["d1", "d2"]

    def test_by_tag(self, tmp_path):
        from redeploy.fleet import Fleet
        path = self._yaml(tmp_path, """
            devices:
              - id: a
                ssh_host: root@1.1.1.1
                tags: [kiosk, prod]
              - id: b
                ssh_host: root@1.1.1.2
                tags: [docker]
        """)
        fleet = Fleet.from_file(path)
        assert len(fleet.by_tag("kiosk")) == 1
        assert fleet.by_tag("kiosk")[0].id == "a"
        assert fleet.by_tag("missing") == []

    def test_by_stage(self, tmp_path):
        from redeploy.fleet import Fleet
        path = self._yaml(tmp_path, """
            devices:
              - id: p
                ssh_host: root@1.1.1.1
                stage: prod
                tags: [prod]
              - id: d
                ssh_host: root@1.1.1.2
                stage: dev
        """)
        fleet = Fleet.from_file(path)
        assert len(fleet.by_stage(Stage.PROD)) == 1
        assert fleet.by_stage(Stage.PROD)[0].id == "p"

    def test_by_strategy(self, tmp_path):
        from redeploy.fleet import Fleet
        path = self._yaml(tmp_path, """
            devices:
              - id: x
                ssh_host: root@1.1.1.1
                strategy: kiosk_appliance
              - id: y
                ssh_host: root@1.1.1.2
                strategy: docker_full
        """)
        fleet = Fleet.from_file(path)
        assert len(fleet.by_strategy("kiosk_appliance")) == 1
        assert fleet.by_strategy("kiosk_appliance")[0].id == "x"

    def test_prod_shortcut(self, tmp_path):
        from redeploy.fleet import Fleet
        path = self._yaml(tmp_path, """
            devices:
              - id: a
                ssh_host: root@1.1.1.1
                stage: prod
                tags: [prod]
              - id: b
                ssh_host: root@1.1.1.2
                stage: dev
        """)
        fleet = Fleet.from_file(path)
        assert [d.id for d in fleet.prod()] == ["a"]

    def test_merge_other_wins(self, tmp_path):
        from redeploy.fleet import Fleet
        base = Fleet([
            FleetDevice(id="x", ssh_host="root@1.1.1.1", name="old"),
            FleetDevice(id="y", ssh_host="root@1.1.1.2"),
        ])
        override = Fleet([
            FleetDevice(id="x", ssh_host="root@9.9.9.9", name="new"),
            FleetDevice(id="z", ssh_host="root@1.1.1.3"),
        ])
        merged = base.merge(override)
        assert len(merged) == 3
        assert merged.get("x").name == "new"
        assert merged.get("x").ssh_host == "root@9.9.9.9"
        assert merged.get("y") is not None
        assert merged.get("z") is not None

    def test_from_registry_empty(self, tmp_path):
        from redeploy.fleet import Fleet
        from unittest.mock import patch
        from redeploy.models import DeviceRegistry
        with patch.object(DeviceRegistry, "load", return_value=DeviceRegistry()):
            fleet = Fleet.from_registry()
        assert len(fleet) == 0

    def test_from_registry_converts_known_device(self, tmp_path):
        from redeploy.fleet import Fleet
        from unittest.mock import patch
        from redeploy.models import DeviceRegistry, KnownDevice
        reg = DeviceRegistry()
        reg.upsert(KnownDevice(
            id="vps1", host="root@10.0.0.5",
            strategy="docker_full", tags=["prod"],
            domain="example.com",
        ))
        with patch.object(DeviceRegistry, "load", return_value=reg):
            fleet = Fleet.from_registry()
        assert len(fleet) == 1
        d = fleet.get("vps1")
        assert d is not None
        assert d.ssh_host == "root@10.0.0.5"
        assert d.stage == Stage.PROD

    def test_from_config_wraps_fleet_config(self, tmp_path):
        from redeploy.fleet import Fleet
        path = self._yaml(tmp_path, """
            devices:
              - id: q1
                ssh_host: root@1.1.1.1
        """)
        config = FleetConfig.from_file(path)
        fleet = Fleet.from_config(config)
        assert len(fleet) == 1

    def test_repr(self, tmp_path):
        from redeploy.fleet import Fleet
        fleet = Fleet([FleetDevice(id="a", ssh_host="root@1.1.1.1")])
        assert "1" in repr(fleet)

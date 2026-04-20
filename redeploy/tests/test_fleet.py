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

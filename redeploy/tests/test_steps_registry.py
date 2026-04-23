"""Tests that every domain module in redeploy.steps is correctly wired into StepLibrary."""
from __future__ import annotations

import pytest

from redeploy.models import MigrationStep
from redeploy.steps import StepLibrary
from redeploy.steps import (
    docker,
    generic,
    hardware,
    k3s,
    kiosk,
    podman,
    process,
    scm,
    transfer,
)


ALL_MODULES = [
    docker,
    generic,
    hardware,
    k3s,
    kiosk,
    podman,
    process,
    scm,
    transfer,
]


class TestNoDuplicateIds:
    def test_no_duplicate_ids_within_each_module(self):
        for mod in ALL_MODULES:
            ids = [s.id for s in mod.ALL]
            assert len(ids) == len(set(ids)), f"duplicate ids in {mod.__name__}: {ids}"

    def test_no_duplicate_ids_across_all_modules(self):
        all_ids = []
        for mod in ALL_MODULES:
            all_ids.extend(s.id for s in mod.ALL)
        assert len(all_ids) == len(set(all_ids)), f"duplicate ids across modules: {all_ids}"


class TestAllStepsReachableViaLibrary:
    @pytest.mark.parametrize(
        "module",
        ALL_MODULES,
        ids=lambda m: m.__name__.split(".")[-1],
    )
    def test_every_step_in_library(self, module):
        for step in module.ALL:
            found = StepLibrary.get(step.id)
            assert found is not None, f"{step.id} missing from StepLibrary"
            assert isinstance(found, MigrationStep)


class TestLibraryGetReturnsCopy:
    def test_mutating_copy_does_not_affect_template(self):
        s1 = StepLibrary.get("http_health_check")
        s2 = StepLibrary.get("http_health_check")
        assert s1 is not s2
        s1.url = "https://modified.example.com"
        assert s2.url != s1.url


class TestKnownStepsExist:
    def test_k3s_steps(self):
        for sid in ("flush_k3s_iptables", "delete_k3s_ingresses", "stop_k3s", "disable_k3s"):
            assert StepLibrary.get(sid) is not None

    def test_docker_steps(self):
        for sid in ("docker_prune", "docker_compose_down", "restart_traefik"):
            assert StepLibrary.get(sid) is not None

    def test_podman_steps(self):
        for sid in ("podman_daemon_reload", "stop_podman", "enable_podman_unit"):
            assert StepLibrary.get(sid) is not None

    def test_generic_steps(self):
        for sid in (
            "wait_startup",
            "wait_startup_long",
            "http_health_check",
            "version_check",
            "systemctl_restart",
            "systemctl_daemon_reload",
            "stop_nginx",
        ):
            assert StepLibrary.get(sid) is not None

    def test_scm_steps(self):
        assert StepLibrary.get("git_pull") is not None

    def test_transfer_steps(self):
        assert StepLibrary.get("sync_env") is not None

    def test_process_steps(self):
        for sid in ("kill_processes_on_ports", "kill_dev_processes"):
            assert StepLibrary.get(sid) is not None

    def test_hardware_steps(self):
        assert StepLibrary.get("hardware_diagnostic") is not None

    def test_kiosk_steps(self):
        for sid in ("kanshi_dsi_only", "autostart_kiosk", "browser_kiosk_script"):
            assert StepLibrary.get(sid) is not None

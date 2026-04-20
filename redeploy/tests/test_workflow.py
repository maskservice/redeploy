"""Tests for detect/workflow.py — DetectionWorkflow, WorkflowResult, HostDetectionResult."""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from redeploy.detect.workflow import (
    DetectionWorkflow,
    HostDetectionResult,
    WorkflowResult,
)
from redeploy.models import (
    AppHealthInfo,
    ConflictInfo,
    ConflictSeverity,
    DeployStrategy,
    DeviceRegistry,
    EnvironmentConfig,
    InfraState,
    KnownDevice,
    ProjectManifest,
    RuntimeInfo,
)


# ── helpers ───────────────────────────────────────────────────────────────────


def _state(host="root@10.0.0.1", strategy=DeployStrategy.DOCKER_FULL,
           ports=None, version=None) -> InfraState:
    return InfraState(
        host=host,
        app="myapp",
        runtime=RuntimeInfo(docker="20.10", arch="x86_64", os="Ubuntu 22.04"),
        detected_strategy=strategy,
        ports={p: MagicMock() for p in (ports or [])},
        current_version=version,
    )


def _reachable_host(host="root@10.0.0.1", strategy=DeployStrategy.DOCKER_FULL,
                    env="prod") -> HostDetectionResult:
    from redeploy.detect.templates import DetectionTemplate, TemplateMatch
    t = DetectionTemplate(id="vps-docker-prod", name="VPS Docker", strategy=strategy,
                          environment=env, notes=["note1"])
    match = TemplateMatch(template=t, score=8.0, max_score=10.0,
                          matched_conditions=["Docker"], failed_conditions=[])
    from redeploy.detect.templates import DetectionResult
    tr = DetectionResult(best=match, ranked=[match], ctx={
        "host": host, "app": "myapp", "has_health": True,
        "port_8000": True, "port_8080": False,
    })
    return HostDetectionResult(
        host=host, ip="10.0.0.1", reachable=True,
        ssh_user="root", ssh_key="/root/.ssh/id_ed25519",
        arch="x86_64", state=_state(host), template_result=tr,
    )


def _unreachable_host(host="root@10.0.0.2") -> HostDetectionResult:
    return HostDetectionResult(host=host, reachable=False, error="timeout")


# ── WorkflowResult ────────────────────────────────────────────────────────────


class TestWorkflowResult:
    def test_reachable_filter(self):
        r = WorkflowResult(hosts=[_reachable_host(), _unreachable_host()])
        assert len(r.reachable) == 1
        assert len(r.unreachable) == 1

    def test_by_env(self):
        r = WorkflowResult(hosts=[
            _reachable_host("a@1", env="prod"),
            _reachable_host("b@2", env="dev"),
            _reachable_host("c@3", env="prod"),
        ])
        by = r.by_env()
        assert len(by["prod"]) == 2
        assert len(by["dev"]) == 1

    def test_summary_contains_host(self):
        r = WorkflowResult(hosts=[_reachable_host("root@1.2.3.4")])
        s = r.summary()
        assert "root@1.2.3.4" in s
        assert "1/1" in s

    def test_summary_unreachable(self):
        r = WorkflowResult(hosts=[_unreachable_host("root@9.9.9.9")])
        s = r.summary()
        assert "0/1" in s
        assert "timeout" in s

    def test_generated_redeploy_yaml_contains_host(self):
        r = WorkflowResult(app="myapp", hosts=[_reachable_host("root@1.2.3.4")])
        yaml_out = r.generated_redeploy_yaml()
        assert "root@1.2.3.4" in yaml_out
        assert "app: myapp" in yaml_out
        assert "environments:" in yaml_out

    def test_generated_redeploy_yaml_deduplicates_envs(self):
        r = WorkflowResult(app="myapp", hosts=[
            _reachable_host("a@1", env="prod"),
            _reachable_host("b@2", env="prod"),   # same env label
        ])
        yaml_out = r.generated_redeploy_yaml()
        assert "prod:" in yaml_out
        assert "prod2:" in yaml_out   # deduplicated

    def test_generated_redeploy_yaml_empty_when_no_reachable(self):
        r = WorkflowResult(hosts=[_unreachable_host()])
        yaml_out = r.generated_redeploy_yaml()
        assert "environments:" in yaml_out
        # No hosts under environments
        lines = [l.strip() for l in yaml_out.splitlines() if l.strip()]
        env_idx = next(i for i, l in enumerate(lines) if l == "environments:")
        assert env_idx == len(lines) - 1 or lines[env_idx + 1].startswith("#")

    def test_generated_migration_yaml_no_reachable(self):
        r = WorkflowResult(hosts=[_unreachable_host()])
        out = r.generated_migration_yaml()
        assert "No reachable" in out

    def test_generated_migration_yaml_contains_strategy(self):
        r = WorkflowResult(app="myapp", hosts=[_reachable_host()])
        out = r.generated_migration_yaml()
        assert "strategy: docker_full" in out
        assert "app: myapp" in out

    def test_generated_migration_yaml_for_env(self):
        r = WorkflowResult(app="myapp", hosts=[
            _reachable_host("a@1", env="prod"),
            _reachable_host("b@2", env="dev"),
        ])
        out = r.generated_migration_yaml(env="dev")
        assert "b@2" in out


# ── HostDetectionResult properties ───────────────────────────────────────────


class TestHostDetectionResult:
    def test_strategy_from_template(self):
        h = _reachable_host()
        assert h.strategy == DeployStrategy.DOCKER_FULL

    def test_strategy_from_state_when_no_template(self):
        h = HostDetectionResult(
            host="x", reachable=True,
            state=_state(strategy=DeployStrategy.K3S),
        )
        assert h.strategy == DeployStrategy.K3S

    def test_strategy_unknown_when_nothing(self):
        h = HostDetectionResult(host="x", reachable=False)
        assert h.strategy == DeployStrategy.UNKNOWN

    def test_environment(self):
        h = _reachable_host(env="rpi5")
        assert h.environment == "rpi5"

    def test_confidence(self):
        h = _reachable_host()
        assert h.confidence in ("high", "medium", "low")

    def test_env_block_generated(self):
        h = _reachable_host("root@1.2.3.4")
        block = h.env_block()
        assert "root@1.2.3.4" in block

    def test_notes(self):
        h = _reachable_host()
        assert "note1" in h.notes()


# ── DetectionWorkflow._collect_hosts ─────────────────────────────────────────


class TestCollectHosts:
    def _workflow(self):
        return DetectionWorkflow(deep=False, timeout=1)

    def test_explicit_hosts_included(self):
        w = self._workflow()
        result = w._collect_hosts(["root@1.2.3.4"], None, None, None)
        assert "root@1.2.3.4" in result

    def test_manifest_envs_added(self):
        w = self._workflow()
        m = ProjectManifest(app="x", environments={
            "prod": EnvironmentConfig(host="root@9.9.9.9"),
        })
        result = w._collect_hosts([], m, None, None)
        assert "root@9.9.9.9" in result

    def test_local_hosts_excluded_from_manifest(self):
        w = self._workflow()
        m = ProjectManifest(app="x", environments={
            "dev": EnvironmentConfig(host="local"),
        })
        result = w._collect_hosts([], m, None, None)
        assert "local" not in result

    def test_registry_hosts_added(self):
        w = self._workflow()
        reg = DeviceRegistry(devices=[
            KnownDevice(id="dev1", host="pi@192.168.1.5"),
        ])
        result = w._collect_hosts([], None, reg, None)
        assert "pi@192.168.1.5" in result

    def test_deduplication_by_ip(self):
        w = self._workflow()
        # root@1.2.3.4 and pi@1.2.3.4 same IP → deduplicated
        result = w._collect_hosts(["root@1.2.3.4", "pi@1.2.3.4"], None, None, None)
        assert len(result) == 1

    def test_explicit_takes_priority_over_registry(self):
        w = self._workflow()
        reg = DeviceRegistry(devices=[
            KnownDevice(id="dev1", host="root@1.2.3.4"),
        ])
        result = w._collect_hosts(["root@1.2.3.4"], None, reg, None)
        assert result.count("root@1.2.3.4") == 1

    def test_empty_when_no_sources(self):
        w = self._workflow()
        result = w._collect_hosts([], None, DeviceRegistry(), None)
        assert result == []


# ── DetectionWorkflow.run (mocked) ────────────────────────────────────────────


class TestDetectionWorkflowRun:
    def _mock_probe(self, reachable=True, strategy="docker_full"):
        p = MagicMock()
        p.reachable = reachable
        p.ip = "10.0.0.1"
        p.ssh_user = "root"
        p.ssh_key = "/root/.ssh/id_ed25519"
        p.arch = "x86_64"
        p.os_info = "Ubuntu 22.04"
        p.error = "" if reachable else "timeout"
        p.strategy = strategy
        p.app = "myapp"
        p.has_chromium = False
        p.running_services = []
        return p

    def test_run_empty_hosts_returns_empty(self):
        w = DetectionWorkflow(deep=False)
        result = w.run(hosts=[], registry=DeviceRegistry())
        assert result.hosts == []

    def test_run_unreachable_host(self):
        w = DetectionWorkflow(deep=False)
        with patch("redeploy.detect.workflow.DetectionWorkflow._probe_ssh",
                   return_value=HostDetectionResult(host="x", reachable=False, error="timeout")):
            result = w.run(hosts=["root@1.2.3.4"], registry=DeviceRegistry())
        assert len(result.hosts) == 1
        assert not result.hosts[0].reachable

    def test_run_reachable_scores_template(self):
        w = DetectionWorkflow(deep=False)
        state = _state()
        hr = HostDetectionResult(
            host="root@10.0.0.1", ip="10.0.0.1",
            reachable=True, ssh_user="root",
        )

        with patch("redeploy.detect.workflow.DetectionWorkflow._probe_ssh", return_value=hr):
            result = w.run(hosts=["root@10.0.0.1"], registry=DeviceRegistry())

        assert len(result.hosts) == 1
        assert result.hosts[0].reachable

    def test_run_sets_app_on_result(self):
        w = DetectionWorkflow(deep=False)
        hr = HostDetectionResult(host="x", reachable=False, error="no ssh")
        with patch("redeploy.detect.workflow.DetectionWorkflow._probe_ssh", return_value=hr):
            result = w.run(hosts=["x"], app="c2004", registry=DeviceRegistry())
        assert result.app == "c2004"

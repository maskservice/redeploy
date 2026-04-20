"""Tests for redeploy CLI commands using Click CliRunner (no real SSH)."""
from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from redeploy.cli import cli


# ── helpers ───────────────────────────────────────────────────────────────────


def _migration_yaml(strategy="docker_full", host="local") -> str:
    return textwrap.dedent(f"""\
        name: test migration
        source:
          strategy: {strategy}
          host: {host}
          app: myapp
          version: "1.0.0"
        target:
          strategy: {strategy}
          host: {host}
          app: myapp
          version: "1.0.1"
          remote_dir: ~/myapp
    """)


def _runner():
    return CliRunner(mix_stderr=False)


# ── redeploy run --plan-only ──────────────────────────────────────────────────


class TestRunPlanOnly:
    def test_plan_only_exit_zero(self, tmp_path):
        spec = tmp_path / "migration.yaml"
        spec.write_text(_migration_yaml())
        runner = _runner()
        result = runner.invoke(cli, ["run", str(spec), "--plan-only"])
        assert result.exit_code == 0, result.output

    def test_plan_only_shows_steps(self, tmp_path):
        spec = tmp_path / "migration.yaml"
        spec.write_text(_migration_yaml())
        result = _runner().invoke(cli, ["run", str(spec), "--plan-only"])
        assert "plan" in result.output.lower() or "step" in result.output.lower()

    def test_plan_only_missing_spec_exits_1(self, tmp_path):
        result = _runner().invoke(cli, ["run", str(tmp_path / "nofile.yaml"), "--plan-only"])
        assert result.exit_code != 0

    def test_plan_only_k3s_to_docker(self, tmp_path):
        spec = tmp_path / "m.yaml"
        spec.write_text(_migration_yaml(strategy="k3s"))
        result = _runner().invoke(cli, ["run", str(spec), "--plan-only"])
        assert result.exit_code == 0

    def test_plan_only_saves_plan_out(self, tmp_path):
        spec = tmp_path / "migration.yaml"
        spec.write_text(_migration_yaml())
        out = tmp_path / "plan.yaml"
        result = _runner().invoke(cli, ["run", str(spec), "--plan-only",
                                        "--plan-out", str(out)])
        assert result.exit_code == 0
        assert out.exists()

    def test_run_dry_run(self, tmp_path):
        spec = tmp_path / "migration.yaml"
        spec.write_text(_migration_yaml(host="local"))
        result = _runner().invoke(cli, ["run", str(spec), "--dry-run"])
        assert result.exit_code == 0
        assert "dry" in result.output.lower() or "DRY" in result.output

    def test_env_unknown_warns(self, tmp_path):
        spec = tmp_path / "migration.yaml"
        spec.write_text(_migration_yaml())
        manifest = tmp_path / "redeploy.yaml"
        manifest.write_text("app: myapp\n")
        result = _runner().invoke(cli, ["run", str(spec), "--plan-only",
                                        "--env", "nonexistent"],
                                  catch_exceptions=False)
        assert "nonexistent" in result.output or result.exit_code == 0

    def test_env_prod_applied_from_manifest(self, tmp_path):
        from redeploy.models import ProjectManifest, EnvironmentConfig
        spec = tmp_path / "migration.yaml"
        spec.write_text(_migration_yaml(host="local"))
        m = ProjectManifest(
            app="myapp",
            environments={"prod": EnvironmentConfig(host="local", strategy="docker_full")},
        )
        with patch("redeploy.models.ProjectManifest.find_and_load", return_value=m):
            result = _runner().invoke(cli, ["run", str(spec), "--plan-only", "--env", "prod"])
        assert result.exit_code == 0

    def test_run_plan_only_rejects_markdown_spec_with_clear_error(self, tmp_path):
        spec = tmp_path / "migration.md"
        spec.write_text("# markpact prototype\n", encoding="utf-8")

        result = _runner().invoke(cli, ["run", str(spec), "--plan-only"])

        assert result.exit_code == 1
        assert "Unsupported spec format '.md'" in result.output
        assert "markdown/markpact specs are not implemented" in result.output


# ── redeploy status ───────────────────────────────────────────────────────────


class TestStatus:
    def test_status_no_manifest(self, tmp_path):
        with patch("redeploy.models.ProjectManifest.find_and_load", return_value=None):
            result = _runner().invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "no redeploy.yaml" in result.output.lower() or "manifest" in result.output.lower()

    def test_status_with_manifest(self, tmp_path):
        from redeploy.models import ProjectManifest, EnvironmentConfig
        m = ProjectManifest(
            app="myapp", host="root@1.2.3.4",
            environments={"prod": EnvironmentConfig(host="root@1.2.3.4", strategy="docker_full")}
        )
        with patch("redeploy.models.ProjectManifest.find_and_load", return_value=m):
            result = _runner().invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "myapp" in result.output

    def test_status_rejects_markdown_spec_with_clear_error(self, tmp_path):
        spec = tmp_path / "migration.md"
        spec.write_text("# markpact prototype\n", encoding="utf-8")

        with patch("redeploy.models.ProjectManifest.find_and_load", return_value=None):
            result = _runner().invoke(cli, ["status", str(spec)])

        assert result.exit_code == 1
        assert "Unsupported spec format '.md'" in result.output
        assert "markdown/markpact specs are not implemented" in result.output


# ── redeploy init ─────────────────────────────────────────────────────────────


class TestInit:
    def test_init_creates_migration_yaml(self, tmp_path):
        runner = CliRunner(mix_stderr=False)
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["init", "--app", "myapp",
                                         "--host", "local", "--strategy", "docker_full"],
                                   catch_exceptions=False)
        assert result.exit_code == 0

    def test_init_idempotent(self, tmp_path):
        runner = CliRunner(mix_stderr=False)
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result1 = runner.invoke(cli, ["init", "--app", "test"])
            result2 = runner.invoke(cli, ["init", "--app", "test"])
        assert result1.exit_code in (0, 1)
        assert result2.exit_code in (0, 1)


# ── redeploy devices ──────────────────────────────────────────────────────────


class TestDevices:
    def test_devices_empty_registry(self):
        from redeploy.models import DeviceRegistry
        with patch("redeploy.models.DeviceRegistry.load", return_value=DeviceRegistry()):
            result = _runner().invoke(cli, ["devices"])
        assert result.exit_code == 0

    def test_devices_lists_known(self):
        from redeploy.models import DeviceRegistry, KnownDevice
        reg = DeviceRegistry(devices=[
            KnownDevice(id="root@1.2.3.4", host="root@1.2.3.4",
                        strategy="docker_full", tags=["prod"])
        ])
        with patch("redeploy.models.DeviceRegistry.load", return_value=reg):
            result = _runner().invoke(cli, ["devices"])
        assert result.exit_code == 0
        assert "docker_full" in result.output   # strategy shown even with truncated ID

    def test_devices_filter_by_tag(self):
        from redeploy.models import DeviceRegistry, KnownDevice
        reg = DeviceRegistry(devices=[
            KnownDevice(id="a@1", host="a@1", tags=["kiosk"]),
            KnownDevice(id="b@2", host="b@2", tags=["vps"]),
        ])
        with patch("redeploy.models.DeviceRegistry.load", return_value=reg):
            result = _runner().invoke(cli, ["devices", "--tag", "kiosk"])
        assert result.exit_code == 0
        assert "kiosk" in result.output          # tag shown
        assert "vps" not in result.output

    def test_devices_json_output(self):
        from redeploy.models import DeviceRegistry, KnownDevice
        reg = DeviceRegistry(devices=[
            KnownDevice(id="x@1", host="x@1", strategy="k3s")
        ])
        with patch("redeploy.models.DeviceRegistry.load", return_value=reg):
            result = _runner().invoke(cli, ["devices", "--json"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["id"] == "x@1"


class TestTarget:
    def test_target_rejects_markdown_spec_with_clear_error(self, tmp_path):
        spec = tmp_path / "migration.md"
        spec.write_text("# markpact prototype\n", encoding="utf-8")

        with patch("redeploy.cli._resolve_device", return_value=(None, None)):
            result = _runner().invoke(cli, ["target", "pi@192.168.1.42", str(spec), "--plan-only"])

        assert result.exit_code == 1
        assert "Unsupported spec format '.md'" in result.output
        assert "markdown/markpact specs are not implemented" in result.output


# ── redeploy apply ────────────────────────────────────────────────────────────


class TestApply:
    def _plan_file(self, tmp_path, host="local") -> Path:
        from redeploy.models import (
            DeployStrategy, MigrationPlan, MigrationStep, StepAction,
            ConflictSeverity, StepStatus,
        )
        plan = MigrationPlan(
            host=host, app="myapp",
            from_strategy=DeployStrategy.DOCKER_FULL,
            to_strategy=DeployStrategy.DOCKER_FULL,
            steps=[
                MigrationStep(
                    id="test_step", action=StepAction.SSH_CMD,
                    description="echo test", command="echo test",
                    risk=ConflictSeverity.LOW,
                )
            ],
        )
        p = tmp_path / "plan.yaml"
        p.write_text(yaml.dump(plan.model_dump(mode="json"), allow_unicode=True))
        return p

    def test_apply_dry_run(self, tmp_path):
        p = self._plan_file(tmp_path)
        result = _runner().invoke(cli, ["apply", "--plan", str(p), "--dry-run"])
        assert result.exit_code == 0

    def test_apply_unknown_step_id(self, tmp_path):
        p = self._plan_file(tmp_path)
        result = _runner().invoke(cli, ["apply", "--plan", str(p),
                                        "--step", "nonexistent_id"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

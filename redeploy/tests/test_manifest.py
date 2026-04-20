"""Tests for ProjectManifest, EnvironmentConfig, DeviceRegistry, KnownDevice."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from redeploy.models import (
    DeployStrategy,
    DeviceRegistry,
    EnvironmentConfig,
    InfraSpec,
    KnownDevice,
    MigrationSpec,
    ProjectManifest,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _spec() -> MigrationSpec:
    return MigrationSpec(
        name="test",
        source=InfraSpec(host="local", strategy=DeployStrategy.K3S, app="myapp"),
        target=InfraSpec(host="local", strategy=DeployStrategy.DOCKER_FULL, app="myapp"),
    )


def _manifest(**kw) -> ProjectManifest:
    return ProjectManifest(app="myapp", **kw)


# ── ProjectManifest.find_and_load ─────────────────────────────────────────────


class TestFindAndLoad:
    def test_finds_in_cwd(self, tmp_path):
        (tmp_path / "redeploy.yaml").write_text("app: testapp\n")
        m = ProjectManifest.find_and_load(tmp_path)
        assert m is not None
        assert m.app == "testapp"

    def test_finds_in_parent(self, tmp_path):
        (tmp_path / "redeploy.yaml").write_text("app: parentapp\n")
        subdir = tmp_path / "sub"
        subdir.mkdir()
        m = ProjectManifest.find_and_load(subdir)
        assert m is not None
        assert m.app == "parentapp"

    def test_returns_none_when_missing(self, tmp_path):
        m = ProjectManifest.find_and_load(tmp_path)
        assert m is None

    def test_parses_environments(self, tmp_path):
        (tmp_path / "redeploy.yaml").write_text(
            "app: myapp\nenvironments:\n  prod:\n    host: root@1.2.3.4\n"
        )
        m = ProjectManifest.find_and_load(tmp_path)
        assert "prod" in m.environments
        assert m.environments["prod"].host == "root@1.2.3.4"


# ── ProjectManifest.from_dotenv ───────────────────────────────────────────────


class TestFromDotenv:
    def test_reads_deploy_vars(self, tmp_path):
        (tmp_path / ".env").write_text(
            "DEPLOY_HOST=root@10.0.0.1\nDEPLOY_APP=c2004\nDEPLOY_DOMAIN=c2004.example.com\n"
        )
        m = ProjectManifest.from_dotenv(tmp_path)
        assert m is not None
        assert m.host == "root@10.0.0.1"
        assert m.app == "c2004"
        assert m.domain == "c2004.example.com"

    def test_returns_none_without_deploy_vars(self, tmp_path):
        (tmp_path / ".env").write_text("FOO=bar\nBAR=baz\n")
        m = ProjectManifest.from_dotenv(tmp_path)
        assert m is None

    def test_returns_none_when_no_dotenv(self, tmp_path):
        m = ProjectManifest.from_dotenv(tmp_path)
        assert m is None

    def test_strips_quotes(self, tmp_path):
        (tmp_path / ".env").write_text('DEPLOY_HOST="root@1.2.3.4"\n')
        m = ProjectManifest.from_dotenv(tmp_path)
        assert m.host == "root@1.2.3.4"

    def test_skips_comment_lines(self, tmp_path):
        (tmp_path / ".env").write_text("# this is a comment\nDEPLOY_APP=myapp\n")
        m = ProjectManifest.from_dotenv(tmp_path)
        assert m.app == "myapp"

    def test_reads_ssh_key(self, tmp_path):
        (tmp_path / ".env").write_text("DEPLOY_HOST=x\nDEPLOY_SSH_KEY=/root/.ssh/id_ed25519\n")
        m = ProjectManifest.from_dotenv(tmp_path)
        assert m.ssh_key == "/root/.ssh/id_ed25519"


# ── ProjectManifest.resolve_env ───────────────────────────────────────────────


class TestResolveEnv:
    def _manifest_with_envs(self) -> ProjectManifest:
        return ProjectManifest(
            app="myapp",
            host="global@1.2.3.4",
            domain="global.example.com",
            env_file=".env",
            environments={
                "prod": EnvironmentConfig(
                    host="root@87.1.1.1",
                    strategy="docker_full",
                    domain="prod.example.com",
                    env_file="envs/prod.env",
                    verify_url="https://prod.example.com/health",
                ),
                "dev": EnvironmentConfig(
                    host="local",
                    strategy="docker_full",
                    env_file=".env.local",
                    verify_url="http://localhost:8000/health",
                ),
            },
        )

    def test_returns_env_with_overrides(self):
        m = self._manifest_with_envs()
        cfg = m.resolve_env("prod")
        assert cfg.host == "root@87.1.1.1"
        assert cfg.domain == "prod.example.com"
        assert cfg.verify_url == "https://prod.example.com/health"

    def test_falls_back_to_manifest_defaults(self):
        m = self._manifest_with_envs()
        cfg = m.resolve_env("dev")
        assert cfg.host == "local"
        assert cfg.domain == "global.example.com"   # dev has no domain → manifest default

    def test_unknown_env_returns_base(self):
        m = self._manifest_with_envs()
        cfg = m.resolve_env("staging")
        assert cfg.host == "global@1.2.3.4"

    def test_env_file_overridden(self):
        m = self._manifest_with_envs()
        cfg = m.resolve_env("prod")
        assert cfg.env_file == "envs/prod.env"

    def test_global_env_returns_manifest_defaults(self):
        m = self._manifest_with_envs()
        cfg = m.resolve_env("")
        assert cfg.host == "global@1.2.3.4"


# ── ProjectManifest.apply_to_spec ─────────────────────────────────────────────


class TestApplyToSpec:
    def test_sets_host(self):
        m = _manifest(host="root@10.0.0.1")
        s = _spec()
        m.apply_to_spec(s)
        assert s.source.host == "root@10.0.0.1"
        assert s.target.host == "root@10.0.0.1"

    def test_sets_domain_when_unset(self):
        m = _manifest(domain="example.com")
        s = _spec()
        m.apply_to_spec(s)
        assert s.target.domain == "example.com"

    def test_does_not_override_existing_domain(self):
        m = _manifest(domain="example.com")
        s = _spec()
        s.target.domain = "already.set"
        m.apply_to_spec(s)
        assert s.target.domain == "already.set"

    def test_sets_env_file(self):
        m = _manifest(env_file="envs/prod.env")
        s = _spec()
        m.apply_to_spec(s)
        assert s.target.env_file == "envs/prod.env"

    def test_env_name_applied(self):
        m = ProjectManifest(
            app="myapp",
            environments={
                "prod": EnvironmentConfig(
                    host="root@1.2.3.4",
                    strategy="docker_full",
                    verify_url="https://example.com/health",
                )
            },
        )
        s = _spec()
        m.apply_to_spec(s, env_name="prod")
        assert s.source.host == "root@1.2.3.4"
        assert s.target.strategy == DeployStrategy.DOCKER_FULL
        assert s.target.verify_url == "https://example.com/health"

    def test_env_strategy_applied(self):
        m = ProjectManifest(
            app="myapp",
            environments={"rpi5": EnvironmentConfig(
                host="pi@192.168.1.5", strategy="systemd"
            )},
        )
        s = _spec()
        m.apply_to_spec(s, env_name="rpi5")
        assert s.target.strategy == DeployStrategy.SYSTEMD

    def test_invalid_strategy_ignored(self):
        m = ProjectManifest(
            app="myapp",
            environments={"bad": EnvironmentConfig(host="x", strategy="unknown_xyz")},
        )
        s = _spec()
        original = s.target.strategy
        m.apply_to_spec(s, env_name="bad")
        assert s.target.strategy == original


# ── DeviceRegistry ────────────────────────────────────────────────────────────


class TestDeviceRegistry:
    def _reg(self) -> DeviceRegistry:
        return DeviceRegistry(devices=[])

    def _device(self, id="root@10.0.0.1", **kw) -> KnownDevice:
        return KnownDevice(id=id, host=id, **kw)

    def test_get_returns_device(self):
        reg = self._reg()
        d = self._device()
        reg.upsert(d)
        assert reg.get("root@10.0.0.1") is not None

    def test_get_returns_none_for_missing(self):
        reg = self._reg()
        assert reg.get("nobody") is None

    def test_upsert_adds_new(self):
        reg = self._reg()
        reg.upsert(self._device("a@1.2.3.4"))
        reg.upsert(self._device("b@1.2.3.5"))
        assert len(reg.devices) == 2

    def test_upsert_updates_existing(self):
        reg = self._reg()
        reg.upsert(self._device(strategy="k3s"))
        reg.upsert(KnownDevice(id="root@10.0.0.1", host="root@10.0.0.1", strategy="docker_full"))
        assert len(reg.devices) == 1
        assert reg.devices[0].strategy == "docker_full"

    def test_remove(self):
        reg = self._reg()
        reg.upsert(self._device())
        removed = reg.remove("root@10.0.0.1")
        assert removed is True
        assert len(reg.devices) == 0

    def test_remove_missing_returns_false(self):
        reg = self._reg()
        assert reg.remove("nobody") is False

    def test_by_tag(self):
        reg = self._reg()
        reg.upsert(self._device("a@1", tags=["rpi", "local"]))
        reg.upsert(self._device("b@2", tags=["vps"]))
        assert len(reg.by_tag("rpi")) == 1

    def test_by_strategy(self):
        reg = self._reg()
        reg.upsert(self._device("a@1", strategy="k3s"))
        reg.upsert(self._device("b@2", strategy="docker_full"))
        reg.upsert(self._device("c@3", strategy="k3s"))
        assert len(reg.by_strategy("k3s")) == 2

    def test_save_and_load(self, tmp_path):
        reg = self._reg()
        reg.upsert(self._device(tags=["test"]))
        p = tmp_path / "devices.yaml"
        reg.save(p)
        loaded = DeviceRegistry.load(p)
        assert len(loaded.devices) == 1
        assert loaded.devices[0].id == "root@10.0.0.1"

    def test_load_missing_returns_empty(self, tmp_path):
        reg = DeviceRegistry.load(tmp_path / "nofile.yaml")
        assert reg.devices == []


# ── KnownDevice ───────────────────────────────────────────────────────────────


class TestKnownDevice:
    def _device(self, **kw) -> KnownDevice:
        return KnownDevice(id="dev1", host="root@10.0.0.1", **kw)

    def test_is_reachable_recent(self):
        d = self._device(last_seen=datetime.now(timezone.utc))
        assert d.is_reachable is True

    def test_is_reachable_old(self):
        from datetime import timedelta
        old = datetime.now(timezone.utc) - timedelta(seconds=400)
        d = self._device(last_seen=old)
        assert d.is_reachable is False

    def test_is_reachable_none(self):
        d = self._device()
        assert d.is_reachable is False

    def test_last_deploy_none_when_empty(self):
        d = self._device()
        assert d.last_deploy is None

    def test_record_deploy(self):
        from redeploy.models import DeployRecord
        d = self._device()
        d.record_deploy(DeployRecord(spec_name="test", ok=True))
        assert d.last_deploy is not None
        assert d.last_deploy.spec_name == "test"

    def test_record_deploy_capped_at_50(self):
        from redeploy.models import DeployRecord
        d = self._device()
        for i in range(55):
            d.record_deploy(DeployRecord(spec_name=f"r{i}"))
        assert len(d.deploys) == 50
        assert d.deploys[-1].spec_name == "r54"

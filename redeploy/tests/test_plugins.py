"""Tests for redeploy.plugins — PluginRegistry, builtins, auto-discovery."""
from __future__ import annotations

import textwrap
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from redeploy.plugins import (
    PluginContext,
    PluginRegistry,
    register_plugin,
    registry,
    load_user_plugins,
)
from redeploy.models import StepStatus


# ── helpers ───────────────────────────────────────────────────────────────────


def _ctx(params: dict = None, dry_run: bool = False) -> PluginContext:
    step = SimpleNamespace(result=None, status=None, id="test_step", plugin_params={})
    probe = MagicMock()
    return PluginContext(
        step=step,
        host="root@10.0.0.1",
        probe=probe,
        emitter=None,
        params=params or {},
        dry_run=dry_run,
    )


# ── PluginRegistry ────────────────────────────────────────────────────────────


class TestPluginRegistry:
    def test_register_and_get(self):
        reg = PluginRegistry()
        handler = lambda ctx: None
        reg.register("my_plugin", handler)
        assert reg.get("my_plugin") is handler

    def test_get_missing_returns_none(self):
        reg = PluginRegistry()
        reg._loaded_builtins = True  # skip auto-load
        assert reg.get("nonexistent") is None

    def test_names_returns_registered(self):
        reg = PluginRegistry()
        reg._loaded_builtins = True
        reg.register("a", lambda ctx: None)
        reg.register("b", lambda ctx: None)
        assert "a" in reg.names()
        assert "b" in reg.names()

    def test_decorator_syntax(self):
        reg = PluginRegistry()

        @reg("test_action")
        def handler(ctx: PluginContext) -> None:
            ctx.step.result = "done"

        reg._loaded_builtins = True
        assert reg.get("test_action") is handler

    def test_override_logs_debug(self, capfd):
        reg = PluginRegistry()
        reg._loaded_builtins = True
        reg.register("dup", lambda ctx: None)
        reg.register("dup", lambda ctx: None)  # override — should not raise
        assert reg.get("dup") is not None

    def test_load_directory_imports_py_files(self, tmp_path):
        plugin_file = tmp_path / "my_plugin.py"
        plugin_file.write_text(textwrap.dedent("""
            from redeploy.plugins import registry
            def my_handler(ctx): ctx.step.result = "my_plugin"
            registry.register("my_dynamic_plugin", my_handler)
        """))
        reg = PluginRegistry()
        reg._loaded_builtins = True
        count = reg.load_directory(tmp_path)
        assert count == 1
        # Plugin registers into the global registry singleton
        assert registry.get("my_dynamic_plugin") is not None

    def test_load_directory_skips_underscored(self, tmp_path):
        (tmp_path / "_private.py").write_text("raise RuntimeError('should not load')")
        reg = PluginRegistry()
        reg._loaded_builtins = True
        count = reg.load_directory(tmp_path)
        assert count == 0

    def test_load_directory_missing(self, tmp_path):
        reg = PluginRegistry()
        count = reg.load_directory(tmp_path / "nonexistent")
        assert count == 0

    def test_load_directory_bad_syntax_does_not_crash(self, tmp_path):
        (tmp_path / "broken.py").write_text("def (broken syntax")
        reg = PluginRegistry()
        reg._loaded_builtins = True
        count = reg.load_directory(tmp_path)
        assert count == 0


# ── register_plugin decorator ─────────────────────────────────────────────────


class TestRegisterPlugin:
    def test_registers_in_global_registry(self):
        @register_plugin("_test_decorator_plugin")
        def handler(ctx: PluginContext) -> None:
            ctx.step.result = "ok"

        assert registry.get("_test_decorator_plugin") is handler

    def test_handler_callable(self):
        @register_plugin("_test_callable")
        def handler(ctx: PluginContext) -> None:
            ctx.step.result = "called"

        ctx = _ctx()
        handler(ctx)
        assert ctx.step.result == "called"


# ── PluginContext ──────────────────────────────────────────────────────────────


class TestPluginContext:
    def test_fields(self):
        step = SimpleNamespace(id="s1", result=None, status=None)
        probe = MagicMock()
        ctx = PluginContext(step=step, host="pi@10.0.0.1", probe=probe, emitter=None)
        assert ctx.host == "pi@10.0.0.1"
        assert ctx.dry_run is False
        assert ctx.params == {}

    def test_dry_run_default_false(self):
        ctx = _ctx()
        assert ctx.dry_run is False


# ── builtin: browser_reload ───────────────────────────────────────────────────


class TestBrowserReloadPlugin:
    def _get_handler(self):
        from redeploy.plugins.builtin.browser_reload import browser_reload
        return browser_reload

    def test_dry_run_sets_done(self):
        ctx = _ctx(params={"port": 9222}, dry_run=True)
        self._get_handler()(ctx)
        assert ctx.step.status == StepStatus.DONE
        assert "dry" in ctx.step.result

    def test_live_cdp_not_reachable(self):
        from redeploy.apply.executor import StepError

        probe = MagicMock()
        probe.run.return_value = SimpleNamespace(ok=False, out="", stderr="connection refused")
        ctx = _ctx(params={"port": 9222})
        ctx.probe = probe

        with pytest.raises(StepError, match="CDP"):
            self._get_handler()(ctx)

    def test_live_no_tabs(self):
        import json
        from redeploy.apply.executor import StepError

        probe = MagicMock()
        probe.run.return_value = SimpleNamespace(ok=True, out="[]", stderr="")
        ctx = _ctx(params={"port": 9222})
        ctx.probe = probe

        with pytest.raises(StepError, match="No page tabs"):
            self._get_handler()(ctx)

    def test_live_reload_success(self):
        import json

        tabs = [{"id": "abc123", "type": "page", "url": "http://localhost:8080"}]
        probe = MagicMock()
        # First call: /json listing; subsequent calls: reload script
        probe.run.side_effect = [
            SimpleNamespace(ok=True, out=json.dumps(tabs), stderr=""),
            SimpleNamespace(ok=True, out="ok", stderr=""),
        ]
        ctx = _ctx(params={"port": 9222})
        ctx.probe = probe

        self._get_handler()(ctx)
        assert ctx.step.status == StepStatus.DONE
        assert "reloaded" in ctx.step.result


# ── builtin: systemd_reload ───────────────────────────────────────────────────


class TestSystemdReloadPlugin:
    def _get_handler(self):
        from redeploy.plugins.builtin.systemd_reload import systemd_reload
        return systemd_reload

    def test_dry_run(self):
        ctx = _ctx(params={"units": ["myapp.service"]}, dry_run=True)
        self._get_handler()(ctx)
        assert ctx.step.status == StepStatus.DONE
        assert "dry" in ctx.step.result

    def test_daemon_reload_failure_raises(self):
        from redeploy.apply.executor import StepError

        probe = MagicMock()
        probe.run.return_value = SimpleNamespace(ok=False, out="", stderr="Access denied")
        ctx = _ctx(params={"units": ["myapp.service"], "wait_active": False})
        ctx.probe = probe

        with pytest.raises(StepError, match="daemon-reload"):
            self._get_handler()(ctx)

    def test_restart_success_no_wait(self):
        probe = MagicMock()
        probe.run.return_value = SimpleNamespace(ok=True, out="", stderr="")
        ctx = _ctx(params={
            "units": ["myapp.service"],
            "daemon_reload": True,
            "wait_active": False,
        })
        ctx.probe = probe

        self._get_handler()(ctx)
        assert ctx.step.status == StepStatus.DONE
        assert "myapp.service" in ctx.step.result

    def test_units_as_comma_string(self):
        probe = MagicMock()
        probe.run.return_value = SimpleNamespace(ok=True, out="", stderr="")
        ctx = _ctx(params={
            "units": "svc-a.service, svc-b.service",
            "wait_active": False,
        })
        ctx.probe = probe

        self._get_handler()(ctx)
        assert "svc-a.service" in ctx.step.result
        assert "svc-b.service" in ctx.step.result

    def test_wait_active_polls_until_active(self):
        probe = MagicMock()
        # daemon-reload + restart + is-active (activating) + is-active (active)
        probe.run.side_effect = [
            SimpleNamespace(ok=True, out="", stderr=""),        # daemon-reload
            SimpleNamespace(ok=True, out="", stderr=""),        # restart
            SimpleNamespace(ok=True, out="activating", stderr=""),  # poll 1
            SimpleNamespace(ok=True, out="active", stderr=""),      # poll 2
        ]
        ctx = _ctx(params={
            "units": ["myapp.service"],
            "wait_active": True,
            "wait_timeout": 10,
        })
        ctx.probe = probe

        with patch("time.sleep"):
            self._get_handler()(ctx)

        assert ctx.step.status == StepStatus.DONE

    def test_wait_active_timeout_raises(self):
        from redeploy.apply.executor import StepError
        import time as _time

        probe = MagicMock()
        probe.run.return_value = SimpleNamespace(ok=True, out="activating", stderr="")

        ctx = _ctx(params={
            "units": ["slow.service"],
            "wait_active": True,
            "wait_timeout": 1,
        })
        ctx.probe = probe

        with pytest.raises(StepError, match="did not become active"):
            self._get_handler()(ctx)


# ── builtin: notify ───────────────────────────────────────────────────────────


class TestNotifyPlugin:
    def _get_handler(self):
        from redeploy.plugins.builtin.notify import notify
        return notify

    def test_dry_run(self):
        ctx = _ctx(params={"backend": "slack", "webhook_url": "http://x"}, dry_run=True)
        self._get_handler()(ctx)
        assert ctx.step.status == StepStatus.DONE
        assert "dry" in ctx.step.result

    def test_unknown_backend_raises(self):
        from redeploy.apply.executor import StepError

        ctx = _ctx(params={"backend": "telegram"})
        with pytest.raises(StepError, match="unknown notify backend"):
            self._get_handler()(ctx)

    def test_slack_missing_webhook_raises(self):
        from redeploy.apply.executor import StepError

        ctx = _ctx(params={"backend": "slack"})
        with pytest.raises(StepError, match="webhook_url"):
            self._get_handler()(ctx)

    def test_webhook_missing_url_raises(self):
        from redeploy.apply.executor import StepError

        ctx = _ctx(params={"backend": "webhook"})
        with pytest.raises(StepError, match="requires url"):
            self._get_handler()(ctx)

    def test_slack_success(self):
        ctx = _ctx(params={
            "backend": "slack",
            "webhook_url": "https://hooks.slack.com/test",
            "message": "deployed {app} to {env}",
            "app": "c2004",
            "env": "prod",
        })
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.status = 200
            mock_open.return_value = mock_resp
            self._get_handler()(ctx)

        assert ctx.step.status == StepStatus.DONE
        assert "slack" in ctx.step.result

    def test_webhook_post_success(self):
        ctx = _ctx(params={
            "backend": "webhook",
            "url": "https://ops.example.com/hooks/deploy",
            "payload": {"event": "deploy", "app": "c2004"},
        })
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.status = 200
            mock_open.return_value = mock_resp
            self._get_handler()(ctx)

        assert ctx.step.status == StepStatus.DONE

    def test_env_var_expansion(self, monkeypatch):
        monkeypatch.setenv("TEST_WEBHOOK_URL", "https://hooks.example.com/test")
        ctx = _ctx(params={
            "backend": "slack",
            "webhook_url": "$TEST_WEBHOOK_URL",
            "message": "test",
        })
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.status = 200
            mock_open.return_value = mock_resp
            self._get_handler()(ctx)
        assert ctx.step.status == StepStatus.DONE


# ── builtins auto-loaded ──────────────────────────────────────────────────────


class TestBuiltinsAutoLoaded:
    def test_browser_reload_in_registry(self):
        assert registry.get("browser_reload") is not None

    def test_systemd_reload_in_registry(self):
        assert registry.get("systemd_reload") is not None

    def test_notify_in_registry(self):
        assert registry.get("notify") is not None

    def test_names_include_builtins(self):
        names = registry.names()
        assert "browser_reload" in names
        assert "systemd_reload" in names
        assert "notify" in names


# ── load_user_plugins ─────────────────────────────────────────────────────────


def test_load_user_plugins_empty_dirs(tmp_path):
    """load_user_plugins returns 0 when no plugin dirs exist."""
    with patch("redeploy.plugins.Path.cwd", return_value=tmp_path):
        with patch("redeploy.plugins.Path.home", return_value=tmp_path):
            n = load_user_plugins()
    assert n == 0

"""Tests for redeploy.observe — DeployAuditLog, AuditEntry, DeployReport."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import redeploy
from redeploy.observe import AuditEntry, DeployAuditLog, DeployReport
from redeploy.models import (
    DeployStrategy, InfraState, MigrationPlan, MigrationStep,
    StepAction, StepStatus,
)


# ── fixtures ──────────────────────────────────────────────────────────────────


def _plan(host="root@1.2.3.4", app="myapp"):
    return MigrationPlan(
        host=host, app=app,
        from_strategy=DeployStrategy.K3S,
        to_strategy=DeployStrategy.DOCKER_FULL,
    )


def _step(id="s1", status=StepStatus.DONE):
    s = MigrationStep(id=id, action=StepAction.SSH_CMD,
                      description="test", command="echo ok")
    s.status = status
    s.result = "ok" if status == StepStatus.DONE else None
    return s


# ── AuditEntry ────────────────────────────────────────────────────────────────


class TestAuditEntry:
    def _entry(self, **kw):
        data = {
            "ts": "2026-04-20T12:00:00+00:00",
            "host": "root@1.2.3.4",
            "app": "myapp",
            "from_strategy": "k3s",
            "to_strategy": "docker_full",
            "ok": True,
            "dry_run": False,
            "elapsed_s": 12.5,
            "steps_total": 3,
            "steps_ok": 3,
            "steps_failed": 0,
            "steps": [],
            **kw,
        }
        return AuditEntry(data)

    def test_accessors_ok(self):
        e = self._entry()
        assert e.host == "root@1.2.3.4"
        assert e.app == "myapp"
        assert e.from_strategy == "k3s"
        assert e.to_strategy == "docker_full"
        assert e.ok is True
        assert e.dry_run is False
        assert e.elapsed_s == pytest.approx(12.5)
        assert e.steps_total == 3
        assert e.steps_ok == 3
        assert e.steps_failed == 0

    def test_accessor_failed(self):
        e = self._entry(ok=False, steps_failed=1, error="[s2] boom")
        assert e.ok is False
        assert e.steps_failed == 1
        assert e.error == "[s2] boom"

    def test_pattern_none(self):
        assert self._entry().pattern is None

    def test_pattern_set(self):
        e = self._entry(pattern="blue_green")
        assert e.pattern == "blue_green"

    def test_to_dict_roundtrip(self):
        e = self._entry()
        d = e.to_dict()
        assert d["host"] == "root@1.2.3.4"
        assert AuditEntry(d).host == "root@1.2.3.4"

    def test_repr_ok(self):
        r = repr(self._entry())
        assert "ok" in r
        assert "myapp" in r

    def test_repr_fail(self):
        r = repr(self._entry(ok=False))
        assert "FAIL" in r


# ── DeployAuditLog ────────────────────────────────────────────────────────────


class TestDeployAuditLog:
    def _log(self, tmp_path):
        return DeployAuditLog(path=tmp_path / "audit.jsonl")

    def test_empty_load(self, tmp_path):
        log = self._log(tmp_path)
        assert log.load() == []

    def test_record_creates_file(self, tmp_path):
        log = self._log(tmp_path)
        plan = _plan()
        plan.steps = [_step()]
        entry = log.record(plan, [_step()], ok=True, elapsed_s=1.5)
        assert log.path.exists()
        assert isinstance(entry, AuditEntry)

    def test_record_ok_entry(self, tmp_path):
        log = self._log(tmp_path)
        plan = _plan()
        plan.steps = [_step("s1"), _step("s2")]
        entry = log.record(plan, [_step("s1"), _step("s2")], ok=True, elapsed_s=5.0)
        assert entry.ok is True
        assert entry.host == "root@1.2.3.4"
        assert entry.app == "myapp"
        assert entry.elapsed_s == pytest.approx(5.0)
        assert entry.steps_total == 2
        assert entry.steps_ok == 2

    def test_record_failed_entry(self, tmp_path):
        log = self._log(tmp_path)
        plan = _plan()
        s1 = _step("s1", StepStatus.DONE)
        s2 = _step("s2", StepStatus.FAILED)
        s2.error = "exit=1: bad"
        plan.steps = [s1, s2]
        entry = log.record(plan, [s1], ok=False, elapsed_s=3.0)
        assert entry.ok is False
        assert entry.steps_ok == 1
        assert entry.steps_failed == 1

    def test_record_dry_run(self, tmp_path):
        log = self._log(tmp_path)
        plan = _plan()
        plan.steps = [_step()]
        entry = log.record(plan, [_step()], ok=True, elapsed_s=0.1, dry_run=True)
        assert entry.dry_run is True

    def test_load_after_record(self, tmp_path):
        log = self._log(tmp_path)
        plan = _plan()
        plan.steps = [_step()]
        log.record(plan, [_step()], ok=True, elapsed_s=1.0)
        log.record(plan, [_step()], ok=False, elapsed_s=2.0)
        entries = log.load()
        assert len(entries) == 2
        assert entries[0].ok is True
        assert entries[1].ok is False

    def test_tail(self, tmp_path):
        log = self._log(tmp_path)
        plan = _plan()
        plan.steps = [_step()]
        for _ in range(5):
            log.record(plan, [_step()], ok=True, elapsed_s=1.0)
        assert len(log.tail(3)) == 3
        assert len(log.tail(10)) == 5

    def test_filter_by_ok(self, tmp_path):
        log = self._log(tmp_path)
        plan = _plan()
        plan.steps = [_step()]
        log.record(plan, [_step()], ok=True, elapsed_s=1.0)
        log.record(plan, [], ok=False, elapsed_s=1.0)
        assert len(log.filter(ok=True)) == 1
        assert len(log.filter(ok=False)) == 1

    def test_filter_by_host(self, tmp_path):
        log = self._log(tmp_path)
        plan_a = _plan(host="root@1.1.1.1")
        plan_b = _plan(host="root@2.2.2.2")
        plan_a.steps = plan_b.steps = [_step()]
        log.record(plan_a, [_step()], ok=True, elapsed_s=1.0)
        log.record(plan_b, [_step()], ok=True, elapsed_s=1.0)
        assert len(log.filter(host="1.1.1.1")) == 1
        assert len(log.filter(host="2.2.2.2")) == 1

    def test_filter_by_app(self, tmp_path):
        log = self._log(tmp_path)
        plan_a = _plan(app="app1")
        plan_b = _plan(app="app2")
        plan_a.steps = plan_b.steps = [_step()]
        log.record(plan_a, [_step()], ok=True, elapsed_s=1.0)
        log.record(plan_b, [_step()], ok=True, elapsed_s=1.0)
        assert len(log.filter(app="app1")) == 1

    def test_filter_by_since(self, tmp_path):
        log = self._log(tmp_path)
        plan = _plan()
        plan.steps = [_step()]
        log.record(plan, [_step()], ok=True, elapsed_s=1.0)
        future = datetime(2099, 1, 1, tzinfo=timezone.utc)
        assert log.filter(since=future) == []

    def test_clear(self, tmp_path):
        log = self._log(tmp_path)
        plan = _plan()
        plan.steps = [_step()]
        log.record(plan, [_step()], ok=True, elapsed_s=1.0)
        assert len(log.load()) == 1
        log.clear()
        assert log.load() == []

    def test_file_is_jsonl(self, tmp_path):
        log = self._log(tmp_path)
        plan = _plan()
        plan.steps = [_step()]
        log.record(plan, [_step()], ok=True, elapsed_s=1.0)
        log.record(plan, [_step()], ok=True, elapsed_s=2.0)
        lines = [l for l in log.path.read_text().splitlines() if l.strip()]
        assert len(lines) == 2
        for line in lines:
            d = json.loads(line)
            assert "ts" in d
            assert "host" in d

    def test_corrupt_line_skipped(self, tmp_path):
        log = self._log(tmp_path)
        plan = _plan()
        plan.steps = [_step()]
        log.record(plan, [_step()], ok=True, elapsed_s=1.0)
        with log.path.open("a") as f:
            f.write("NOT JSON\n")
        assert len(log.load()) == 1  # corrupt line silently skipped

    def test_creates_parent_dirs(self, tmp_path):
        log = DeployAuditLog(path=tmp_path / "deep" / "nested" / "audit.jsonl")
        plan = _plan()
        plan.steps = [_step()]
        log.record(plan, [_step()], ok=True, elapsed_s=1.0)
        assert log.path.exists()


# ── DeployReport ──────────────────────────────────────────────────────────────


class TestDeployReport:
    def _entry(self, ok=True):
        return AuditEntry({
            "ts": "2026-04-20T12:00:00+00:00",
            "host": "root@1.2.3.4",
            "app": "myapp",
            "from_strategy": "k3s",
            "to_strategy": "docker_full",
            "ok": ok,
            "dry_run": False,
            "elapsed_s": 8.3,
            "steps_total": 3,
            "steps_ok": 3 if ok else 2,
            "steps_failed": 0 if ok else 1,
            "steps": [
                {"id": "s1", "action": "ssh_cmd", "status": "done", "result": "ok", "error": None},
                {"id": "s2", "action": "http_check", "status": "done" if ok else "failed",
                 "result": None, "error": None if ok else "connection refused"},
                {"id": "s3", "action": "wait", "status": "done", "result": None, "error": None},
            ],
        })

    def test_text_contains_host(self):
        report = DeployReport(self._entry())
        assert "root@1.2.3.4" in report.text()

    def test_text_contains_result_success(self):
        assert "SUCCESS" in DeployReport(self._entry(ok=True)).text()

    def test_text_contains_result_failed(self):
        assert "FAILED" in DeployReport(self._entry(ok=False)).text()

    def test_text_contains_step_ids(self):
        t = DeployReport(self._entry()).text()
        assert "s1" in t
        assert "s2" in t
        assert "s3" in t

    def test_text_shows_strategy(self):
        t = DeployReport(self._entry()).text()
        assert "k3s" in t
        assert "docker_full" in t

    def test_text_elapsed(self):
        assert "8.3" in DeployReport(self._entry()).text()

    def test_text_pattern_shown(self):
        e = AuditEntry({**self._entry().to_dict(), "pattern": "blue_green"})
        assert "blue_green" in DeployReport(e).text()

    def test_text_no_pattern_line_when_none(self):
        t = DeployReport(self._entry()).text()
        assert "pattern" not in t

    def test_yaml_output(self):
        y = DeployReport(self._entry()).yaml()
        assert "host:" in y
        assert "myapp" in y

    def test_summary_line_ok(self):
        s = DeployReport(self._entry(ok=True)).summary_line()
        assert "[ok]" in s
        assert "myapp" in s

    def test_summary_line_fail(self):
        s = DeployReport(self._entry(ok=False)).summary_line()
        assert "[FAIL]" in s

    def test_dry_run_in_text(self):
        e = AuditEntry({**self._entry().to_dict(), "dry_run": True})
        assert "DRY RUN" in DeployReport(e).text()


# ── public API smoke ──────────────────────────────────────────────────────────


def test_public_api_all_importable():
    for name in ["AuditEntry", "DeployAuditLog", "DeployReport"]:
        assert hasattr(redeploy, name)


def test_executor_writes_audit(tmp_path):
    """Executor.run() auto-writes audit entry (dry_run, no real SSH needed)."""
    from redeploy.models import RuntimeInfo
    state = InfraState(
        host="local", app="testapp",
        runtime=RuntimeInfo(docker="24.0"),
        detected_strategy=DeployStrategy.DOCKER_FULL,
    )
    target = redeploy.TargetConfig(
        strategy="docker_full", app="testapp", remote_dir="~/testapp",
    )
    plan = redeploy.Planner(state, target).run()
    audit_path = tmp_path / "audit.jsonl"
    executor = redeploy.Executor(plan, dry_run=True,
                                 audit_log=True, audit_path=audit_path)
    ok = executor.run()
    assert ok is True
    assert audit_path.exists()
    entries = DeployAuditLog(path=audit_path).load()
    assert len(entries) == 1
    assert entries[0].app == "testapp"
    assert entries[0].dry_run is True
    assert entries[0].ok is True


def test_executor_audit_disabled(tmp_path):
    """audit_log=False — no file written."""
    from redeploy.models import RuntimeInfo
    state = InfraState(
        host="local", app="testapp",
        runtime=RuntimeInfo(docker="24.0"),
        detected_strategy=DeployStrategy.DOCKER_FULL,
    )
    target = redeploy.TargetConfig(strategy="docker_full", app="testapp")
    plan = redeploy.Planner(state, target).run()
    audit_path = tmp_path / "audit.jsonl"
    executor = redeploy.Executor(plan, dry_run=True,
                                 audit_log=False, audit_path=audit_path)
    executor.run()
    assert not audit_path.exists()

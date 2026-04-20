"""Tests for apply/state.py and Executor resume integration."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from redeploy.apply.executor import Executor
from redeploy.apply.state import (
    ResumeState,
    default_state_path,
    state_key,
)
from redeploy.models import (
    ConflictSeverity,
    DeployStrategy,
    MigrationPlan,
    MigrationStep,
    StepAction,
    StepStatus,
)


# ── helpers ──────────────────────────────────────────────────────────────────


def _step(sid: str, command: str = "echo ok") -> MigrationStep:
    return MigrationStep(
        id=sid,
        action=StepAction.SSH_CMD,
        description=f"step {sid}",
        command=command,
    )


def _plan(steps: list[MigrationStep]) -> MigrationPlan:
    return MigrationPlan(
        host="local",
        app="testapp",
        from_strategy=DeployStrategy.DOCKER_FULL,
        to_strategy=DeployStrategy.DOCKER_FULL,
        risk=ConflictSeverity.LOW,
        steps=steps,
        notes=[],
    )


def _make_executor(plan: MigrationPlan, *, state_path: Path,
                   resume: bool = False, from_step: str | None = None,
                   fail_on: str | None = None) -> Executor:
    exc = Executor(
        plan,
        ssh_key=None,
        progress_yaml=False,
        audit_log=False,
        resume=resume,
        from_step=from_step,
        state_path=state_path,
        spec_path="spec.yaml",
    )
    exc.probe = MagicMock()

    def fake_run(cmd, timeout=300):
        r = MagicMock()
        if fail_on and fail_on in cmd:
            r.ok = False
            r.exit_code = 1
            r.stderr = "boom"
            r.out = ""
        else:
            r.ok = True
            r.exit_code = 0
            r.stderr = ""
            r.out = "ok"
        return r

    exc.probe.run.side_effect = fake_run
    exc.probe.is_local = True
    return exc


# ── state_key / default_state_path ───────────────────────────────────────────


class TestStateKey:
    def test_stable_for_same_inputs(self):
        assert state_key("x.yaml", "host") == state_key("x.yaml", "host")

    def test_changes_with_host(self):
        assert state_key("x.yaml", "a") != state_key("x.yaml", "b")

    def test_changes_with_path(self):
        assert state_key("a.yaml", "h") != state_key("b.yaml", "h")

    def test_path_safe(self):
        key = state_key("/weird path/with*chars.yaml", "user@host:22")
        # Should not contain any path-traversal-ish chars beyond - . _
        for ch in key:
            assert ch.isalnum() or ch in "-._"

    def test_default_state_path_uses_default_dir(self):
        p = default_state_path("migration.yaml", "pi@rpi5")
        assert p.parent.name == "state"
        assert p.parent.parent.name == ".redeploy"
        assert p.suffix == ".yaml"


# ── ResumeState IO ───────────────────────────────────────────────────────────


class TestResumeStateIO:
    def test_load_or_new_creates_when_missing(self, tmp_path):
        p = tmp_path / "ck.yaml"
        st = ResumeState.load_or_new(p, spec_path="s.yaml", host="h", total_steps=4)
        assert st.completed_count == 0
        assert st.total_steps == 4
        assert st.path == p
        assert not p.exists()  # no save until first checkpoint

    def test_mark_done_persists(self, tmp_path):
        p = tmp_path / "ck.yaml"
        st = ResumeState.load_or_new(p, spec_path="s", host="h", total_steps=2)
        st.mark_done("step1")
        assert p.exists()
        reloaded = ResumeState.load(p)
        assert reloaded.completed_step_ids == ["step1"]
        assert reloaded.failed_step_id is None

    def test_mark_done_idempotent(self, tmp_path):
        p = tmp_path / "ck.yaml"
        st = ResumeState.load_or_new(p, total_steps=1)
        st.mark_done("a")
        st.mark_done("a")
        assert st.completed_step_ids == ["a"]

    def test_mark_failed_records_error(self, tmp_path):
        p = tmp_path / "ck.yaml"
        st = ResumeState.load_or_new(p, total_steps=2)
        st.mark_done("ok")
        st.mark_failed("bad", "exit=1")
        reloaded = ResumeState.load(p)
        assert reloaded.failed_step_id == "bad"
        assert reloaded.failed_error == "exit=1"
        assert reloaded.completed_step_ids == ["ok"]

    def test_remove_deletes_file(self, tmp_path):
        p = tmp_path / "ck.yaml"
        st = ResumeState.load_or_new(p, total_steps=1)
        st.mark_done("a")
        assert p.exists()
        st.remove()
        assert not p.exists()

    def test_remove_when_missing_is_safe(self, tmp_path):
        st = ResumeState(path=tmp_path / "missing.yaml")
        st.remove()  # no exception

    def test_save_atomic(self, tmp_path):
        # Two saves in a row produce a valid YAML each time, no .tmp leftovers.
        p = tmp_path / "ck.yaml"
        st = ResumeState.load_or_new(p, total_steps=3)
        st.mark_done("a")
        st.mark_done("b")
        leftovers = [f for f in p.parent.iterdir() if f.name.startswith(".state-")]
        assert leftovers == []
        assert ResumeState.load(p).completed_step_ids == ["a", "b"]


# ── Executor checkpointing ───────────────────────────────────────────────────


class TestExecutorCheckpoint:
    def test_writes_checkpoint_after_each_success(self, tmp_path):
        plan = _plan([_step("s1"), _step("s2"), _step("s3")])
        sp = tmp_path / "ck.yaml"
        exc = _make_executor(plan, state_path=sp)
        assert exc.run() is True
        # On success, checkpoint is removed.
        assert not sp.exists()

    def test_checkpoint_persists_on_failure(self, tmp_path):
        plan = _plan([_step("s1"), _step("s2", "boom-here"), _step("s3")])
        sp = tmp_path / "ck.yaml"
        exc = _make_executor(plan, state_path=sp, fail_on="boom-here")
        assert exc.run() is False
        assert sp.exists()
        st = ResumeState.load(sp)
        assert st.completed_step_ids == ["s1"]
        assert st.failed_step_id == "s2"
        assert "boom" in (st.failed_error or "")

    def test_resume_skips_completed_and_runs_remainder(self, tmp_path):
        plan = _plan([_step("s1"), _step("s2", "boom-here"), _step("s3")])
        sp = tmp_path / "ck.yaml"
        # First run: fails at s2
        first = _make_executor(plan, state_path=sp, fail_on="boom-here")
        assert first.run() is False
        assert sp.exists()

        # Second run: same spec, no failure injected, with --resume
        plan2 = _plan([_step("s1"), _step("s2"), _step("s3")])
        second = _make_executor(plan2, state_path=sp, resume=True)
        assert second.run() is True

        # s1 was skipped, s2 + s3 ran.
        assert plan2.steps[0].status == StepStatus.SKIPPED
        assert plan2.steps[0].result and "previously completed" in plan2.steps[0].result
        assert plan2.steps[1].status == StepStatus.DONE
        assert plan2.steps[2].status == StepStatus.DONE
        # On success, checkpoint is gone.
        assert not sp.exists()
        # probe.run was called only for s2 + s3.
        executed_cmds = [c.args[0] for c in second.probe.run.call_args_list]
        assert all("echo ok" in cmd for cmd in executed_cmds)
        assert len(executed_cmds) == 2

    def test_from_step_skips_earlier_steps(self, tmp_path):
        plan = _plan([_step("s1"), _step("s2"), _step("s3")])
        sp = tmp_path / "ck.yaml"
        exc = _make_executor(plan, state_path=sp, from_step="s2")
        assert exc.run() is True
        assert plan.steps[0].status == StepStatus.SKIPPED
        assert plan.steps[1].status == StepStatus.DONE
        assert plan.steps[2].status == StepStatus.DONE
        assert exc.probe.run.call_count == 2

    def test_from_step_unknown_runs_full_plan(self, tmp_path):
        plan = _plan([_step("s1"), _step("s2")])
        sp = tmp_path / "ck.yaml"
        exc = _make_executor(plan, state_path=sp, from_step="nonexistent")
        assert exc.run() is True
        assert plan.steps[0].status == StepStatus.DONE
        assert plan.steps[1].status == StepStatus.DONE

    def test_resume_without_checkpoint_runs_all(self, tmp_path):
        plan = _plan([_step("s1"), _step("s2")])
        sp = tmp_path / "ck.yaml"
        exc = _make_executor(plan, state_path=sp, resume=True)
        assert exc.run() is True
        assert plan.steps[0].status == StepStatus.DONE
        assert plan.steps[1].status == StepStatus.DONE
        assert not sp.exists()  # cleaned up after success

    def test_dry_run_does_not_touch_state(self, tmp_path):
        plan = _plan([_step("s1")])
        sp = tmp_path / "ck.yaml"
        exc = Executor(
            plan,
            dry_run=True,
            audit_log=False,
            state_path=sp,
            spec_path="spec.yaml",
        )
        exc.probe = MagicMock()
        assert exc.run() is True
        assert exc.state is None
        assert not sp.exists()

    def test_rollback_clears_rolled_back_steps(self, tmp_path):
        # s1 has rollback_command; s2 fails; rollback should drop s1 from state.
        s1 = _step("s1")
        s1.rollback_command = "echo undo-s1"
        plan = _plan([s1, _step("s2", "boom-here")])
        sp = tmp_path / "ck.yaml"
        exc = _make_executor(plan, state_path=sp, fail_on="boom-here")
        assert exc.run() is False
        st = ResumeState.load(sp)
        # s1 was rolled back -> should NOT appear in completed list anymore.
        assert "s1" not in st.completed_step_ids
        assert st.failed_step_id == "s2"

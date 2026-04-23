"""Tests for apply/executor.py — Executor, StepError, rollback, all handlers."""
from __future__ import annotations

from unittest.mock import MagicMock, patch, call
import subprocess

import pytest

from redeploy.apply.executor import Executor, StepError
from redeploy.models import (
    ConflictSeverity,
    DeployStrategy,
    MigrationPlan,
    MigrationStep,
    StepAction,
    StepStatus,
)


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_step(
    step_id: str,
    action: StepAction = StepAction.SSH_CMD,
    command: str = "echo ok",
    **kwargs,
) -> MigrationStep:
    return MigrationStep(
        id=step_id,
        action=action,
        description=f"step {step_id}",
        command=command,
        **kwargs,
    )


def _make_plan(steps: list[MigrationStep], host: str = "local") -> MigrationPlan:
    return MigrationPlan(
        host=host,
        app="testapp",
        from_strategy=DeployStrategy.DOCKER_FULL,
        to_strategy=DeployStrategy.DOCKER_FULL,
        risk=ConflictSeverity.LOW,
        steps=steps,
        notes=[],
    )


def _executor(plan: MigrationPlan, dry_run: bool = False) -> Executor:
    exc = Executor(plan, dry_run=dry_run)
    # replace probe with a mock that always succeeds
    exc.probe = MagicMock()
    ok = MagicMock()
    ok.ok = True
    ok.out = "ok"
    ok.stderr = ""
    ok.exit_code = 0
    exc.probe.run.return_value = ok
    exc.probe.is_local = True
    return exc


# ── dry_run ───────────────────────────────────────────────────────────────────


class TestDryRun:
    def test_dry_run_returns_true(self):
        plan = _make_plan([_make_step("s1"), _make_step("s2")])
        exc = _executor(plan, dry_run=True)
        assert exc.run() is True

    def test_dry_run_marks_steps_done(self):
        plan = _make_plan([_make_step("s1"), _make_step("s2")])
        exc = _executor(plan, dry_run=True)
        exc.run()
        for step in plan.steps:
            assert step.status == StepStatus.DONE
            assert step.result == "dry-run"

    def test_dry_run_does_not_call_probe(self):
        plan = _make_plan([_make_step("s1")])
        exc = _executor(plan, dry_run=True)
        exc.run()
        exc.probe.run.assert_not_called()


# ── run / step dispatch ───────────────────────────────────────────────────────


class TestExecutorRun:
    def test_all_steps_pass(self):
        plan = _make_plan([_make_step("a"), _make_step("b"), _make_step("c")])
        exc = _executor(plan)
        assert exc.run() is True
        for step in plan.steps:
            assert step.status == StepStatus.DONE

    def test_step_failure_stops_execution(self):
        steps = [_make_step("ok1"), _make_step("bad"), _make_step("ok2")]
        plan = _make_plan(steps)
        exc = _executor(plan)

        def _fail_on_bad(cmd, timeout=300):
            r = MagicMock()
            r.ok = "ok2" not in cmd
            r.out = ""
            r.stderr = "error"
            r.returncode = 1
            return r

        # make "bad" step fail
        call_count = {"n": 0}

        def _side(cmd, timeout=300):
            call_count["n"] += 1
            r = MagicMock()
            r.ok = call_count["n"] != 2   # fail on 2nd call
            r.out = "out"
            r.stderr = "oops"
            r.returncode = 0 if r.ok else 1
            return r

        exc.probe.run.side_effect = _side
        result = exc.run()
        assert result is False
        assert plan.steps[1].status == StepStatus.FAILED

    def test_unknown_action_raises_step_error(self):
        step = _make_step("x")
        step.action = MagicMock()
        step.action.value = "nonexistent_action"
        plan = _make_plan([step])
        exc = _executor(plan)
        # dispatch returns None for unknown action
        with patch.object(exc, "_execute_step", side_effect=StepError(step, "No handler")):
            result = exc.run()
        assert result is False

    def test_summary_all_done(self):
        plan = _make_plan([_make_step("a"), _make_step("b")])
        exc = _executor(plan, dry_run=True)
        exc.run()
        summary = exc.summary()
        assert "2/2" in summary
        assert "✅" in summary

    def test_summary_with_failure(self):
        step = _make_step("fail")
        plan = _make_plan([step])
        exc = _executor(plan)

        fail_r = MagicMock()
        fail_r.ok = False
        fail_r.out = ""
        fail_r.stderr = "error"
        fail_r.returncode = 1
        exc.probe.run.return_value = fail_r

        exc.run()
        summary = exc.summary()
        assert "❌" in summary
        assert "failed" in summary


# ── _run_ssh ──────────────────────────────────────────────────────────────────


class TestRunSsh:
    def test_success(self):
        step = _make_step("ssh1", command="echo hello")
        plan = _make_plan([step])
        exc = _executor(plan)
        exc.probe.run.return_value.out = "hello"
        exc.run()
        assert step.status == StepStatus.DONE

    def test_no_command_raises(self):
        step = _make_step("ssh_no_cmd", command="")
        step.command = None
        plan = _make_plan([step])
        exc = _executor(plan)
        result = exc.run()
        assert result is False
        assert step.status == StepStatus.FAILED

    def test_result_stored(self):
        step = _make_step("ssh2", command="echo res")
        plan = _make_plan([step])
        exc = _executor(plan)
        exc.probe.run.return_value.out = "result_value"
        exc.run()
        assert "result_value" in step.result

    def test_uses_step_timeout(self):
        step = _make_step("ssh_timeout", command="echo long", timeout=1234)
        plan = _make_plan([step])
        exc = _executor(plan)
        exc.run()
        assert exc.probe.run.call_args.kwargs["timeout"] == 1234


# ── _run_scp ──────────────────────────────────────────────────────────────────


class TestRunScp:
    def test_local_scp_uses_cp(self):
        step = _make_step("scp1", action=StepAction.SCP, command=None, src="/a/b", dst="/c/d")
        plan = _make_plan([step])
        exc = _executor(plan)
        exc.probe.is_local = True
        with patch("subprocess.run") as mock_run, patch("pathlib.Path.mkdir"):
            mock_run.return_value = MagicMock(returncode=0)
            exc.run()
        assert mock_run.called
        args = mock_run.call_args[0][0]
        assert args[0] == "cp"

    def test_remote_scp(self):
        step = _make_step("scp2", action=StepAction.SCP, command=None, src="./local", dst="~/remote")
        plan = _make_plan([step], host="user@host")
        exc = _executor(plan)
        exc.probe.is_local = False
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            exc.run()
        args = mock_run.call_args[0][0]
        assert "scp" in args

    def test_scp_missing_src_fails(self):
        step = _make_step("scp3", action=StepAction.SCP, command=None, src=None, dst="~/remote")
        plan = _make_plan([step])
        exc = _executor(plan)
        result = exc.run()
        assert result is False

    def test_scp_failure_propagates(self):
        step = _make_step("scp4", action=StepAction.SCP, command=None, src="x", dst="y")
        plan = _make_plan([step])
        exc = _executor(plan)
        exc.probe.is_local = True
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="Permission denied")
            result = exc.run()
        assert result is False


# ── _run_rsync ────────────────────────────────────────────────────────────────


class TestRunRsync:
    def test_local_rsync(self):
        step = _make_step("rsync1", action=StepAction.RSYNC, command=None, src="./src/", dst="./dst/")
        plan = _make_plan([step])
        exc = _executor(plan)
        exc.probe.is_local = True
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            exc.run()
        args = mock_run.call_args[0][0]
        assert "rsync" in args
        assert "./dst/" in args

    def test_remote_rsync_prefixes_host(self):
        step = _make_step("rsync2", action=StepAction.RSYNC, command=None, src="./src/", dst="~/remote/")
        plan = _make_plan([step], host="user@vps")
        exc = _executor(plan)
        exc.probe.is_local = False
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            exc.run()
        args = mock_run.call_args[0][0]
        assert "user@vps:~/remote/" in args

    def test_rsync_failure_propagates(self):
        step = _make_step("rsync3", action=StepAction.RSYNC, command=None, src="x", dst="y")
        plan = _make_plan([step])
        exc = _executor(plan)
        exc.probe.is_local = True
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=23, stderr="partial transfer")
            result = exc.run()
        assert result is False


# ── _run_http_check ───────────────────────────────────────────────────────────


class TestRunHttpCheck:
    def _http_step(self, url="http://localhost/health", expect=None):
        return _make_step(
            "http1", action=StepAction.HTTP_CHECK, command=None,
            url=url, expect=expect,
        )

    def test_success_no_expect(self):
        step = self._http_step()
        plan = _make_plan([step])
        exc = _executor(plan)
        exc.probe.run.return_value.ok = True
        exc.probe.run.return_value.out = '{"status":"healthy"}'
        exc.run()
        assert step.status == StepStatus.DONE

    def test_success_with_expect(self):
        step = self._http_step(expect="healthy")
        plan = _make_plan([step])
        exc = _executor(plan)
        exc.probe.run.return_value.ok = True
        exc.probe.run.return_value.out = "healthy"
        exc.run()
        assert step.status == StepStatus.DONE

    def test_missing_url_fails(self):
        step = _make_step("http_no_url", action=StepAction.HTTP_CHECK, command=None, url=None)
        plan = _make_plan([step])
        exc = _executor(plan)
        result = exc.run()
        assert result is False

    def test_retries_then_fails(self):
        step = self._http_step(expect="healthy")
        plan = _make_plan([step])
        exc = _executor(plan)
        exc.probe.run.return_value.ok = True
        exc.probe.run.return_value.out = "not_what_we_want"
        with patch("time.sleep"):   # skip delays
            result = exc.run()
        assert result is False
        assert step.status == StepStatus.FAILED

    def test_expect_found_in_output(self):
        step = self._http_step(expect="ok")
        plan = _make_plan([step])
        exc = _executor(plan)
        exc.probe.run.return_value.ok = True
        exc.probe.run.return_value.out = "status:ok"
        exc.run()
        assert "ok" in step.result


# ── _run_version_check ────────────────────────────────────────────────────────


class TestRunVersionCheck:
    def test_version_found(self):
        step = _make_step(
            "ver1", action=StepAction.VERSION_CHECK, command=None,
            url="http://localhost/health", expect="1.0.20",
        )
        plan = _make_plan([step])
        exc = _executor(plan)
        exc.probe.run.return_value.ok = True
        exc.probe.run.return_value.out = '{"version":"1.0.20"}'
        exc.run()
        assert step.status == StepStatus.DONE
        assert "1.0.20" in step.result

    def test_version_not_found_fails(self):
        step = _make_step(
            "ver2", action=StepAction.VERSION_CHECK, command=None,
            url="http://localhost/health", expect="1.0.20",
        )
        plan = _make_plan([step])
        exc = _executor(plan)
        exc.probe.run.return_value.ok = True
        exc.probe.run.return_value.out = '{"version":"1.0.19"}'
        result = exc.run()
        assert result is False

    def test_curl_failure_fails(self):
        step = _make_step(
            "ver3", action=StepAction.VERSION_CHECK, command=None,
            url="http://localhost/health", expect="1.0.20",
        )
        plan = _make_plan([step])
        exc = _executor(plan)
        exc.probe.run.return_value.ok = False
        exc.probe.run.return_value.stderr = "connection refused"
        result = exc.run()
        assert result is False

    def test_missing_url_or_expect_fails(self):
        step = _make_step(
            "ver4", action=StepAction.VERSION_CHECK, command=None,
            url=None, expect=None,
        )
        plan = _make_plan([step])
        exc = _executor(plan)
        result = exc.run()
        assert result is False


# ── _run_wait ─────────────────────────────────────────────────────────────────


class TestRunWait:
    def test_wait_calls_sleep(self):
        step = _make_step("wait1", action=StepAction.WAIT, command=None, seconds=5)
        plan = _make_plan([step])
        exc = _executor(plan)
        with patch("time.sleep") as mock_sleep:
            exc.run()
        mock_sleep.assert_called_once_with(5)
        assert step.result == "waited 5s"

    def test_zero_seconds(self):
        step = _make_step("wait0", action=StepAction.WAIT, command=None, seconds=0)
        plan = _make_plan([step])
        exc = _executor(plan)
        with patch("time.sleep") as mock_sleep:
            exc.run()
        # seconds=0 → executor skips sleep (if step.seconds > 0 guard)
        assert step.status == StepStatus.DONE
        assert step.result == "waited 0s"


# ── rollback ──────────────────────────────────────────────────────────────────


class TestRollback:
    def test_rollback_called_on_failure(self):
        s1 = _make_step("step1", rollback_command="rollback1")
        s2 = _make_step("step2", command="bad")
        plan = _make_plan([s1, s2])
        exc = _executor(plan)

        call_count = {"n": 0}
        def _side(cmd, timeout=300):
            call_count["n"] += 1
            r = MagicMock()
            r.ok = call_count["n"] != 2   # fail on 2nd SSH call
            r.out = ""
            r.stderr = "error"
            r.returncode = 0 if r.ok else 1
            return r

        exc.probe.run.side_effect = _side
        exc.run()
        # probe was called for: step1 execute, step2 execute (fail), then step1 rollback
        calls_cmds = [str(c) for c in exc.probe.run.call_args_list]
        assert any("rollback1" in c for c in calls_cmds)

    def test_no_rollback_without_rollback_command(self):
        s1 = _make_step("step1")   # no rollback_command
        s2 = _make_step("step2", command="bad")
        plan = _make_plan([s1, s2])
        exc = _executor(plan)

        call_count = {"n": 0}
        def _side(cmd, timeout=300):
            call_count["n"] += 1
            r = MagicMock()
            r.ok = call_count["n"] != 2
            r.out = ""
            r.stderr = "error"
            r.returncode = 0 if r.ok else 1
            return r

        exc.probe.run.side_effect = _side
        exc.run()
        # only 2 calls: step1 + step2 (fail), no rollback
        assert exc.probe.run.call_count == 2

    def test_dry_run_no_rollback(self):
        s1 = _make_step("step1", rollback_command="rollback1")
        plan = _make_plan([s1])
        exc = _executor(plan, dry_run=True)
        exc.run()
        exc.probe.run.assert_not_called()


# ── from_file / save_results ──────────────────────────────────────────────────


class TestExecutorFromFile:
    def test_save_results(self, tmp_path):
        plan = _make_plan([_make_step("s1")])
        exc = _executor(plan, dry_run=True)
        exc.run()
        out = tmp_path / "results.yaml"
        exc.save_results(out)
        assert out.exists()
        content = out.read_text()
        assert "testapp" in content


# ── docker_build progress ─────────────────────────────────────────────────────


class TestRunDockerBuild:
    def test_success_logs_progress(self):
        step = _make_step("build", action=StepAction.DOCKER_BUILD, command="docker compose build")
        plan = _make_plan([step])
        exc = _executor(plan)

        # probe.run: first call = build (blocks), subsequent = df snapshots
        build_result = MagicMock(ok=True, out="built", stderr="", exit_code=0)
        df_result = MagicMock(ok=True, out="Images  0  1.2GB\nBuild Cache  30  500MB", stderr="", exit_code=0)

        call_count = [0]
        def side_effect(cmd, timeout=300):
            call_count[0] += 1
            if "docker compose build" in cmd:
                return build_result
            return df_result

        exc.probe.run.side_effect = side_effect
        result = exc.run()
        assert result is True
        assert step.status == StepStatus.DONE

    def test_build_failure_raises(self):
        step = _make_step("build", action=StepAction.DOCKER_BUILD, command="docker compose build")
        plan = _make_plan([step])
        exc = _executor(plan)

        fail = MagicMock(ok=False, out="", stderr="npm ERR! ENOENT", exit_code=1)
        exc.probe.run.return_value = fail
        result = exc.run()
        assert result is False
        assert step.status == StepStatus.FAILED

    def test_no_command_raises(self):
        step = MigrationStep(id="build", action=StepAction.DOCKER_BUILD,
                             description="build", command=None)
        plan = _make_plan([step])
        exc = _executor(plan)
        result = exc.run()
        assert result is False


# ── docker_health_wait ────────────────────────────────────────────────────────


class TestRunDockerHealthWait:
    def test_all_healthy_immediately(self):
        step = _make_step("wait", action=StepAction.DOCKER_HEALTH_WAIT,
                          command="docker compose ps --format table")
        plan = _make_plan([step])
        exc = _executor(plan)

        healthy_out = "NAME\tSTATUS\nc2004-backend\tUp (healthy)\nc2004-frontend\tUp (healthy)"
        exc.probe.run.return_value = MagicMock(ok=True, out=healthy_out, stderr="", exit_code=0)
        result = exc.run()
        assert result is True
        assert step.status == StepStatus.DONE
        assert "healthy" in step.result

    def test_timeout_does_not_fail(self):
        """docker_health_wait should not fail hard — http_check will catch it."""
        step = MigrationStep(id="wait", action=StepAction.DOCKER_HEALTH_WAIT,
                             description="wait", command="docker compose ps",
                             timeout=1)
        plan = _make_plan([step])
        exc = _executor(plan)

        starting_out = "c2004-backend\tStarting"
        exc.probe.run.return_value = MagicMock(ok=True, out=starting_out, stderr="", exit_code=0)
        result = exc.run()
        assert result is True  # timeout is a warning, not failure
        assert step.status == StepStatus.DONE
        assert "timeout" in step.result

    def test_no_command_raises(self):
        step = MigrationStep(id="wait", action=StepAction.DOCKER_HEALTH_WAIT,
                             description="wait", command=None)
        plan = _make_plan([step])
        exc = _executor(plan)
        result = exc.run()
        assert result is False


# ── container_log_tail ────────────────────────────────────────────────────────


class TestRunContainerLogTail:
    def test_logs_fetched_and_stored(self):
        step = _make_step("logs", action=StepAction.CONTAINER_LOG_TAIL,
                          command="docker compose logs --tail 15")
        plan = _make_plan([step])
        exc = _executor(plan)

        log_output = "\n".join(f"backend | line {i}" for i in range(15))
        exc.probe.run.return_value = MagicMock(ok=True, out=log_output, stderr="", exit_code=0)
        result = exc.run()
        assert result is True
        assert step.status == StepStatus.DONE
        assert "15" in step.result

    def test_empty_output_handled(self):
        step = _make_step("logs", action=StepAction.CONTAINER_LOG_TAIL,
                          command="docker compose logs --tail 15")
        plan = _make_plan([step])
        exc = _executor(plan)
        exc.probe.run.return_value = MagicMock(ok=False, out="", stderr="", exit_code=0)
        result = exc.run()
        assert result is True  # not fatal
        assert "no log output" in step.result


# ── wait progress ticker ──────────────────────────────────────────────────────


class TestRunWait:
    def test_zero_seconds(self):
        step = MigrationStep(id="w", action=StepAction.WAIT, description="w", seconds=0)
        plan = _make_plan([step])
        exc = _executor(plan)
        exc.probe.run.return_value = MagicMock(ok=True, out="ok", stderr="", exit_code=0)
        result = exc.run()
        assert result is True
        assert step.result == "waited 0s"

    def test_positive_seconds(self):
        import redeploy.apply.executor as ex_mod
        step = MigrationStep(id="w", action=StepAction.WAIT, description="w", seconds=15)
        plan = _make_plan([step])
        exc = _executor(plan)
        exc.probe.run.return_value = MagicMock(ok=True, out="ok", stderr="", exit_code=0)
        with patch("redeploy.apply.executor.time") as mock_time:
            mock_time.sleep = MagicMock()
            result = exc.run()
        assert result is True
        assert step.result == "waited 15s"


# ── inline_script ───────────────────────────────────────────────────────────────


class TestRunInlineScript:
    def test_multiline_script_success(self):
        script = """#!/bin/bash
echo "Line 1"
echo "Line 2"
exit 0
"""
        step = _make_step("script1", action=StepAction.INLINE_SCRIPT, command=script)
        plan = _make_plan([step])
        exc = _executor(plan)
        exc.probe.run.return_value = MagicMock(ok=True, out="Line 1\nLine 2", stderr="", exit_code=0)
        result = exc.run()
        assert result is True
        assert step.status == StepStatus.DONE
        assert "Line 1" in step.result

    def test_script_failure_raises(self):
        script = """#!/bin/bash
echo "Error"
exit 1
"""
        step = _make_step("script_fail", action=StepAction.INLINE_SCRIPT, command=script)
        plan = _make_plan([step])
        exc = _executor(plan)
        exc.probe.run.return_value = MagicMock(ok=False, out="", stderr="Error", exit_code=1)
        result = exc.run()
        assert result is False
        assert step.status == StepStatus.FAILED

    def test_no_command_raises(self):
        step = _make_step("script_no_cmd", action=StepAction.INLINE_SCRIPT, command="")
        step.command = None
        plan = _make_plan([step])
        exc = _executor(plan)
        result = exc.run()
        assert result is False
        assert step.status == StepStatus.FAILED

    def test_uses_step_timeout(self):
        script = "#!/bin/bash\necho test"
        step = _make_step("script_timeout", action=StepAction.INLINE_SCRIPT, command=script, timeout=456)
        plan = _make_plan([step])
        exc = _executor(plan)
        exc.probe.run.return_value = MagicMock(ok=True, out="test", stderr="", exit_code=0)
        exc.run()
        assert exc.probe.run.call_args.kwargs["timeout"] == 456

    def test_command_ref_resolves_from_markdown(self, tmp_path):
        """Test that command_ref extracts script from markdown codeblock."""
        # Create markdown file with script
        md_content = """# Test Migration

## Test Script Section

```bash
#!/bin/bash
echo "from markdown"
```
"""
        md_file = tmp_path / "test.md"
        md_file.write_text(md_content)
        
        # Create step with command_ref
        step = MigrationStep(
            id="script_ref",
            action=StepAction.INLINE_SCRIPT,
            description="test",
            command=None,
            command_ref="#test-script-section",
        )
        plan = _make_plan([step])
        plan.spec_path = str(md_file)
        
        exc = _executor(plan)
        exc.probe.run.return_value = MagicMock(ok=True, out="from markdown", stderr="", exit_code=0)
        
        result = exc.run()
        assert result is True
        assert step.status == StepStatus.DONE

    def test_command_ref_missing_section_fails(self, tmp_path):
        """Test that missing section in markdown fails gracefully."""
        md_content = "# Test\n\n## Other Section\n```bash\necho test\n```"
        md_file = tmp_path / "test.md"
        md_file.write_text(md_content)
        
        step = MigrationStep(
            id="script_ref_fail",
            action=StepAction.INLINE_SCRIPT,
            description="test",
            command=None,
            command_ref="#nonexistent-section",
        )
        plan = _make_plan([step])
        plan.spec_path = str(md_file)
        
        exc = _executor(plan)
        result = exc.run()
        
        assert result is False
        assert step.status == StepStatus.FAILED
        assert "nonexistent-section" in step.error

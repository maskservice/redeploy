from __future__ import annotations

import textwrap

from redeploy.apply.executor import Executor
from redeploy.models import (
    ConflictSeverity,
    DeployStrategy,
    Hook,
    MigrationPlan,
    MigrationSpec,
    MigrationStep,
    StepAction,
)


def _plan(*, hooks: list[Hook], steps: list[MigrationStep]) -> MigrationPlan:
    return MigrationPlan(
        host="local",
        app="testapp",
        from_strategy=DeployStrategy.DOCKER_FULL,
        to_strategy=DeployStrategy.DOCKER_FULL,
        risk=ConflictSeverity.LOW,
        steps=steps,
        notes=[],
        hooks=hooks,
    )


def test_legacy_post_deploy_is_migrated_to_hooks(tmp_path):
    spec_path = tmp_path / "migration.yaml"
    spec_path.write_text(
        textwrap.dedent(
            """
            name: legacy hooks migration
            source:
              strategy: docker_full
              host: local
              app: myapp
            target:
              strategy: docker_full
              host: local
              app: myapp
              post_deploy:
                open_browser: true
                browser_url: http://localhost:8100
            post_deploy:
              refresh_cache: true
              browser_url: http://localhost:8100
            """
        ).strip()
    )

    spec = MigrationSpec.from_file(spec_path)
    hooks = spec.hooks

    assert len(hooks) == 2
    assert {h.id for h in hooks} == {"after_apply_refresh_cache", "after_apply_open_browser"}
    assert all(h.phase == "after_apply" for h in hooks)


def test_executor_fires_hook_phases_on_success(monkeypatch):
    calls: list[tuple[str, str]] = []

    hooks = [
        Hook(id="h_before_apply", phase="before_apply", action="local_cmd", command="echo 1"),
        Hook(id="h_before_step", phase="before_step", action="local_cmd", when="step.id == 's1'", command="echo 2"),
        Hook(id="h_after_step", phase="after_step", action="local_cmd", command="echo 3"),
        Hook(id="h_after_apply", phase="after_apply", action="local_cmd", command="echo 4"),
        Hook(id="h_always", phase="always", action="local_cmd", command="echo 5"),
    ]
    steps = [
        MigrationStep(id="s1", action=StepAction.SSH_CMD, description="step", command="echo ok"),
    ]
    plan = _plan(hooks=hooks, steps=steps)
    executor = Executor(plan, dry_run=True)

    def _capture(self, hook, context):  # noqa: ANN001
        calls.append((hook.phase, hook.id))

    monkeypatch.setattr(Executor, "_execute_hook", _capture)

    ok = executor.run()

    assert ok is True
    assert calls == [
        ("before_apply", "h_before_apply"),
        ("before_step", "h_before_step"),
        ("after_step", "h_after_step"),
        ("after_apply", "h_after_apply"),
        ("always", "h_always"),
    ]


def test_executor_fires_failure_hooks(monkeypatch):
    calls: list[tuple[str, str]] = []

    hooks = [
        Hook(id="h_step_fail", phase="on_step_failure", action="local_cmd", command="echo fail"),
        Hook(id="h_fail", phase="on_failure", action="local_cmd", command="echo fail2"),
        Hook(id="h_always", phase="always", action="local_cmd", command="echo always"),
    ]
    steps = [
        # Missing command triggers StepError in SSH handler path.
        MigrationStep(id="s1", action=StepAction.SSH_CMD, description="step", command=None),
    ]
    plan = _plan(hooks=hooks, steps=steps)
    executor = Executor(plan, dry_run=False)

    def _capture(self, hook, context):  # noqa: ANN001
        calls.append((hook.phase, hook.id))

    monkeypatch.setattr(Executor, "_execute_hook", _capture)
    monkeypatch.setattr(Executor, "_rollback", lambda self: None)

    ok = executor.run()

    assert ok is False
    assert calls == [
        ("on_step_failure", "h_step_fail"),
        ("on_failure", "h_fail"),
        ("always", "h_always"),
    ]

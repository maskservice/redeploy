from redeploy.heal import HealLoopDetector
from redeploy.heal.decider import Action, Decision


def test_loop_detector_triggers_on_identical_hint_streak():
    d = HealLoopDetector(max_identical_hints=3)

    assert d.observe("sync_env", "manual | ssh: no such file") is False
    assert d.observe("sync_env", "manual | ssh: no such file") is False
    assert d.observe("sync_env", "manual | ssh: no such file") is True


def test_loop_detector_does_not_trigger_for_varying_hints():
    d = HealLoopDetector(max_identical_hints=3)

    assert d.observe("sync_env", "manual | first") is False
    assert d.observe("sync_env", "manual | second") is False
    assert d.observe("sync_env", "manual | first") is False


def test_loop_detector_tracks_each_step_independently():
    d = HealLoopDetector(max_identical_hints=2)

    assert d.observe("sync_env", "manual | x") is False
    assert d.observe("verify_health", "manual | x") is False
    assert d.observe("sync_env", "manual | x") is True
    assert d.observe("verify_health", "manual | x") is True


def test_loop_detector_reset_clears_step_history():
    d = HealLoopDetector(max_identical_hints=2)

    assert d.observe("sync_env", "manual | x") is False
    assert d.observe("sync_env", "manual | x") is True

    d.reset("sync_env")
    assert d.observe("sync_env", "manual | x") is False


def test_heal_runner_stops_on_repeating_hint_pattern(monkeypatch, tmp_path):
    from redeploy.heal import HealRunner

    spec_path = tmp_path / "spec.md"
    spec_path.write_text("steps:\n  - id: sync_env\n")

    class _FakeExecutor:
        def run(self):
            return False

        def summary(self):
            return "Step failed: [sync_env] exit=1: boom"

    make_executor_calls = []
    ask_calls = []

    def _fake_make_executor(self, resume=False):
        make_executor_calls.append(resume)
        return _FakeExecutor()

    def _fake_ask(*_args, **_kwargs):
        ask_calls.append(True)
        return "```yaml\n- id: sync_env\n  action: ssh_cmd\n  description: \"manual\"\n```"

    monkeypatch.setattr("redeploy.heal.runner.parse_failed_step", lambda *_a, **_k: ("sync_env", "boom"))
    monkeypatch.setattr("redeploy.heal.runner.collect_diagnostics", lambda *_a, **_k: "ERROR: same")
    monkeypatch.setattr("redeploy.heal.runner.ask_llm", _fake_ask)
    monkeypatch.setattr("redeploy.heal.runner.apply_fix_to_spec", lambda *_a, **_k: True)
    monkeypatch.setattr("redeploy.heal.runner.write_repair_log", lambda *_a, **_k: None)
    monkeypatch.setattr(HealRunner, "_make_executor", _fake_make_executor)
    monkeypatch.setattr(HealRunner, "_reload_migration", lambda *_a, **_k: None)

    runner = HealRunner(
        migration=object(),
        spec_path=spec_path,
        host="pi@test",
        max_retries=5,
        dry_run=True,
        version="0.0.0",
    )
    runner._loop_detector = HealLoopDetector(max_identical_hints=2)

    assert runner.run() is False
    assert len(ask_calls) == 2
    assert make_executor_calls == [False, True]


def test_heal_runner_reverts_invalid_llm_patch_without_crash(monkeypatch, tmp_path):
    from redeploy.heal import HealRunner

    spec_path = tmp_path / "spec.md"
    original = "steps:\n  - id: start_services\n    action: ssh_cmd\n"
    spec_path.write_text(original)

    class _FakeExecutor:
        def run(self):
            return False

        def summary(self):
            return "Step failed: [start_services] exit=1: boom"

    monkeypatch.setattr("redeploy.heal.runner.parse_failed_step", lambda *_a, **_k: ("start_services", "boom"))
    monkeypatch.setattr("redeploy.heal.runner.collect_diagnostics", lambda *_a, **_k: "ERROR: same")
    monkeypatch.setattr(
        "redeploy.heal.runner.ask_llm",
        lambda *_a, **_k: "```yaml\n- id: start_services\n  action: local_cmd\n  description: \"broken\"\n```",
    )

    def _fake_apply_fix(path, *_args, **_kwargs):
        path.write_text("steps:\n  - id: start_services\n    action: local_cmd\n")
        return True

    monkeypatch.setattr("redeploy.heal.runner.apply_fix_to_spec", _fake_apply_fix)
    monkeypatch.setattr("redeploy.heal.runner.write_repair_log", lambda *_a, **_k: None)
    monkeypatch.setattr(HealRunner, "_make_executor", lambda *_a, **_k: _FakeExecutor())
    monkeypatch.setattr(HealRunner, "_reload_migration", lambda *_a, **_k: (_ for _ in ()).throw(ValueError("invalid action")))

    runner = HealRunner(
        migration=object(),
        spec_path=spec_path,
        host="pi@test",
        max_retries=1,
        dry_run=True,
        version="0.0.0",
    )

    assert runner.run() is False
    assert spec_path.read_text() == original


def test_heal_runner_skip_marks_state_and_resumes(monkeypatch, tmp_path):
    from redeploy.heal import HealRunner

    spec_path = tmp_path / "spec.md"
    spec_path.write_text("steps:\n  - id: sync_env\n")

    class _State:
        def __init__(self):
            self.marked: list[str] = []

        def mark_done(self, step_id: str):
            self.marked.append(step_id)

    class _FakeExecutor:
        def __init__(self, ok: bool, state):
            self._ok = ok
            self.state = state

        def run(self):
            return self._ok

        def summary(self):
            return "Step failed: [sync_env] exit=1: boom"

    state = _State()
    make_calls: list[bool] = []

    def _fake_make_executor(self, resume=False):
        make_calls.append(resume)
        if not resume:
            return _FakeExecutor(False, state)
        return _FakeExecutor(True, state)

    monkeypatch.setattr(HealRunner, "_make_executor", _fake_make_executor)
    monkeypatch.setattr(
        HealRunner,
        "_heal_step",
        lambda *_a, **_k: (Decision(Action.SKIP, "skip"), "sync_env", "hint"),
    )
    monkeypatch.setattr("redeploy.heal.runner.write_repair_log", lambda *_a, **_k: None)

    runner = HealRunner(
        migration=object(),
        spec_path=spec_path,
        host="pi@test",
        max_retries=2,
        dry_run=True,
        version="0.0.0",
    )

    assert runner.run() is True
    assert state.marked == ["sync_env"]
    assert make_calls == [False, True]

from redeploy.heal import HealLoopDetector


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

    monkeypatch.setattr("redeploy.heal.parse_failed_step", lambda *_a, **_k: ("sync_env", "boom"))
    monkeypatch.setattr("redeploy.heal.collect_diagnostics", lambda *_a, **_k: "ERROR: same")
    monkeypatch.setattr("redeploy.heal.ask_llm", _fake_ask)
    monkeypatch.setattr("redeploy.heal.apply_fix_to_spec", lambda *_a, **_k: False)
    monkeypatch.setattr("redeploy.heal.write_repair_log", lambda *_a, **_k: None)
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

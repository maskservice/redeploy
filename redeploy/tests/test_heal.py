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

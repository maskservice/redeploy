"""Unit tests for redeploy.heal.loop_detector (R1)."""
import pytest

from redeploy.heal.loop_detector import HealAbort, HealLoopDetector


class TestHealLoopDetector:
    def test_empty_hint_ignored(self):
        d = HealLoopDetector(max_identical_hints=2)
        assert d.observe("step1", "") is False
        assert d.observe("step1", "   ") is False

    def test_loop_detected_after_n_identical(self):
        d = HealLoopDetector(max_identical_hints=3)
        assert d.observe("s", "hint-a") is False
        assert d.observe("s", "hint-a") is False
        assert d.observe("s", "hint-a") is True

    def test_different_hints_reset(self):
        d = HealLoopDetector(max_identical_hints=3)
        d.observe("s", "hint-a")
        d.observe("s", "hint-a")
        assert d.observe("s", "hint-b") is False
        assert d.observe("s", "hint-b") is False
        assert d.observe("s", "hint-b") is True

    def test_reset_clears_history(self):
        d = HealLoopDetector(max_identical_hints=2)
        d.observe("s", "h")
        d.reset("s")
        assert d.observe("s", "h") is False

    def test_different_step_ids_isolated(self):
        d = HealLoopDetector(max_identical_hints=2)
        assert d.observe("s1", "h") is False
        assert d.observe("s2", "h") is False
        assert d.observe("s1", "h") is True
        assert d.observe("s2", "h") is True


class TestHealAbort:
    def test_message(self):
        exc = HealAbort("sync_env", "bad hint", 3)
        assert "sync_env" in str(exc)
        assert "3x" in str(exc)
        assert exc.step_id == "sync_env"
        assert exc.repeats == 3

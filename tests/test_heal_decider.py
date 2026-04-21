"""Unit tests for redeploy.heal.decider (R1)."""
import pytest

from redeploy.heal.decider import Action, Decision, decide_after_failure, format_decision_message


class TestDecideAfterFailure:
    def test_loop_aborts(self):
        d = decide_after_failure(
            attempt=1, max_retries=5, failed_step="s",
            loop_detected=True, llm_error=False, spec_patched=False,
        )
        assert d.action is Action.ABORT
        assert "Loop detected" in d.reason

    def test_missing_step_aborts(self):
        d = decide_after_failure(
            attempt=1, max_retries=5, failed_step=None,
            loop_detected=False, llm_error=False, spec_patched=False,
        )
        assert d.action is Action.ABORT

    def test_max_retries_aborts(self):
        d = decide_after_failure(
            attempt=3, max_retries=3, failed_step="s",
            loop_detected=False, llm_error=False, spec_patched=False,
        )
        assert d.action is Action.ABORT
        assert "exhausted" in d.reason

    def test_patch_retries(self):
        d = decide_after_failure(
            attempt=2, max_retries=3, failed_step="s",
            loop_detected=False, llm_error=False, spec_patched=True,
        )
        assert d.action is Action.RETRY

    def test_llm_error_retries_then_aborts(self):
        d = decide_after_failure(
            attempt=1, max_retries=3, failed_step="s",
            loop_detected=False, llm_error=True, spec_patched=False,
        )
        assert d.action is Action.RETRY
        d2 = decide_after_failure(
            attempt=3, max_retries=3, failed_step="s",
            loop_detected=False, llm_error=True, spec_patched=False,
        )
        assert d2.action is Action.ABORT

    def test_no_patch_skips(self):
        d = decide_after_failure(
            attempt=1, max_retries=3, failed_step="s",
            loop_detected=False, llm_error=False, spec_patched=False,
        )
        assert d.action is Action.SKIP


class TestFormatDecisionMessage:
    def test_contains_action(self):
        d = Decision(Action.RETRY, "because patched")
        msg = format_decision_message(d, "step-1")
        assert "RETRY" in msg
        assert "patched" in msg

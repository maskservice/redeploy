from redeploy.heal.decider import Action, Decision, decide_after_failure, format_decision_message


def test_decide_abort_on_loop_detected():
    decision = decide_after_failure(
        attempt=1,
        max_retries=3,
        failed_step="sync_env",
        loop_detected=True,
        llm_error=False,
        spec_patched=False,
    )
    assert decision == Decision(Action.ABORT, "Loop detected: same hint for 'sync_env' ≥ 3 times in a row")


def test_decide_abort_when_failed_step_unknown():
    decision = decide_after_failure(
        attempt=1,
        max_retries=3,
        failed_step=None,
        loop_detected=False,
        llm_error=False,
        spec_patched=False,
    )
    assert decision == Decision(Action.ABORT, "Cannot identify failed step — giving up")


def test_decide_retry_on_transient_llm_error_before_limit():
    decision = decide_after_failure(
        attempt=1,
        max_retries=3,
        failed_step="sync_env",
        loop_detected=False,
        llm_error=True,
        spec_patched=False,
    )
    assert decision == Decision(Action.RETRY, "LLM error — retrying may help if transient")


def test_decide_abort_on_llm_error_at_retry_limit():
    decision = decide_after_failure(
        attempt=3,
        max_retries=3,
        failed_step="sync_env",
        loop_detected=False,
        llm_error=True,
        spec_patched=False,
    )
    assert decision == Decision(Action.ABORT, "LLM error — retrying may help if transient")


def test_decide_abort_when_retry_budget_exhausted():
    decision = decide_after_failure(
        attempt=3,
        max_retries=3,
        failed_step="sync_env",
        loop_detected=False,
        llm_error=False,
        spec_patched=False,
    )
    assert decision == Decision(Action.ABORT, "Max retries (3) exhausted for 'sync_env'")


def test_decide_retry_when_spec_was_patched():
    decision = decide_after_failure(
        attempt=1,
        max_retries=3,
        failed_step="sync_env",
        loop_detected=False,
        llm_error=False,
        spec_patched=True,
    )
    assert decision == Decision(Action.RETRY, "Spec patched — re-running migration")


def test_decide_skip_when_patch_not_applicable():
    decision = decide_after_failure(
        attempt=1,
        max_retries=3,
        failed_step="sync_env",
        loop_detected=False,
        llm_error=False,
        spec_patched=False,
    )
    assert decision == Decision(Action.SKIP, "LLM did not produce an applicable patch — skipping step")


def test_format_decision_message_uses_action_and_reason():
    msg = format_decision_message(Decision(Action.RETRY, "Spec patched"), "sync_env")
    assert "RETRY" in msg
    assert "Spec patched" in msg

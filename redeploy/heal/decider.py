"""Heal decision policy — retry / skip / abort logic."""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class Action(Enum):
    RETRY = "retry"
    SKIP = "skip"
    ABORT = "abort"


@dataclass(frozen=True)
class Decision:
    action: Action
    reason: str = ""


def decide_after_failure(
    *,
    attempt: int,
    max_retries: int,
    failed_step: Optional[str],
    loop_detected: bool,
    llm_error: bool,
    spec_patched: bool,
) -> Decision:
    """Return the next action for the heal loop.

    Parameters
    ----------
    attempt:
        1-based attempt counter inside the heal loop.
    max_retries:
        Maximum retries configured by the user.
    failed_step:
        Step identifier, or *None* if the parser could not identify it.
    loop_detected:
        *True* when :class:`HealLoopDetector` flagged a repeating hint.
    llm_error:
        *True* when the LLM call itself failed (not a fixable step failure).
    spec_patched:
        *True* when the LLM produced a patch and it was applied.

    Returns
    -------
    Decision
    """
    if loop_detected:
        return Decision(
            Action.ABORT,
            f"Loop detected: same hint for {failed_step!r} ≥ 3 times in a row",
        )
    if failed_step is None:
        return Decision(Action.ABORT, "Cannot identify failed step — giving up")
    if llm_error:
        return Decision(
            Action.ABORT if attempt >= max_retries else Action.RETRY,
            "LLM error — retrying may help if transient",
        )
    if attempt >= max_retries:
        return Decision(
            Action.ABORT,
            f"Max retries ({max_retries}) exhausted for {failed_step!r}",
        )
    if spec_patched:
        return Decision(Action.RETRY, "Spec patched — re-running migration")
    return Decision(
        Action.SKIP,
        "LLM did not produce an applicable patch — skipping step",
    )


def format_decision_message(decision: Decision, step_id: str) -> str:
    """Human-readable log / console message for a decision."""
    emoji = {
        Action.RETRY: "🔄",
        Action.SKIP: "⏭️",
        Action.ABORT: "🛑",
    }
    return f"{emoji[decision.action]} {decision.action.value.upper()}: {decision.reason}"

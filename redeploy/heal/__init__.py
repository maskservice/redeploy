"""redeploy.heal — Self-healing runner with LiteLLM auto-repair.

This package has been refactored from the monolithic ``redeploy.heal`` module.
For backward compatibility all public names remain importable from
``redeploy.heal``.
"""
from __future__ import annotations

from .loop_detector import HealAbort, HealLoopDetector
from .log_writer import write_repair_log
from .hint_provider import (
    DIAG_COMMANDS,
    KNOWN_CONSTRAINTS,
    collect_diagnostics,
    ask_llm,
    apply_fix_to_spec,
    parse_failed_step,
)
from .decider import Action, Decision, decide_after_failure, format_decision_message
from .runner import HealRunner

__all__ = [
    "HealAbort",
    "HealLoopDetector",
    "write_repair_log",
    "DIAG_COMMANDS",
    "KNOWN_CONSTRAINTS",
    "collect_diagnostics",
    "ask_llm",
    "apply_fix_to_spec",
    "parse_failed_step",
    "Action",
    "Decision",
    "decide_after_failure",
    "format_decision_message",
    "HealRunner",
]

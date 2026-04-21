"""Heal loop detection — prevents non-converging auto-repair cycles."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


class HealAbort(Exception):
    """Raised when a heal loop is detected and retries must stop."""

    def __init__(self, step_id: str, hint: str, repeats: int) -> None:
        self.step_id = step_id
        self.hint = hint
        self.repeats = repeats
        super().__init__(
            f"Heal loop detected for {step_id!r}: "
            f"same hint repeated {repeats}x"
        )


@dataclass
class HealLoopDetector:
    """Detect repeated non-converging heal hints for a given step.

    Parameters
    ----------
    max_identical_hints:
        Number of consecutive identical hints that trigger a loop abort.
        Default is 3 because after two identical retries the third
        almost never brings new information.
    """

    max_identical_hints: int = 3
    _history: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    def observe(self, step_id: str, hint: str) -> bool:
        """Return *True* when the latest hints indicate a heal loop.

        A loop is defined as ``max_identical_hints`` identical non-empty
        hints in a row for the same failed step.
        """
        normalized = (hint or "").strip()
        if not normalized:
            return False

        history = self._history[step_id]
        history.append(normalized)

        if len(history) < self.max_identical_hints:
            return False

        recent = history[-self.max_identical_hints :]
        return all(item == recent[0] for item in recent)

    def reset(self, step_id: str) -> None:
        """Clear history for *step_id* (e.g. after a successful retry)."""
        self._history.pop(step_id, None)

    def reset_all(self) -> None:
        """Clear all history."""
        self._history.clear()

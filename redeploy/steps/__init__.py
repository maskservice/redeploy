"""Step library — pre-defined, reusable named MigrationSteps.

Usage in a MigrationSpec::

    extra_steps:
      - id: flush_k3s_iptables   # references a library step by id
      - id: stop_nginx
      - id: http_health_check
        url: https://myapp.example.com/health

Usage from Python::

    from redeploy.steps import StepLibrary
    steps = StepLibrary.get("flush_k3s_iptables")
"""
from __future__ import annotations

from typing import Any, Optional

from ..models import MigrationStep

from . import builtins, kiosk

# Merge domain modules into a single flat registry.
_LIBRARY: dict[str, MigrationStep] = {
    s.id: s for s in (builtins.ALL + kiosk.ALL)
}


class StepLibrary:
    """Registry of pre-defined named MigrationSteps.

    Steps are returned as copies so callers can override individual fields::

        step = StepLibrary.get("http_health_check")
        step.url = "https://myapp.example.com/health"
        step.expect = "1.0.20"
    """

    @staticmethod
    def get(step_id: str, **overrides: Any) -> Optional[MigrationStep]:
        """Return a copy of a named step, optionally with field overrides.

        Returns ``None`` if the step_id is not in the library.
        """
        template = _LIBRARY.get(step_id)
        if template is None:
            return None
        data = template.model_dump()
        data.update(overrides)
        return MigrationStep(**data)

    @staticmethod
    def list() -> list[str]:
        """Return sorted list of available step IDs."""
        return sorted(_LIBRARY.keys())

    @staticmethod
    def all() -> dict[str, MigrationStep]:
        """Return full registry (copies)."""
        return {k: v.model_copy() for k, v in _LIBRARY.items()}

    @staticmethod
    def resolve_from_spec(raw: dict[str, Any]) -> MigrationStep:
        """Resolve a raw dict (from migration YAML extra_steps) to a MigrationStep.

        If ``id`` matches a library entry and no ``action`` is given, use the
        library template as base and merge the raw dict on top.
        """
        step_id = raw.get("id", "")
        template = _LIBRARY.get(step_id)
        if template:
            data = template.model_dump()
            data.update({k: v for k, v in raw.items() if v is not None})
            return MigrationStep(**data)
        return MigrationStep(**raw)

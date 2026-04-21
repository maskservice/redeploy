"""Diagnostic rules for hardware analysis (adapter to op3).

The rule engine moved to ``opstree.probes.builtin.rpi_diagnostics`` in
op3 ≥ 0.1.10.  This module is a thin adapter that converts
:class:`redeploy.models.HardwareInfo` ↔ op3 generic diagnostics.
"""
from __future__ import annotations

from redeploy.models import HardwareDiagnostic, HardwareInfo

try:
    from opstree.probes.builtin.rpi_diagnostics import diagnose_display_layer
    _OP3_AVAILABLE = True
except ImportError:  # pragma: no cover
    _OP3_AVAILABLE = False


# ── adapter helpers ───────────────────────────────────────────────────────────


def _hw_info_to_dict(hw: HardwareInfo) -> dict:
    """Convert :class:`HardwareInfo` → flat dict that op3 rules expect."""
    d = hw.model_dump(mode="json")
    # op3 probe uses ``board_model``; redeploy model uses ``board``
    d["board_model"] = d.pop("board", None) or ""
    # ``kms_enabled`` is a computed property in HardwareInfo, not a field
    d["kms_enabled"] = hw.kms_enabled
    return d


def _op3_diag_to_hw_diag(d) -> HardwareDiagnostic:
    """Convert op3 :class:`Diagnostic` → redeploy :class:`HardwareDiagnostic`."""
    return HardwareDiagnostic(
        component=getattr(d, "component", "unknown"),
        severity=getattr(d, "severity", "warning"),
        message=getattr(d, "message", ""),
        fix=getattr(d, "fix", None),
    )


# ── public API ────────────────────────────────────────────────────────────────


def analyze(hw: HardwareInfo) -> list[HardwareDiagnostic]:
    """Run all diagnostic rules against *hw* and return findings.

    Delegates to :func:`opstree.probes.builtin.rpi_diagnostics.diagnose_display_layer`.
    """
    if not _OP3_AVAILABLE:
        raise RuntimeError(
            "op3 is required for hardware diagnostics. "
            "Install: pip install 'redeploy[op3]'"
        )

    op3_diags = diagnose_display_layer(_hw_info_to_dict(hw))
    return [_op3_diag_to_hw_diag(d) for d in op3_diags]

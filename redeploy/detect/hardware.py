"""Hardware probes — adapter to op3's LinearScanner.

The rich probe logic moved to ``opstree.probes.builtin.physical_rpi`` +
``opstree.probes.builtin.os_linux`` in op3 ≥ 0.1.10.  This module is now a
thin adapter that:

1. Wraps :class:`redeploy.ssh.RemoteProbe` as an op3 :class:`ProbeContext`.
2. Builds an op3 :class:`LinearScanner` covering the hardware layer set.
3. Reuses :func:`redeploy.integrations.op3_bridge.snapshot_to_hardware_info`
   to produce a :class:`redeploy.models.HardwareInfo`.
4. Attaches diagnostics via op3's rule engine (through
   :func:`redeploy.detect.hardware_rules.analyze`).

Legacy per-probe helpers (``probe_drm_outputs``, ``probe_backlights``, …)
were removed; they are now part of the op3 probe.
"""
from __future__ import annotations

from redeploy.models import HardwareDiagnostic, HardwareInfo

from ..integrations.op3_bridge import (
    DEFAULT_HARDWARE_LAYERS,
    make_scanner,
    op3_available,
    snapshot_to_hardware_info,
)
from .hardware_rules import analyze as _analyze
from .remote import RemoteProbe

try:
    from opstree.probes.base import ProbeContext
    _OP3_CONTEXT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _OP3_CONTEXT_AVAILABLE = False


# ── adapter helpers ────────────────────────────────────────────────────────


def _wrap_remote_probe(p: RemoteProbe) -> "ProbeContext":
    """Wrap a redeploy :class:`RemoteProbe` as an op3 :class:`ProbeContext`."""

    def execute(cmd: str):
        r = p.run(cmd)
        return (r.stdout, r.stderr, r.exit_code)

    return ProbeContext(target=p.host, execute=execute)


# ── public API ────────────────────────────────────────────────────────────


def probe_hardware(p: RemoteProbe) -> HardwareInfo:
    """Probe hardware state of the remote host and return ``HardwareInfo``.

    When op3 is installed this delegates to :func:`make_scanner` which wires
    op3 probes for ``physical.display``, ``os.kernel`` and ``os.config``.
    Diagnostics are attached via op3's rule engine.
    """
    if not (op3_available() and _OP3_CONTEXT_AVAILABLE):
        raise RuntimeError(
            "Hardware probing requires op3. Install: pip install 'redeploy[op3]'"
        )

    ctx = _wrap_remote_probe(p)
    scanner = make_scanner(list(DEFAULT_HARDWARE_LAYERS))
    snapshot = scanner.scan(p.host, ctx.execute)

    hw = snapshot_to_hardware_info(snapshot)

    # Only run rules when there's actually a physical.display layer — on
    # non-RPi hosts the probe is skipped and we want a clear signal.
    if snapshot.layer("physical.display") is None:
        hw.diagnostics = [
            HardwareDiagnostic(
                component="board",
                severity="warning",
                message="Target does not appear to be a Raspberry Pi",
            )
        ]
    else:
        hw.diagnostics = _analyze(hw)
    return hw

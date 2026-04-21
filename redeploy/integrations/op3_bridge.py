"""Bridge between redeploy and op3.

All adapters go through here. This module isolates op3 usage so that redeploy
remains runnable when op3 is not installed.

Design notes
------------

- ``op3_available()`` hard feature-detects ``opstree``.
- ``op3_enabled()`` reads ``REDEPLOY_USE_OP3`` so operators can flip the
  code path without a code change — mirrors doql's ``DOQL_USE_OP3``.
- ``should_use_op3()`` is what legacy call sites branch on.
- The scanner helpers (:func:`make_scanner`, :func:`make_ssh_context`,
  :func:`make_mock_context`) are thin shims over op3 0.1.8's
  :func:`opstree.build_scanner`. They exist so redeploy command modules
  don't have to import ~6 submodules apiece and so we have one place to
  patch when op3's API evolves.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Callable, Optional, Sequence

if TYPE_CHECKING:
    from opstree.probes.base import Probe
    from opstree.probes.context import ProbeContext, SSHContext
    from opstree.scanner.linear import LinearScanner
    from opstree.snapshot.model import Snapshot
    from redeploy.models import InfraState, HardwareInfo

OP3_ENABLED_ENV = "REDEPLOY_USE_OP3"

# Redeploy-specific default layer set — hardware-focused because that is
# where the legacy ``redeploy hardware`` command lives.
DEFAULT_HARDWARE_LAYERS: tuple[str, ...] = (
    "physical.display",
    "os.kernel",
    "os.config",
)


# ── feature detection ────────────────────────────────────────────────────


def op3_enabled() -> bool:
    """Check whether the user wants to use op3."""
    return os.environ.get(OP3_ENABLED_ENV, "0").lower() in ("1", "true", "yes", "on")


def op3_available() -> bool:
    """Check whether op3 is installed."""
    try:
        import opstree  # noqa: F401
        return True
    except ImportError:
        return False


def should_use_op3() -> bool:
    """Use op3 only when both flag is on and library is available."""
    return op3_enabled() and op3_available()


def require_op3(feature: str) -> None:
    """Raise :class:`RuntimeError` with a helpful install hint.

    Use at the top of any code path that unconditionally needs op3.
    """
    if op3_available():
        return
    raise RuntimeError(
        f"{feature} requires op3. Install with: pip install 'redeploy[op3]'"
    )


# ── scanner + context helpers ────────────────────────────────────────────


def make_scanner(
    layer_ids: Optional[Sequence[str]] = None,
    *,
    extra_probes: Optional[dict[str, list["Probe"]]] = None,
) -> "LinearScanner":
    """Return a fully-wired op3 :class:`LinearScanner`.

    Delegates to :func:`opstree.build_scanner` (0.1.8+), which handles
    transitive layer dependency resolution and per-scanner probe
    isolation. When ``layer_ids`` is omitted we fall back to
    :data:`DEFAULT_HARDWARE_LAYERS` because the historical consumer is
    the ``redeploy hardware`` command.
    """
    from opstree.scanner.build import build_scanner as _op3_build_scanner

    requested = list(layer_ids) if layer_ids else list(DEFAULT_HARDWARE_LAYERS)
    return _op3_build_scanner(requested, extra_probes=extra_probes)


def make_ssh_context(target: str, ssh_key: Optional[str] = None) -> "SSHContext":
    """Build an :class:`opstree.SSHContext` from redeploy-style arguments."""
    from opstree.probes.context import SSHContext

    return SSHContext(target=target, ssh_key_path=ssh_key)


def make_op3_context_from_ssh_client(ssh_client) -> "SSHContext":
    """Convert :class:`redeploy.ssh.SshClient` -> :class:`opstree.SSHContext`.

    ``SshClient.host`` is already the ``user@ip`` string op3 expects as
    ``target``; the key is resolved lazily via the property so we read it
    here once and forward to op3.
    """
    return make_ssh_context(target=ssh_client.host, ssh_key=ssh_client.key)


def make_mock_context(responses: dict[str, tuple[str, str, int]]) -> "ProbeContext":
    """Build an :class:`opstree.MockContext` used in tests.

    ``responses`` maps a command string to a ``(stdout, stderr, returncode)``
    triple — the same shape doql's bridge uses.
    """
    from opstree.probes.context import ExecuteResult, MockContext

    normalised = {
        cmd: ExecuteResult(stdout=out, stderr=err, returncode=rc)
        for cmd, (out, err, rc) in responses.items()
    }
    return MockContext(responses=normalised)


def snapshot_to_infra_state(snapshot: "Snapshot") -> "InfraState":
    """Convert opstree.Snapshot -> redeploy.InfraState (backward compat)."""
    from redeploy.models import InfraState

    runtime_data = snapshot.layer("runtime.container")
    service_data = snapshot.layer("service.containers")
    endpoint_data = snapshot.layer("endpoint.http")

    # TODO: full mapping once layer schemas stabilise
    return InfraState(
        runtime=runtime_data.data if runtime_data else {},
        services=service_data.data if service_data else {},
        endpoints=endpoint_data.data if endpoint_data else {},
    )


def snapshot_to_hardware_info(snapshot: "Snapshot") -> "HardwareInfo":
    """Convert opstree.Snapshot -> redeploy.HardwareInfo."""
    from redeploy.models import HardwareInfo, DrmOutput, BacklightInfo

    physical = snapshot.layer("physical.display")
    os_kernel = snapshot.layer("os.kernel")
    os_config = snapshot.layer("os.config")

    if physical is None:
        return HardwareInfo()

    # Map DRM outputs (op3 field names differ slightly from redeploy)
    drm_raw = physical.data.get("drm_outputs", [])
    drm_outputs = []
    for d in drm_raw:
        drm_outputs.append(DrmOutput(
            name=d.get("name", ""),
            connector=d.get("connector", ""),
            status=d.get("status", "unknown"),
            enabled=d.get("enabled", "unknown"),
            modes=d.get("modes", []),
            transform=d.get("transform", "normal"),
            position=d.get("position", "0,0"),
            scale=d.get("scale", "1.0"),
            edid_bytes=d.get("edid_bytes", 0),
            power_state=d.get("dpms"),
            sysfs_path=f"/sys/class/drm/{d.get('name', '')}",
        ))

    # Map backlights
    bl_raw = physical.data.get("backlights", [])
    backlights = []
    for b in bl_raw:
        backlights.append(BacklightInfo(
            name=b.get("name", ""),
            brightness=b.get("brightness", 0),
            max_brightness=b.get("max_brightness", 255),
            bl_power=b.get("bl_power", 0),
            display_name=b.get("display_name"),
            sysfs_path=f"/sys/class/backlight/{b.get('name', '')}",
        ))

    return HardwareInfo(
        board=physical.data.get("board_model"),
        kernel=os_kernel.data.get("version") if os_kernel else None,
        config_txt=os_config.data.get("config_txt", "") if os_config else "",
        config_txt_path=os_config.data.get("config_txt_path", "/boot/firmware/config.txt") if os_config else "/boot/firmware/config.txt",
        drm_outputs=drm_outputs,
        backlights=backlights,
        framebuffers=physical.data.get("framebuffers", []),
    )

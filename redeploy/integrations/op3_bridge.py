"""Bridge between redeploy and op3.

All adapters go through here. This module isolates op3 usage so that redeploy
remains runnable when op3 is not installed.

The feature-detect / scanner-factory / context helpers are produced by
:func:`opstree.integrations.make_compat_helpers` — they were previously
copy-pasted between doql and redeploy. Only redeploy-specific snapshot
adapters live here now.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Sequence

from opstree.integrations import make_compat_helpers

if TYPE_CHECKING:
    from opstree.probes.context import SSHContext
    from opstree.snapshot.model import Snapshot
    from redeploy.models import InfraState, HardwareInfo, DeviceMap

OP3_ENABLED_ENV = "REDEPLOY_USE_OP3"

# Redeploy-specific default layer set — hardware-focused because that is
# where the legacy ``redeploy hardware`` command lives.
DEFAULT_HARDWARE_LAYERS: tuple[str, ...] = (
    "physical.display",
    "os.kernel",
    "os.config",
)


# ── feature detection + factory helpers (shared via op3) ────────────────

_H = make_compat_helpers(
    env_var=OP3_ENABLED_ENV,
    default_layers=DEFAULT_HARDWARE_LAYERS,
    install_hint="pip install 'redeploy[op3]'",
)

op3_available = _H.op3_available
op3_enabled = _H.op3_enabled
should_use_op3 = _H.should_use_op3
require_op3 = _H.require_op3
make_ssh_context = _H.make_ssh_context
make_mock_context = _H.make_mock_context
make_scanner = _H.make_scanner


def make_op3_context_from_ssh_client(ssh_client) -> "SSHContext":
    """Convert :class:`redeploy.ssh.SshClient` -> :class:`opstree.SSHContext`.

    ``SshClient.host`` is already the ``user@ip`` string op3 expects as
    ``target``; the key is resolved lazily via the property so we read it
    here once and forward to op3.
    """
    return make_ssh_context(target=ssh_client.host, ssh_key=ssh_client.key)


def snapshot_to_infra_state(
    snapshot: "Snapshot",
    host: str = "",
) -> "InfraState":
    """Convert opstree.Snapshot -> redeploy.InfraState (backward compat).

    Only ``host`` is mapped for now — ``runtime``/``services`` layer
    schemas haven't been aligned between op3 probes and the pydantic
    models, so we leave them at their defaults instead of passing
    incompatible dicts that would fail validation.  Raw layer data is
    stashed under ``raw`` so downstream code can still inspect it.
    """
    from redeploy.models import InfraState

    raw: dict[str, dict] = {}
    for layer_id in ("runtime.container", "service.containers", "endpoint.http"):
        layer = snapshot.layer(layer_id)
        if layer is not None:
            raw[layer_id] = layer.data

    return InfraState(host=host, raw=raw)


def snapshot_to_hardware_info(snapshot: "Snapshot") -> "HardwareInfo":
    """Convert opstree.Snapshot -> redeploy.HardwareInfo."""
    from redeploy.models import HardwareInfo, DrmOutput, BacklightInfo, I2CBusInfo

    physical = snapshot.layer("physical.display")
    os_kernel = snapshot.layer("os.kernel")
    os_config = snapshot.layer("os.config")

    if physical is None:
        return HardwareInfo()

    pdata = physical.data

    drm_outputs = [
        DrmOutput(
            name=d.get("name", ""),
            connector=d.get("connector", ""),
            status=d.get("status", "unknown"),
            enabled=d.get("enabled", "unknown"),
            modes=d.get("modes", []),
            transform=d.get("transform", "normal"),
            position=d.get("position", "0,0"),
            scale=d.get("scale", "1.0"),
            edid_bytes=d.get("edid_bytes", 0),
            power_state=d.get("power_state") or d.get("dpms"),
            sysfs_path=d.get("sysfs_path", f"/sys/class/drm/{d.get('name', '')}"),
        )
        for d in pdata.get("drm_outputs", [])
    ]

    backlights = [
        BacklightInfo(
            name=b.get("name", ""),
            brightness=b.get("brightness", 0),
            max_brightness=b.get("max_brightness", 255),
            bl_power=b.get("bl_power", 0),
            display_name=b.get("display_name"),
            sysfs_path=b.get("sysfs_path", f"/sys/class/backlight/{b.get('name', '')}"),
        )
        for b in pdata.get("backlights", [])
    ]

    i2c_buses = [
        I2CBusInfo(
            bus=b.get("bus", 0),
            devices=b.get("devices", []),
            sysfs_path=b.get("sysfs_path", f"/dev/i2c-{b.get('bus', 0)}"),
        )
        for b in pdata.get("i2c_buses", [])
    ]

    return HardwareInfo(
        board=pdata.get("board_model"),
        kernel=pdata.get("kernel") or (os_kernel.data.get("version") if os_kernel else None),
        config_txt=pdata.get("config_txt", "") or (os_config.data.get("config_txt", "") if os_config else ""),
        config_txt_path=pdata.get("config_txt_path", "/boot/firmware/config.txt"),
        dsi_overlays=pdata.get("dsi_overlays", []),
        drm_outputs=drm_outputs,
        wlr_outputs=pdata.get("wlr_outputs", []),
        backlights=backlights,
        framebuffers=pdata.get("framebuffers", []),
        i2c_buses=i2c_buses,
        dsi_dmesg=pdata.get("dsi_dmesg", []),
        dsi_dmesg_errors=pdata.get("dsi_dmesg_errors", []),
        kernel_modules=pdata.get("kernel_modules", []),
        wayland_sockets=pdata.get("wayland_sockets", []),
        compositor_processes=pdata.get("compositor_processes", {}),
    )

def diagnostics_to_hardware_diagnostics(
    diagnostics: list,
) -> list:
    """Convert op3 :class:`opstree.diagnostics.Diagnostic` -> redeploy :class:`redeploy.models.HardwareDiagnostic`."""
    from redeploy.models import HardwareDiagnostic

    result: list = []
    for d in diagnostics:
        # d may be an opstree.diagnostics.Diagnostic dataclass instance or dict
        if isinstance(d, dict):
            result.append(HardwareDiagnostic(**d))
        else:
            result.append(HardwareDiagnostic(
                component=getattr(d, "component", "unknown"),
                severity=getattr(d, "severity", "warning"),
                message=getattr(d, "message", ""),
                fix=getattr(d, "fix", None),
            ))
    return result


def snapshot_to_device_map(
    snapshot: "Snapshot",
    host: str,
    tags: "Optional[Sequence[str]]" = None,
) -> "DeviceMap":
    """Convert opstree.Snapshot -> redeploy.DeviceMap.

    Pulls the hardware and infra layers already mapped by
    :func:`snapshot_to_hardware_info` and :func:`snapshot_to_infra_state`,
    then wraps them in a :class:`DeviceMap` with a UTC timestamp.
    """
    from datetime import datetime, timezone
    from redeploy.models import DeviceMap

    hw = snapshot_to_hardware_info(snapshot)
    infra = snapshot_to_infra_state(snapshot, host=host)

    # op3 snapshots expose *probed_at* on individual LayerData entries;
    # fall back to the snapshot-level timestamp when available.
    probed_at = getattr(snapshot, "timestamp", None)
    if probed_at is None and hasattr(snapshot, "layers"):
        for layer in snapshot.layers:
            if getattr(layer, "probed_at", None):
                probed_at = layer.probed_at
                break
    timestamp = probed_at or datetime.now(timezone.utc)

    return DeviceMap(
        id=host.replace("@", "_at_").replace(":", "_"),
        host=host,
        scanned_at=timestamp,
        hardware=hw,
        infra=infra,
        tags=list(tags) if tags else [],
    )

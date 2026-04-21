"""Bridge between redeploy and op3.

All adapters go through here. This module isolates op3 usage so that redeploy
remains runnable when op3 is not installed.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from opstree.probes.context import SSHContext
    from opstree.snapshot.model import Snapshot
    from redeploy.models import InfraState, HardwareInfo

OP3_ENABLED_ENV = "REDEPLOY_USE_OP3"


def op3_enabled() -> bool:
    """Check whether the user wants to use op3."""
    return os.environ.get(OP3_ENABLED_ENV, "0").lower() in ("1", "true", "yes")


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


def make_op3_context_from_ssh_client(ssh_client) -> "SSHContext":
    """Convert redeploy.SshClient -> opstree.SSHContext."""
    from opstree.probes.context import SSHContext

    return SSHContext(
        target=ssh_client.target,
        host=ssh_client.host,
        user=ssh_client.user,
        ssh_key=ssh_client.ssh_key,
    )


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

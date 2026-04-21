"""Apply a declarative config dict or file to a remote host."""
from __future__ import annotations

from pathlib import Path

from rich.console import Console

from ..apply.state_apply import apply_state, ApplyResult
from ..detect.remote import RemoteProbe
from .loader import load_config_file


def _normalize_hardware(data: dict) -> dict:
    """Flatten nested hardware configs for state_apply handlers.

    DeviceMap and DeviceBlueprint nest hardware under a ``hardware`` key,
    while ``redeploy hardware`` produces a flat file.  This helper makes
    both shapes palatable for :func:`apply_state`.
    """
    if "drm_outputs" in data or "backlights" in data:
        return data
    hw = data.get("hardware")
    if isinstance(hw, dict):
        return hw
    return data


def apply_config_dict(data: dict, probe: RemoteProbe, console: Console) -> ApplyResult:
    """Apply *data* to the host behind *probe*.

    Delegates to :func:`redeploy.apply.state_apply.apply_state` after
    normalising nested ``hardware`` sections.
    """
    normalized = _normalize_hardware(data)
    return apply_state(normalized, probe, console)


def apply_config_file(
    path: str | Path,
    *,
    host: str | None = None,
    ssh_key: str | None = None,
    console: Console | None = None,
) -> ApplyResult:
    """Load *path* and apply its hardware/infra settings to the remote host.

    Parameters
    ----------
    path:
        Local YAML/JSON file (DeviceMap, DeviceBlueprint, or flat hardware dump).
    host:
        Optional SSH target.  Falls back to ``data["host"]``.
    ssh_key:
        Private-key path for the SSH connection.
    console:
        Rich console for progress output.  Created automatically when ``None``.

    Raises
    ------
    ValueError
        If no host can be determined (neither *host* nor ``data["host"]``).
    """
    data = load_config_file(path)
    _host = host or data.get("host")
    if not _host:
        raise ValueError("No host specified and no 'host' field in config file")

    if console is None:
        console = Console()

    probe = RemoteProbe(_host, ssh_key=ssh_key)
    return apply_config_dict(data, probe, console)

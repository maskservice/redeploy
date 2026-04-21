"""Contract test: hardware command output is identical in legacy and op3 paths."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
import yaml
from click.testing import CliRunner

from redeploy.cli.commands.hardware import hardware
from redeploy.integrations.op3_bridge import snapshot_to_hardware_info, op3_available
from redeploy.models import HardwareInfo, DrmOutput

op3 = pytest.importorskip("opstree")


@pytest.fixture
def mock_hw() -> HardwareInfo:
    """Deterministic hardware state used for both paths."""
    return HardwareInfo(
        board="Raspberry Pi 5 Model B Rev 1.0",
        kernel="6.6.20+rpt-rpi-2712",
        config_txt="dtparam=audio=on\ndtoverlay=vc4-kms-v3d\n",
        config_txt_path="/boot/firmware/config.txt",
        drm_outputs=[
            DrmOutput(
                name="card1-DSI-1",
                connector="DSI-1",
                status="connected",
                enabled="enabled",
                edid_bytes=128,
                power_state="on",
            ),
        ],
        backlights=[],
    )


def _make_mock_probe_hardware_op3(hw: HardwareInfo):
    """Return a replacement for _probe_hardware_op3 that yields *hw*."""
    def _fn(host, ssh_key, console):
        return hw
    return _fn


def _normalize(data: dict) -> dict:
    """Drop empty defaults so missing vs empty lists don't differ."""
    def clean(v):
        if isinstance(v, dict):
            return {k: clean(vv) for k, vv in v.items() if vv not in (None, [], {}, "")}
        if isinstance(v, list):
            return [clean(vv) for vv in v]
        return v
    return clean(data)


def test_hardware_yaml_parity(mock_hw: HardwareInfo, monkeypatch):
    """Legacy and op3 paths must produce semantically identical YAML."""
    runner = CliRunner()

    # Legacy path
    monkeypatch.setenv("REDEPLOY_USE_OP3", "0")
    monkeypatch.setattr(
        "redeploy.detect.hardware.probe_hardware",
        lambda p: mock_hw,
    )

    legacy_result = runner.invoke(hardware, ["pi@mock.local", "--format", "yaml"])
    assert legacy_result.exit_code == 0, legacy_result.output

    # op3 path
    monkeypatch.setenv("REDEPLOY_USE_OP3", "1")
    monkeypatch.setattr(
        "redeploy.cli.commands.hardware._probe_hardware_op3",
        _make_mock_probe_hardware_op3(mock_hw),
    )

    op3_result = runner.invoke(hardware, ["pi@mock.local", "--format", "yaml"])
    assert op3_result.exit_code == 0, op3_result.output

    legacy_data = yaml.safe_load(legacy_result.output)
    op3_data = yaml.safe_load(op3_result.output)

    assert _normalize(legacy_data) == _normalize(op3_data)

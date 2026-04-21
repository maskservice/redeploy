"""Contract test: hardware command yields deterministic YAML from op3-backed probe.

The legacy-vs-op3 dual code path was collapsed in redeploy ≥ 0.1.x
(``REDEPLOY_USE_OP3`` is a no-op now — both branches used op3 internally).
This test now just guards the single code path against shape regressions.
"""
from __future__ import annotations

import pytest
import yaml
from click.testing import CliRunner

from redeploy.cli.commands.hardware import hardware
from redeploy.models import HardwareInfo, DrmOutput

op3 = pytest.importorskip("opstree")


@pytest.fixture
def mock_hw() -> HardwareInfo:
    """Deterministic hardware state injected into the CLI."""
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


def test_hardware_yaml_shape(mock_hw: HardwareInfo, monkeypatch):
    """CLI renders HardwareInfo as YAML containing the expected top-level keys."""
    runner = CliRunner()

    monkeypatch.setattr(
        "redeploy.detect.hardware.probe_hardware",
        lambda p: mock_hw,
    )

    result = runner.invoke(hardware, ["pi@mock.local", "--format", "yaml"])
    assert result.exit_code == 0, result.output

    data = yaml.safe_load(result.output)
    assert data["board"] == "Raspberry Pi 5 Model B Rev 1.0"
    assert data["kernel"] == "6.6.20+rpt-rpi-2712"
    assert data["drm_outputs"][0]["connector"] == "DSI-1"

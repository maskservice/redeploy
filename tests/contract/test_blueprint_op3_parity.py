"""Contract test: blueprint extraction parity between legacy Detector and op3 scanner."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from redeploy.integrations.op3_bridge import (
    make_mock_context,
    make_scanner,
    op3_available,
    snapshot_to_device_map,
)
from redeploy.models import DeviceMap, InfraState, HardwareInfo

op3 = pytest.importorskip("opstree")


@pytest.fixture
def mock_device_map() -> DeviceMap:
    """Deterministic device-map used for both paths."""
    return DeviceMap(
        id="pi_at_mock.local",
        host="pi@mock.local",
        scanned_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        hardware=HardwareInfo(board="Raspberry Pi 5 Model B Rev 1.0"),
        infra=InfraState(host="pi@mock.local"),
        tags=["test"],
    )


def _build_mock_snapshot():
    """Build an op3 Snapshot that converts to the same DeviceMap."""
    board = "Raspberry Pi 5 Model B Rev 1.0"
    responses = {
        # RpiPhysicalDisplayProbe.can_probe()
        "test -f /sys/firmware/devicetree/base/model && "
        "cat /sys/firmware/devicetree/base/model":
            (board, "", 0),
        # _probe_board_model
        "cat /sys/firmware/devicetree/base/model 2>/dev/null | tr -d '\\0'":
            (board, "", 0),
        # OsKernelProbe.can_probe() + fields
        "uname -s": ("Linux", "", 0),
        "uname -r": ("6.6.20+rpt-rpi-2712", "", 0),
        "uname -m": ("aarch64", "", 0),
        "hostname": ("mock", "", 0),
        "cat /proc/uptime": ("12345.67 1000.00", "", 0),
        # OsConfigProbe.can_probe() shares uname -s; config.txt reads:
        "cat /boot/firmware/config.txt 2>/dev/null": ("", "", 0),
        "cat /boot/config.txt 2>/dev/null": ("", "", 0),
        "cat /proc/cmdline 2>/dev/null": ("", "", 0),
    }
    ctx = make_mock_context(responses)
    scanner = make_scanner(["physical.display", "os.kernel", "os.config"])
    return scanner.scan("pi@mock.local", ctx.execute)


def test_snapshot_to_device_map_roundtrip(mock_device_map: DeviceMap):
    """op3 snapshot → DeviceMap must preserve host and hardware board."""
    snapshot = _build_mock_snapshot()
    dm = snapshot_to_device_map(
        snapshot,
        host=mock_device_map.host,
        tags=mock_device_map.tags,
    )
    assert dm.host == mock_device_map.host
    assert dm.hardware.board == mock_device_map.hardware.board
    assert dm.tags == mock_device_map.tags
    assert dm.infra is not None

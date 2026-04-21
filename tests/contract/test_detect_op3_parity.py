"""Contract test: detect infra snapshot parity between legacy Detector and op3."""
from __future__ import annotations

import pytest

from redeploy.integrations.op3_bridge import (
    make_mock_context,
    make_scanner,
    op3_available,
    snapshot_to_infra_state,
)
from redeploy.models import InfraState

op3 = pytest.importorskip("opstree")


@pytest.fixture
def mock_infra() -> InfraState:
    return InfraState(
        host="pi@mock.local",
        services={"systemd": []},
    )


def _build_mock_snapshot():
    """Build an op3 Snapshot that converts to the same InfraState."""
    # Minimal responses for runtime/service/endpoint layers
    responses = {
        "docker ps --format json 2>/dev/null || true": ("[]", "", 0),
        "systemctl list-units --type=service --state=running --no-pager 2>/dev/null || true":
            ("", "", 0),
        "curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/health 2>/dev/null || true":
            ("200", "", 0),
    }
    ctx = make_mock_context(responses)
    scanner = make_scanner(
        ["runtime.container", "service.containers", "endpoint.http", "business.health"]
    )
    return scanner.scan("pi@mock.local", ctx.execute)


def test_snapshot_to_infra_state_parity(mock_infra: InfraState):
    """op3 snapshot → InfraState must preserve host and keys."""
    snapshot = _build_mock_snapshot()
    infra = snapshot_to_infra_state(snapshot, host=mock_infra.host)
    assert infra.host == mock_infra.host
    # shape must match InfraState model
    from redeploy.models import RuntimeInfo
    assert isinstance(infra.runtime, RuntimeInfo)
    assert isinstance(infra.services, dict)
    assert isinstance(infra.raw, dict)

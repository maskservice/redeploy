"""Smoke tests that redeploy and op3 can talk to each other."""
from __future__ import annotations

import pytest
from redeploy.integrations.op3_bridge import op3_available, should_use_op3


@pytest.mark.skipif(not op3_available(), reason="op3 not installed")
def test_op3_importable():
    import opstree

    assert hasattr(opstree, "LayerTree")
    assert hasattr(opstree, "Snapshot")


@pytest.mark.skipif(not op3_available(), reason="op3 not installed")
def test_op3_mock_scan():
    """Test that we can run an op3 scan through a mock context."""
    from opstree.probes.context import MockContext
    from opstree.layers.tree import LayerTree
    from opstree.layers.builtin import PhysicalLayer
    from opstree.scanner.linear import LinearScanner
    from opstree.probes.builtin.physical_rpi import RpiPhysicalDisplayProbe
    from opstree.probes.registry import ProbeRegistry

    ctx = MockContext(
        responses={
            "cat /sys/firmware/devicetree/base/model": ("Raspberry Pi 5 Model B", "", 0),
        },
        metadata={"target": "test"},
    )

    tree = LayerTree()
    tree.register(PhysicalLayer.display)

    registry = ProbeRegistry()
    registry.register(RpiPhysicalDisplayProbe())

    scanner = LinearScanner(tree)
    scanner.probe_registry = registry

    snapshot = scanner.scan("test", ctx.execute)
    assert snapshot is not None
    assert snapshot.target == "test"

"""Tests for redeploy.blueprint.sources (migration, hardware, infra)."""
from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from redeploy.blueprint.sources.hardware import build_hw_requirements
from redeploy.blueprint.sources.infra import extract_services_from_infra, infer_app_url
from redeploy.blueprint.sources.migration import parse_migration_meta


class FakeHw:
    """Minimal fake hardware probe result."""

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestParseMigrationMeta:
    def test_reads_version_and_strategy(self, tmp_path: Path):
        p = tmp_path / "migration.yaml"
        p.write_text(textwrap.dedent("""\
            version: 1.2.3
            strategy: docker_compose
        """))
        meta = parse_migration_meta(p)
        assert meta["version"] == "1.2.3"
        assert meta["strategy"] == "docker_compose"

    def test_infers_podman_quadlet_from_steps(self, tmp_path: Path):
        p = tmp_path / "migration.yaml"
        p.write_text(textwrap.dedent("""\
            version: 2.0.0
            steps:
              - action: start_podman_quadlet
        """))
        meta = parse_migration_meta(p)
        assert meta["strategy"] == "podman_quadlet"

    def test_infers_docker_from_steps(self, tmp_path: Path):
        p = tmp_path / "migration.yaml"
        p.write_text(textwrap.dedent("""\
            steps:
              - action: docker_compose_up
        """))
        meta = parse_migration_meta(p)
        assert meta["strategy"] == "docker_compose"

    def test_missing_file_returns_empty(self, tmp_path: Path):
        meta = parse_migration_meta(tmp_path / "missing.yaml")
        assert meta == {}

    def test_invalid_yaml_returns_empty(self, tmp_path: Path):
        p = tmp_path / "bad.yaml"
        p.write_text("not: valid: [")
        meta = parse_migration_meta(p)
        assert meta == {}

    def test_no_strategy_or_version_returns_empty(self, tmp_path: Path):
        p = tmp_path / "migration.yaml"
        p.write_text("steps: []\n")
        meta = parse_migration_meta(p)
        assert meta == {}


class TestBuildHwRequirements:
    def test_none_returns_empty(self):
        req = build_hw_requirements(None)
        assert req.arch == "linux/arm64"  # model default
        assert req.display_type is None
        assert req.features == []

    def test_dsi_detected(self):
        output = MagicMock()
        output.connector = "DSI-1"
        output.modes = ["800x480"]
        hw = FakeHw(drm_outputs=[output], dsi_overlays=["dsi7-inch"])
        req = build_hw_requirements(hw)
        assert req.display_type == "DSI"
        assert req.display_resolution == "800x480"
        assert "wayland" in req.features

    def test_backlight_and_i2c_features(self):
        bl = MagicMock()
        i2c = MagicMock()
        hw = FakeHw(backlights=[bl], i2c_buses=[i2c])
        req = build_hw_requirements(hw)
        assert "backlight" in req.features
        assert "i2c" in req.features
        assert req.i2c_required is True

    def test_rpi_arch(self):
        hw = FakeHw(board="Raspberry Pi 5")
        req = build_hw_requirements(hw)
        assert req.arch == "linux/arm64"

    def test_aarch64_arch(self):
        hw = FakeHw(board="aarch64-pc")
        req = build_hw_requirements(hw)
        assert req.arch == "linux/arm64"

    def test_non_pi_arch(self):
        hw = FakeHw(board="x86_64-server")
        req = build_hw_requirements(hw)
        assert req.arch == ""


class FakeSvc:
    def __init__(self, name: str, image: str = "") -> None:
        self.name = name
        self.image = image


class FakeInfra:
    def __init__(self, host: str = "", ports: dict[int, Any] | None = None, services: dict[str, list] | None = None) -> None:
        self.host = host
        self.ports = ports or {}
        self.services = services or {}


class TestExtractServicesFromInfra:
    def test_empty_infra(self):
        infra = FakeInfra()
        seen: set[str] = set()
        result = extract_services_from_infra(infra, seen)  # type: ignore[arg-type]
        assert result == []

    def test_extracts_services(self):
        infra = FakeInfra(services={"podman": [FakeSvc("web", "nginx")]})
        seen: set[str] = set()
        result = extract_services_from_infra(infra, seen)  # type: ignore[arg-type]
        assert len(result) == 1
        assert result[0].name == "web"
        assert result[0].image == "nginx"
        assert result[0].source_ref == "infra:live"

    def test_skips_already_seen(self):
        infra = FakeInfra(services={"podman": [FakeSvc("web")]})
        seen: set[str] = {"web"}
        result = extract_services_from_infra(infra, seen)  # type: ignore[arg-type]
        assert result == []
        assert "web" in seen

    def test_multiple_groups(self):
        infra = FakeInfra(services={
            "podman": [FakeSvc("web")],
            "systemd": [FakeSvc("backend")],
        })
        seen: set[str] = set()
        result = extract_services_from_infra(infra, seen)  # type: ignore[arg-type]
        assert len(result) == 2
        assert {s.name for s in result} == {"web", "backend"}


class TestInferAppUrl:
    def test_none_infra(self):
        assert infer_app_url(None) is None  # type: ignore[arg-type]

    def test_no_host(self):
        infra = FakeInfra()
        assert infer_app_url(infra) is None  # type: ignore[arg-type]

    def test_port_80(self):
        infra = FakeInfra(host="pi@192.168.1.5", ports={80: True})
        assert infer_app_url(infra) == "http://192.168.1.5"  # type: ignore[arg-type]

    def test_port_443(self):
        infra = FakeInfra(host="pi@192.168.1.5", ports={443: True})
        assert infer_app_url(infra) == "https://192.168.1.5"  # type: ignore[arg-type]

    def test_port_8100(self):
        infra = FakeInfra(host="pi@192.168.1.5", ports={8100: True})
        assert infer_app_url(infra) == "http://192.168.1.5:8100"  # type: ignore[arg-type]

    def test_no_matching_ports(self):
        infra = FakeInfra(host="pi@192.168.1.5", ports={22: True})
        assert infer_app_url(infra) is None  # type: ignore[arg-type]

    def test_strips_user_from_host(self):
        infra = FakeInfra(host="admin@server.local", ports={80: True})
        assert infer_app_url(infra) == "http://server.local"  # type: ignore[arg-type]

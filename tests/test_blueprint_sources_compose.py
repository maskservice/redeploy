"""Tests for redeploy.blueprint.sources.compose."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from redeploy.blueprint.sources.compose import (
    _merge_compose,
    _parse_compose_env,
    _parse_compose_healthcheck,
    _parse_compose_ports,
    _parse_compose_volumes,
    merge_compose_files,
)
from redeploy.models import ServicePort, ServiceSpec, VolumeMount


@pytest.fixture
def compose_file(tmp_path: Path) -> Path:
    p = tmp_path / "docker-compose.yml"
    p.write_text(textwrap.dedent("""\
        services:
          web:
            image: nginx:latest
            ports:
              - "8080:80"
            volumes:
              - ./html:/usr/share/nginx/html:ro
            environment:
              DEBUG: "true"
          db:
            image: postgres:15
            healthcheck:
              test: ["CMD", "pg_isready", "-U", "postgres"]
    """))
    return p


class TestMergeComposeFiles:
    def test_parses_services(self, compose_file):
        services: list[ServiceSpec] = []
        seen: set[str] = set()
        merge_compose_files([compose_file], services, seen)
        assert len(services) == 2
        names = {s.name for s in services}
        assert names == {"web", "db"}

    def test_populates_seen(self, compose_file):
        services: list[ServiceSpec] = []
        seen: set[str] = set()
        merge_compose_files([compose_file], services, seen)
        assert seen == {"web", "db"}

    def test_noop_on_empty_list(self):
        services: list[ServiceSpec] = []
        seen: set[str] = set()
        merge_compose_files([], services, seen)
        assert services == []
        assert seen == set()

    def test_skips_missing_file(self, tmp_path):
        services: list[ServiceSpec] = []
        seen: set[str] = set()
        merge_compose_files([tmp_path / "missing.yml"], services, seen)
        assert services == []

    def test_skips_invalid_yaml(self, tmp_path):
        p = tmp_path / "bad.yml"
        p.write_text("not: valid: yaml: [")
        services: list[ServiceSpec] = []
        seen: set[str] = set()
        merge_compose_files([p], services, seen)
        # yaml.safe_load may or may not raise on this; either way no services
        assert "web" not in {s.name for s in services}

    def test_merges_duplicate_service(self, compose_file):
        services: list[ServiceSpec] = []
        seen: set[str] = set()
        _merge_compose(compose_file, services, seen)
        # Second call with same file should merge, not duplicate
        _merge_compose(compose_file, services, seen)
        assert len(services) == 2
        web = next(s for s in services if s.name == "web")
        assert web.source_ref == str(compose_file)


class TestParseComposePorts:
    def test_int_form(self):
        assert _parse_compose_ports([80]) == [ServicePort(host=80, container=80, protocol="tcp")]

    def test_string_form(self):
        assert _parse_compose_ports(["8080:80"]) == [ServicePort(host=8080, container=80, protocol="tcp")]

    def test_string_with_protocol(self):
        assert _parse_compose_ports(["8080:80/udp"]) == [ServicePort(host=8080, container=80, protocol="udp")]

    def test_dict_form(self):
        assert _parse_compose_ports([{"published": 8080, "target": 80, "protocol": "tcp"}]) == [
            ServicePort(host=8080, container=80, protocol="tcp")
        ]

    def test_dict_form_defaults(self):
        assert _parse_compose_ports([{"target": 80}]) == [ServicePort(host=80, container=80, protocol="tcp")]

    def test_mixed_list(self):
        result = _parse_compose_ports([80, "8080:80/tcp", {"target": 443}])
        assert len(result) == 3


class TestParseComposeVolumes:
    def test_string_form(self):
        assert _parse_compose_volumes(["./data:/app/data"]) == [
            VolumeMount(host="./data", container="/app/data", read_only=False)
        ]

    def test_string_form_readonly(self):
        assert _parse_compose_volumes(["./html:/usr/share/nginx/html:ro"]) == [
            VolumeMount(host="./html", container="/usr/share/nginx/html", read_only=True)
        ]

    def test_dict_form(self):
        assert _parse_compose_volumes([{"source": "vol1", "target": "/data", "read_only": True}]) == [
            VolumeMount(host="vol1", container="/data", read_only=True)
        ]

    def test_dict_input(self):
        assert _parse_compose_volumes({"vol1": "/data"}) == [
            VolumeMount(host="vol1", container="/data", read_only=False)
        ]


class TestParseComposeEnv:
    def test_dict_form(self):
        assert _parse_compose_env({"DEBUG": "true", "PORT": 80}) == {"DEBUG": "true", "PORT": "80"}

    def test_list_form(self):
        assert _parse_compose_env(["DEBUG=true", "PORT=80"]) == {"DEBUG": "true", "PORT": "80"}

    def test_skips_none_values(self):
        assert _parse_compose_env({"X": None, "Y": "z"}) == {"Y": "z"}


class TestParseComposeHealthcheck:
    def test_list_test(self):
        assert _parse_compose_healthcheck({"test": ["CMD", "pg_isready", "-U", "postgres"]}) == "pg_isready -U postgres"

    def test_string_test(self):
        assert _parse_compose_healthcheck({"test": "curl -f http://localhost"}) == "curl -f http://localhost"

    def test_empty_returns_none(self):
        assert _parse_compose_healthcheck({}) is None

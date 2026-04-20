"""Tests for redeploy.iac — pluggable IaC/CI-CD parsers (Faza 0).

Covers:
  - ParsedSpec API
  - ParserRegistry dispatch
  - DockerComposeParser (Tier 1 proof-of-concept)
  - parse_file / parse_dir convenience helpers
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from redeploy.iac import (
    ParsedSpec,
    ParserRegistry,
    parse_dir,
    parse_file,
    parser_registry,
)
from redeploy.iac.base import PortInfo, ServiceInfo, VolumeInfo
from redeploy.iac.docker_compose import DockerComposeParser, _parse_port, _parse_volume


# ── helpers ────────────────────────────────────────────────────────────────────

def write_compose(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "docker-compose.yml"
    p.write_text(textwrap.dedent(content))
    return p


# ── ParsedSpec ─────────────────────────────────────────────────────────────────

class TestParsedSpec:
    def test_all_images_deduplicated(self):
        spec = ParsedSpec(source_file=Path("x.yml"), source_format="test")
        spec.images = ["nginx:latest", "postgres:15"]
        svc = ServiceInfo(name="web", image="nginx:latest")
        spec.services = [svc]
        imgs = spec.all_images()
        assert imgs.count("nginx:latest") == 1
        assert "postgres:15" in imgs

    def test_all_ports_deduplicated(self):
        spec = ParsedSpec(source_file=Path("x.yml"), source_format="test")
        p = PortInfo(container=80, host=8080)
        spec.ports = [p]
        svc = ServiceInfo(name="web", ports=[p])
        spec.services = [svc]
        assert len(spec.all_ports()) == 1

    def test_summary_shows_counts(self):
        spec = ParsedSpec(source_file=Path("compose.yml"), source_format="docker_compose")
        spec.services = [ServiceInfo(name="web", image="nginx")]
        s = spec.summary()
        assert "1 service" in s
        assert "docker_compose" in s

    def test_add_warning(self):
        spec = ParsedSpec(source_file=Path("x.yml"), source_format="test")
        spec.add_warning("something odd", severity="warn")
        assert len(spec.warnings) == 1
        assert "something odd" in str(spec.warnings[0])


# ── PortInfo / VolumeInfo parsers ──────────────────────────────────────────────

class TestPortParsing:
    def test_short_form_published(self):
        p = _parse_port("8080:80")
        assert p.container == 80
        assert p.host == 8080
        assert p.protocol == "tcp"

    def test_short_form_container_only(self):
        p = _parse_port("80")
        assert p.container == 80
        assert p.host is None

    def test_short_form_with_ip(self):
        p = _parse_port("127.0.0.1:8080:80")
        assert p.host_ip == "127.0.0.1"
        assert p.host == 8080

    def test_short_form_with_protocol(self):
        p = _parse_port("5353:5353/udp")
        assert p.protocol == "udp"
        assert p.container == 5353

    def test_long_form_dict(self):
        raw = {"target": 80, "published": "8080", "protocol": "tcp"}
        p = _parse_port(raw)
        assert p.container == 80

    def test_invalid_returns_none(self):
        assert _parse_port("not::a::port::spec") is None


class TestVolumeParsing:
    def test_bind_mount(self):
        v = _parse_volume("./data:/app/data")
        assert v.source_type == "bind"
        assert v.target == "/app/data"
        assert v.source == "./data"

    def test_named_volume(self):
        v = _parse_volume("pgdata:/var/lib/postgresql/data")
        assert v.source_type == "volume"

    def test_read_only(self):
        v = _parse_volume("/host:/container:ro")
        assert v.read_only is True

    def test_long_form(self):
        raw = {"type": "bind", "source": "./src", "target": "/code"}
        v = _parse_volume(raw)
        assert v.source_type == "bind"
        assert v.source == "./src"


# ── DockerComposeParser ────────────────────────────────────────────────────────

class TestDockerComposeParserCanParse:
    def setup_method(self):
        self.parser = DockerComposeParser()

    def test_standard_name(self, tmp_path):
        p = tmp_path / "docker-compose.yml"
        p.write_text("services:\n  web:\n    image: nginx\n")
        assert self.parser.can_parse(p)

    def test_compose_yaml(self, tmp_path):
        p = tmp_path / "compose.yaml"
        p.write_text("services:\n  api:\n    image: python:3.11\n")
        assert self.parser.can_parse(p)

    def test_heuristic_services_key(self, tmp_path):
        p = tmp_path / "infra.yml"
        p.write_text("services:\n  db:\n    image: postgres\n")
        assert self.parser.can_parse(p)

    def test_unrelated_yaml(self, tmp_path):
        p = tmp_path / "config.yml"
        p.write_text("key: value\nother: stuff\n")
        assert not self.parser.can_parse(p)


class TestDockerComposeParserBasic:
    def test_simple_service(self, tmp_path):
        p = write_compose(tmp_path, """\
            services:
              web:
                image: nginx:alpine
                ports:
                  - "80:80"
        """)
        spec = DockerComposeParser().parse(p)
        assert len(spec.services) == 1
        svc = spec.services[0]
        assert svc.name == "web"
        assert svc.image == "nginx:alpine"
        assert svc.ports[0].container == 80
        assert svc.ports[0].host == 80
        assert "docker" in spec.runtime_hints
        assert "nginx:alpine" in spec.images

    def test_multiple_services(self, tmp_path):
        p = write_compose(tmp_path, """\
            services:
              api:
                image: python:3.11
                ports: ["8000:8000"]
              db:
                image: postgres:15
                volumes:
                  - pgdata:/var/lib/postgresql/data
            volumes:
              pgdata:
        """)
        spec = DockerComposeParser().parse(p)
        assert len(spec.services) == 2
        names = {s.name for s in spec.services}
        assert names == {"api", "db"}

    def test_environment_list_form(self, tmp_path):
        p = write_compose(tmp_path, """\
            services:
              api:
                image: myapp
                environment:
                  - DEBUG=true
                  - PORT=8000
        """)
        spec = DockerComposeParser().parse(p)
        assert spec.services[0].env["DEBUG"] == "true"
        assert spec.services[0].env["PORT"] == "8000"

    def test_environment_dict_form(self, tmp_path):
        p = write_compose(tmp_path, """\
            services:
              api:
                image: myapp
                environment:
                  LOG_LEVEL: info
                  DB_HOST: localhost
        """)
        spec = DockerComposeParser().parse(p)
        assert spec.services[0].env["LOG_LEVEL"] == "info"

    def test_volumes_in_service(self, tmp_path):
        p = write_compose(tmp_path, """\
            services:
              app:
                image: myapp
                volumes:
                  - ./src:/app/src
                  - /tmp:/tmp:ro
        """)
        spec = DockerComposeParser().parse(p)
        vols = spec.services[0].volumes
        assert len(vols) == 2
        assert any(v.read_only for v in vols)

    def test_depends_on_list(self, tmp_path):
        p = write_compose(tmp_path, """\
            services:
              api:
                image: myapp
                depends_on: [db]
              db:
                image: postgres
        """)
        spec = DockerComposeParser().parse(p)
        api = next(s for s in spec.services if s.name == "api")
        assert "db" in api.depends_on

    def test_depends_on_dict_form(self, tmp_path):
        p = write_compose(tmp_path, """\
            services:
              api:
                image: myapp
                depends_on:
                  db:
                    condition: service_healthy
              db:
                image: postgres
        """)
        spec = DockerComposeParser().parse(p)
        api = next(s for s in spec.services if s.name == "api")
        assert "db" in api.depends_on

    def test_healthcheck(self, tmp_path):
        p = write_compose(tmp_path, """\
            services:
              api:
                image: myapp
                healthcheck:
                  test: ["CMD", "curl", "-f", "http://localhost/health"]
                  interval: 30s
        """)
        spec = DockerComposeParser().parse(p)
        assert spec.services[0].healthcheck is not None

    def test_named_volumes_top_level(self, tmp_path):
        p = write_compose(tmp_path, """\
            services:
              db:
                image: postgres
            volumes:
              pgdata:
              backups:
        """)
        spec = DockerComposeParser().parse(p)
        vol_sources = {v.source for v in spec.volumes}
        assert "pgdata" in vol_sources
        assert "backups" in vol_sources

    def test_networks_top_level(self, tmp_path):
        p = write_compose(tmp_path, """\
            services:
              app:
                image: myapp
            networks:
              frontend:
              backend:
        """)
        spec = DockerComposeParser().parse(p)
        assert "frontend" in spec.networks
        assert "backend" in spec.networks

    def test_env_file(self, tmp_path):
        p = write_compose(tmp_path, """\
            services:
              app:
                image: myapp
                env_file:
                  - .env.prod
        """)
        spec = DockerComposeParser().parse(p)
        assert ".env.prod" in spec.services[0].env_files

    def test_build_context(self, tmp_path):
        p = write_compose(tmp_path, """\
            services:
              app:
                build: ./backend
        """)
        spec = DockerComposeParser().parse(p)
        assert spec.services[0].build_context == "./backend"

    def test_build_dict_form(self, tmp_path):
        p = write_compose(tmp_path, """\
            services:
              app:
                build:
                  context: ./frontend
                  dockerfile: Dockerfile.prod
        """)
        spec = DockerComposeParser().parse(p)
        assert spec.services[0].build_context == "./frontend"

    def test_deploy_replicas(self, tmp_path):
        p = write_compose(tmp_path, """\
            services:
              worker:
                image: myworker
                deploy:
                  replicas: 3
        """)
        spec = DockerComposeParser().parse(p)
        assert spec.services[0].replicas == 3

    def test_variable_substitution(self, tmp_path):
        (tmp_path / ".env").write_text("APP_PORT=9000\n")
        p = write_compose(tmp_path, """\
            services:
              app:
                image: myapp
                ports:
                  - "${APP_PORT}:8000"
        """)
        spec = DockerComposeParser().parse(p)
        assert spec.services[0].ports[0].host == 9000

    def test_variable_default_fallback(self, tmp_path):
        p = write_compose(tmp_path, """\
            services:
              app:
                image: myapp:${TAG:-latest}
        """)
        spec = DockerComposeParser().parse(p)
        assert spec.services[0].image == "myapp:latest"

    def test_labels_dict(self, tmp_path):
        p = write_compose(tmp_path, """\
            services:
              app:
                image: myapp
                labels:
                  traefik.enable: "true"
                  traefik.http.routers.app.rule: "Host(`app.local`)"
        """)
        spec = DockerComposeParser().parse(p)
        assert spec.services[0].labels.get("traefik.enable") == "true"

    def test_restart_policy(self, tmp_path):
        p = write_compose(tmp_path, """\
            services:
              app:
                image: myapp
                restart: unless-stopped
        """)
        spec = DockerComposeParser().parse(p)
        assert spec.services[0].restart == "unless-stopped"

    def test_empty_file_returns_low_confidence(self, tmp_path):
        p = tmp_path / "docker-compose.yml"
        p.write_text("")
        spec = DockerComposeParser().parse(p)
        assert spec.confidence == 0.0

    def test_invalid_yaml_recorded_as_error(self, tmp_path):
        p = tmp_path / "docker-compose.yml"
        p.write_text("{invalid yaml: [missing bracket\n")
        spec = DockerComposeParser().parse(p)
        assert any(w.severity == "error" for w in spec.warnings)

    def test_profile_warning(self, tmp_path):
        p = write_compose(tmp_path, """\
            services:
              app:
                image: myapp
              debug:
                image: debug-tool
                profiles: [debug]
        """)
        spec = DockerComposeParser().parse(p)
        assert any("Profiles" in str(w) for w in spec.warnings)

    def test_override_file_merged(self, tmp_path):
        (tmp_path / "docker-compose.yml").write_text(
            "services:\n  app:\n    image: myapp\n    ports:\n      - '80:80'\n"
        )
        (tmp_path / "docker-compose.override.yml").write_text(
            "services:\n  app:\n    environment:\n      DEBUG: 'true'\n"
        )
        spec = DockerComposeParser().parse(tmp_path / "docker-compose.yml")
        app = spec.services[0]
        assert app.env.get("DEBUG") == "true"
        assert app.ports[0].host == 80
        assert any("override" in str(w).lower() for w in spec.warnings)


# ── ParserRegistry ────────────────────────────────────────────────────────────

class TestParserRegistry:
    def test_register_and_dispatch(self, tmp_path):
        p = write_compose(tmp_path, """\
            services:
              web:
                image: nginx
        """)
        reg = ParserRegistry()
        reg.register(DockerComposeParser())
        spec = reg.parse(p)
        assert spec.source_format == "docker_compose"

    def test_no_parser_raises(self, tmp_path):
        p = tmp_path / "random.toml"
        p.write_text("[config]\nkey = 'value'\n")
        reg = ParserRegistry()
        reg.register(DockerComposeParser())
        with pytest.raises(ValueError, match="No parser registered"):
            reg.parse(p)

    def test_parse_dir_finds_compose(self, tmp_path):
        write_compose(tmp_path, """\
            services:
              web:
                image: nginx
        """)
        (tmp_path / "ignored.txt").write_text("nope")
        reg = ParserRegistry()
        reg.register(DockerComposeParser())
        results = reg.parse_dir(tmp_path)
        assert len(results) == 1
        assert results[0].source_format == "docker_compose"

    def test_parse_dir_skip_errors(self, tmp_path):
        p = tmp_path / "docker-compose.yml"
        p.write_text("{broken yaml: [")
        reg = ParserRegistry()
        reg.register(DockerComposeParser())
        results = reg.parse_dir(tmp_path, skip_errors=True)
        assert len(results) == 1
        assert results[0].confidence == 0.0

    def test_registered_list(self):
        reg = ParserRegistry()
        reg.register(DockerComposeParser())
        assert "docker_compose" in reg.registered


# ── Global registry + convenience helpers ─────────────────────────────────────

class TestGlobalRegistry:
    def test_parser_registry_has_compose(self):
        assert "docker_compose" in parser_registry.registered

    def test_parse_file_helper(self, tmp_path):
        p = write_compose(tmp_path, """\
            services:
              api:
                image: python:3.11
                ports: ["8000:8000"]
        """)
        spec = parse_file(p)
        assert spec.services[0].image == "python:3.11"

    def test_parse_dir_helper(self, tmp_path):
        write_compose(tmp_path, """\
            services:
              db:
                image: postgres:15
        """)
        results = parse_dir(tmp_path)
        assert len(results) == 1
        assert results[0].services[0].image == "postgres:15"


# ── Summary / confidence ──────────────────────────────────────────────────────

class TestSummary:
    def test_summary_non_empty(self, tmp_path):
        p = write_compose(tmp_path, """\
            services:
              web:
                image: nginx
                ports: ["80:80"]
              db:
                image: postgres
        """)
        spec = parse_file(p)
        s = spec.summary()
        assert "2 service" in s
        assert "docker_compose" in s
        assert "100%" in s

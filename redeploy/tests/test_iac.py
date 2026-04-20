"""Tests for redeploy.iac — ParsedSpec, ParserRegistry, DockerComposeParser."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from redeploy.iac import (
    ParsedSpec, ParserRegistry, parse_file, parse_dir, parser_registry,
)
from redeploy.iac.parsers.compose import DockerComposeParser


# ── helpers ───────────────────────────────────────────────────────────────────


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content))
    return p


# ── DockerComposeParser.can_parse ──────────────────────────────────────────────


class TestCanParse:
    def _p(self, name): return Path(name)

    def test_canonical_names(self):
        parser = DockerComposeParser()
        for name in ("docker-compose.yml", "docker-compose.yaml",
                     "compose.yml", "compose.yaml"):
            assert parser.can_parse(self._p(name)), name

    def test_override_files(self):
        parser = DockerComposeParser()
        assert parser.can_parse(self._p("docker-compose.prod.yml"))
        assert parser.can_parse(self._p("docker-compose.override.yaml"))

    def test_rejects_other_yaml(self):
        parser = DockerComposeParser()
        assert not parser.can_parse(self._p("k8s-deployment.yaml"))
        assert not parser.can_parse(self._p("fleet.yml"))
        assert not parser.can_parse(self._p("redeploy.yaml"))


# ── DockerComposeParser.parse ──────────────────────────────────────────────────


class TestDockerComposeParse:
    def _parse(self, tmp_path: Path, content: str) -> ParsedSpec:
        path = _write(tmp_path, "docker-compose.yml", content)
        return DockerComposeParser().parse(path)

    def test_empty_file(self, tmp_path):
        spec = self._parse(tmp_path, "")
        assert spec.services == []
        assert spec.confidence == 1.0

    def test_single_service_image(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              web:
                image: nginx:latest
        """)
        assert len(spec.services) == 1
        assert spec.services[0].name == "web"
        assert spec.services[0].image == "nginx:latest"
        assert "nginx:latest" in spec.images

    def test_service_with_build(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              app:
                build: .
        """)
        assert spec.services[0].build_context == "."

    def test_service_build_context_dict(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              app:
                build:
                  context: ./backend
                  dockerfile: Dockerfile.prod
        """)
        assert spec.services[0].build_context == "./backend"

    def test_ports_string_form(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              web:
                image: nginx
                ports:
                  - "8080:80"
                  - "443:443"
        """)
        ports = spec.services[0].ports
        assert len(ports) == 2
        assert ports[0].host == 8080
        assert ports[0].container == 80
        assert ports[1].host == 443

    def test_ports_no_host(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              web:
                image: nginx
                ports: ["80"]
        """)
        p = spec.services[0].ports[0]
        assert p.container == 80
        assert p.host is None

    def test_ports_with_protocol(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              udp_svc:
                image: test
                ports: ["5000:5000/udp"]
        """)
        assert spec.services[0].ports[0].protocol == "udp"

    def test_ports_long_form(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              web:
                image: nginx
                ports:
                  - target: 80
                    published: 8080
                    protocol: tcp
        """)
        p = spec.services[0].ports[0]
        assert p.container == 80
        assert p.host == 8080

    def test_volumes_named(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              db:
                image: postgres
                volumes:
                  - pgdata:/var/lib/postgresql/data
            volumes:
              pgdata:
        """)
        svc_vol = spec.services[0].volumes[0]
        assert svc_vol.target == "/var/lib/postgresql/data"
        assert svc_vol.source == "pgdata"
        assert svc_vol.source_type == "volume"

    def test_volumes_bind_mount(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              app:
                image: test
                volumes:
                  - /host/path:/container/path
        """)
        v = spec.services[0].volumes[0]
        assert v.source_type == "bind"
        assert v.source == "/host/path"
        assert v.target == "/container/path"

    def test_volumes_read_only(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              app:
                image: test
                volumes:
                  - /data:/data:ro
        """)
        assert spec.services[0].volumes[0].read_only is True

    def test_env_dict(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              app:
                image: test
                environment:
                  FOO: bar
                  PORT: "8080"
        """)
        env = spec.services[0].env
        assert env["FOO"] == "bar"
        assert env["PORT"] == "8080"

    def test_env_list(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              app:
                image: test
                environment:
                  - FOO=bar
                  - EMPTY
        """)
        env = spec.services[0].env
        assert env["FOO"] == "bar"
        assert "EMPTY" in env

    def test_depends_on_list(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              web:
                image: nginx
                depends_on: [db, redis]
              db:
                image: postgres
              redis:
                image: redis
        """)
        web = next(s for s in spec.services if s.name == "web")
        assert "db" in web.depends_on
        assert "redis" in web.depends_on

    def test_depends_on_dict(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              web:
                image: nginx
                depends_on:
                  db:
                    condition: service_healthy
              db:
                image: postgres
        """)
        web = next(s for s in spec.services if s.name == "web")
        assert "db" in web.depends_on

    def test_networks(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              web:
                image: nginx
                networks: [frontend, backend]
            networks:
              frontend:
              backend:
        """)
        assert "frontend" in spec.networks
        assert "backend" in spec.networks
        web = spec.services[0]
        assert "frontend" in web.networks

    def test_secrets_referenced(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              app:
                image: test
                secrets: [db_password]
            secrets:
              db_password:
                file: ./secrets/db_password.txt
        """)
        assert "db_password" in spec.secrets_referenced

    def test_healthcheck_list(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              web:
                image: nginx
                healthcheck:
                  test: ["CMD", "curl", "-f", "http://localhost"]
        """)
        hc = spec.services[0].healthcheck
        assert hc is not None
        assert "curl" in hc

    def test_labels_dict(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              web:
                image: nginx
                labels:
                  traefik.enable: "true"
                  traefik.http.routers.web.rule: "Host(`example.com`)"
        """)
        labels = spec.services[0].labels
        assert labels.get("traefik.enable") == "true"

    def test_labels_list(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              web:
                image: nginx
                labels:
                  - traefik.enable=true
        """)
        labels = spec.services[0].labels
        assert "traefik.enable" in labels

    def test_command_string(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              app:
                image: python
                command: python manage.py runserver
        """)
        assert spec.services[0].command == "python manage.py runserver"

    def test_command_list(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              app:
                image: python
                command: ["python", "-m", "uvicorn", "main:app"]
        """)
        cmd = spec.services[0].command
        assert "uvicorn" in cmd

    def test_restart_policy(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              app:
                image: nginx
                restart: unless-stopped
        """)
        assert spec.services[0].restart == "unless-stopped"

    def test_replicas_from_deploy(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              app:
                image: nginx
                deploy:
                  replicas: 3
        """)
        assert spec.services[0].replicas == 3

    def test_version_hint(self, tmp_path):
        spec = self._parse(tmp_path, """
            version: "3.9"
            services:
              app:
                image: nginx
        """)
        assert any("3.9" in h for h in spec.runtime_hints)

    def test_multiple_services(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              web:
                image: nginx
              db:
                image: postgres
              cache:
                image: redis
        """)
        assert len(spec.services) == 3
        names = [s.name for s in spec.services]
        assert "web" in names and "db" in names and "cache" in names

    def test_all_images_deduped(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              web:
                image: nginx:latest
              web2:
                image: nginx:latest
        """)
        assert spec.all_images().count("nginx:latest") == 1

    def test_summary(self, tmp_path):
        spec = self._parse(tmp_path, """
            services:
              web:
                image: nginx
                ports: ["80:80"]
        """)
        s = spec.summary()
        assert "docker-compose" in s
        assert "1 service" in s

    def test_corrupt_top_level(self, tmp_path):
        path = _write(tmp_path, "docker-compose.yml", "- item1\n- item2\n")
        spec = DockerComposeParser().parse(path)
        assert spec.confidence == 0.0


# ── ParserRegistry ────────────────────────────────────────────────────────────


class TestParserRegistry:
    def test_registered(self):
        assert "docker-compose" in parser_registry.registered

    def test_parser_for_compose(self, tmp_path):
        path = tmp_path / "docker-compose.yml"
        path.write_text("services: {}")
        p = parser_registry.parser_for(path)
        assert p is not None
        assert p.name == "docker-compose"

    def test_parser_for_unknown(self, tmp_path):
        path = tmp_path / "random.txt"
        path.write_text("hello")
        assert parser_registry.parser_for(path) is None

    def test_parse_raises_for_unknown(self, tmp_path):
        path = tmp_path / "unknown.txt"
        path.write_text("x")
        with pytest.raises(ValueError, match="No parser registered"):
            parser_registry.parse(path)


# ── parse_file / parse_dir ────────────────────────────────────────────────────


def test_parse_file(tmp_path):
    path = _write(tmp_path, "docker-compose.yml", """
        services:
          app:
            image: nginx
    """)
    spec = parse_file(path)
    assert spec.source_format == "docker-compose"
    assert len(spec.services) == 1


def test_parse_dir(tmp_path):
    _write(tmp_path, "docker-compose.yml", """
        services:
          web:
            image: nginx
    """)
    _write(tmp_path, "docker-compose.prod.yml", """
        services:
          web:
            image: nginx:stable
    """)
    (tmp_path / "ignored.txt").write_text("not yaml")
    specs = parse_dir(tmp_path, recursive=False)
    assert len(specs) == 2
    formats = {s.source_format for s in specs}
    assert formats == {"docker-compose"}


def test_parse_dir_skip_errors(tmp_path):
    _write(tmp_path, "docker-compose.yml", "not: valid: yaml: [")
    specs = parse_dir(tmp_path, skip_errors=True)
    assert len(specs) == 1
    assert specs[0].confidence == 0.0 or len(specs[0].warnings) > 0


# ── ConversionWarning ─────────────────────────────────────────────────────────


def test_warning_str_with_location():
    from redeploy.iac.base import ConversionWarning
    w = ConversionWarning("warn", "Something odd", "compose.yml", 42)
    assert "compose.yml:42" in str(w)
    assert "Something odd" in str(w)


def test_warning_str_no_location():
    from redeploy.iac.base import ConversionWarning
    w = ConversionWarning("error", "Bad input")
    assert "Bad input" in str(w)
    assert "ERROR" in str(w)

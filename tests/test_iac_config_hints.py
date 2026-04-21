from __future__ import annotations

from pathlib import Path

from redeploy.iac import parse_file
from redeploy.iac.config_hints import ConfigHintsParser


def test_can_parse_dockerfile(tmp_path: Path):
    p = tmp_path / "Dockerfile"
    p.write_text("FROM python:3.11\n")
    parser = ConfigHintsParser()
    assert parser.can_parse(p)


def test_parse_dockerfile_images(tmp_path: Path):
    p = tmp_path / "Dockerfile"
    p.write_text("FROM python:3.11\nFROM nginx:alpine\n")
    spec = parse_file(p)
    assert spec.source_format == "dockerfile"
    assert "python:3.11" in spec.images
    assert "nginx:alpine" in spec.images


def test_parse_nginx_conf_ports(tmp_path: Path):
    p = tmp_path / "nginx.conf"
    p.write_text("server {\n  listen 8100;\n  proxy_pass http://127.0.0.1:8000;\n}\n")
    spec = parse_file(p)
    assert spec.source_format == "nginx"
    assert any(port.container == 8100 for port in spec.ports)


def test_parse_k8s_yaml(tmp_path: Path):
    p = tmp_path / "deploy.yaml"
    p.write_text(
        """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  template:
    spec:
      containers:
        - name: api
          image: ghcr.io/example/api:1.2.3
          ports:
            - containerPort: 8000
""".strip()
    )
    spec = parse_file(p)
    assert spec.source_format == "kubernetes"
    assert "ghcr.io/example/api:1.2.3" in spec.images
    assert any(s.name == "api" for s in spec.services)


def test_parse_terraform(tmp_path: Path):
    p = tmp_path / "main.tf"
    p.write_text('resource "aws_instance" "web" {}\n')
    spec = parse_file(p)
    assert spec.source_format == "terraform"
    assert any(h.startswith("terraform") for h in spec.runtime_hints)


def test_parse_toml(tmp_path: Path):
    p = tmp_path / "pyproject.toml"
    p.write_text(
        """
[project]
name = "demo"

[project.scripts]
deploy = "demo.cli:main"
""".strip()
    )
    spec = parse_file(p)
    assert spec.source_format == "toml"
    assert "script:deploy" in spec.deploy_commands


def test_parse_vite_config(tmp_path: Path):
    p = tmp_path / "vite.config.ts"
    p.write_text("export default { build: {}, server: { port: 5173 } }\n")
    spec = parse_file(p)
    assert spec.source_format == "vite"
    assert any("vite build" in cmd for cmd in spec.deploy_commands)


def test_parse_github_actions(tmp_path: Path):
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    p = wf / "deploy.yml"
    p.write_text(
        """
on:
  push:
    branches: [ main ]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - run: docker build -t app .
      - run: ssh pi@192.168.1.10 "echo ok"
""".strip()
    )
    spec = parse_file(p)
    assert spec.source_format == "github_actions"
    assert "push" in spec.triggers
    assert any("docker build" in cmd for cmd in spec.deploy_commands)
    assert any(host.startswith("pi@") for host in spec.target_hosts)


def test_parse_gitlab_ci(tmp_path: Path):
    p = tmp_path / ".gitlab-ci.yml"
    p.write_text(
        """
stages: [build, deploy]

build_job:
  stage: build
  image: docker:24
  script:
    - docker build -t app .
""".strip()
    )
    spec = parse_file(p)
    assert spec.source_format == "gitlab_ci"
    assert "docker:24" in spec.images
    assert any("docker build" in cmd for cmd in spec.deploy_commands)

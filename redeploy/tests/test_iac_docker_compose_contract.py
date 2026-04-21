from __future__ import annotations

import textwrap
from dataclasses import asdict

from redeploy.iac.docker_compose import DockerComposeParser


def test_docker_compose_parser_service_contract(tmp_path):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text(
        textwrap.dedent(
            """
            services:
              web:
                image: nginx:1.27
                command: ["nginx", "-g", "daemon off;"]
                restart: unless-stopped
                deploy:
                  replicas: 2
                ports:
                  - "127.0.0.1:8080:80/tcp"
                  - target: 443
                    published: 8443
                    protocol: tcp
                volumes:
                  - ./html:/usr/share/nginx/html:ro
                  - type: volume
                    source: cache
                    target: /var/cache/nginx
                networks: [frontend, backend]
                environment:
                  APP_ENV: prod
                env_file:
                  - .env.web
                depends_on:
                  db:
                    condition: service_healthy
                labels:
                  - traefik.enable=true
                healthcheck:
                  test: ["CMD", "curl", "-f", "http://localhost/health"]
                secrets:
                  - source: tls_cert

              db:
                image: postgres:16
                build:
                  context: ./db
                command: postgres -c max_connections=300
                ports: ["5432"]
                volumes:
                  - pgdata:/var/lib/postgresql/data
                networks:
                  backend: {}
                environment:
                  - POSTGRES_DB=app
                env_file: .env.db
                depends_on: [redis]
                labels:
                  com.example.role: db
                healthcheck: pg_isready -U postgres
                secrets:
                  - db_password

            networks:
              frontend: {}
              backend: {}

            volumes:
              pgdata: {}
              cache: {}

            secrets:
              tls_cert:
                external: true
              db_password:
                file: ./secrets/db_password.txt
            """
        )
    )

    spec = DockerComposeParser().parse(compose)

    actual = {
        "services": [asdict(svc) for svc in spec.services],
        "images": spec.images,
        "networks": spec.networks,
        "secrets": spec.secrets_referenced,
    }

    expected = {
        "services": [
            {
                "name": "web",
                "image": "nginx:1.27",
                "ports": [
                    {
                        "container": 80,
                        "host": 8080,
                        "protocol": "tcp",
                        "host_ip": "127.0.0.1",
                    },
                    {
                        "container": 443,
                        "host": 8443,
                        "protocol": "tcp",
                        "host_ip": "0.0.0.0",
                    },
                ],
                "volumes": [
                    {
                        "target": "/usr/share/nginx/html",
                        "source": "./html",
                        "source_type": "bind",
                        "read_only": True,
                    },
                    {
                        "target": "/var/cache/nginx",
                        "source": "cache",
                        "source_type": "volume",
                        "read_only": False,
                    },
                ],
                "env": {"APP_ENV": "prod"},
                "env_files": [".env.web"],
                "networks": ["frontend", "backend"],
                "depends_on": ["db"],
                "healthcheck": "CMD curl -f http://localhost/health",
                "restart": "unless-stopped",
                "command": "['nginx', '-g', 'daemon off;']",
                "build_context": None,
                "replicas": 2,
                "labels": {"traefik.enable": "true"},
            },
            {
                "name": "db",
                "image": "postgres:16",
                "ports": [
                    {
                        "container": 5432,
                        "host": None,
                        "protocol": "tcp",
                        "host_ip": "0.0.0.0",
                    }
                ],
                "volumes": [
                    {
                        "target": "/var/lib/postgresql/data",
                        "source": "pgdata",
                        "source_type": "volume",
                        "read_only": False,
                    }
                ],
                "env": {"POSTGRES_DB": "app"},
                "env_files": [".env.db"],
                "networks": ["backend"],
                "depends_on": ["redis"],
                "healthcheck": None,
                "restart": None,
                "command": "postgres -c max_connections=300",
                "build_context": "./db",
                "replicas": 1,
                "labels": {"com.example.role": "db"},
            },
        ],
        "images": ["nginx:1.27", "postgres:16"],
        "networks": ["frontend", "backend"],
        "secrets": ["tls_cert"],
    }

    assert actual == expected

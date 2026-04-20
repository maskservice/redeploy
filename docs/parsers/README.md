# redeploy IaC Parsers

`redeploy.iac` — pluggable parser framework that converts external IaC/CI-CD
files into a common `ParsedSpec` intermediate representation, which the CLI
can then scaffold into a `migration.yaml`.

---

## Quick start

```bash
# Parse a docker-compose file and write migration.yaml scaffold
redeploy import docker-compose.yml

# Dry-run: parse and display without writing
redeploy import docker-compose.yml --dry-run

# Embed target host and auto-detect strategy
redeploy import docker-compose.yml --target-host root@vps.example.com

# Parse an entire directory
redeploy import . --dry-run

# JSON output
redeploy import docker-compose.yml --format json
```

Python API:

```python
from redeploy.iac import parse_file, parse_dir, parser_registry

spec = parse_file("docker-compose.yml")
print(spec.services)          # list[ServiceInfo]
print(spec.confidence)        # 0.0–1.0
print(spec.warnings)          # list[ConversionWarning]
print(parser_registry.registered)  # ['docker_compose', ...]
```

---

## Architecture

```
redeploy import <file>
        │
        ▼
  ParserRegistry.parse(path)
        │  auto-detects format via can_parse()
        ▼
  Parser.parse(path) → ParsedSpec
        │  format-specific (docker-compose, GHA, k8s, …)
        ▼
  _spec_to_migration_yaml(spec) → dict
        │  lossy conversion to migration.yaml scaffold
        ▼
  migration.yaml  (user edits further)
```

### Core types (`redeploy.iac.base`)

| Type | Description |
|---|---|
| `Parser` | Protocol every parser must implement |
| `ParsedSpec` | Common IR: services, ports, volumes, networks, warnings |
| `ServiceInfo` | One logical service/container |
| `PortInfo` | Published port mapping |
| `VolumeInfo` | Volume or bind-mount |
| `ConversionWarning` | Non-fatal parse issue with severity (`info`/`warn`/`error`) |
| `ParserRegistry` | Dispatches file → first matching parser |

### `ParsedSpec` fields

| Field | Type | Description |
|---|---|---|
| `source_file` | `Path` | Absolute path of the parsed file |
| `source_format` | `str` | Parser name (e.g. `docker_compose`) |
| `confidence` | `float` | 0.0–1.0; lowered on partial/ambiguous input |
| `services` | `list[ServiceInfo]` | All detected services |
| `ports` | `list[PortInfo]` | Aggregate of all service ports |
| `volumes` | `list[VolumeInfo]` | Top-level named volumes |
| `networks` | `list[str]` | Top-level named networks |
| `images` | `list[str]` | Distinct images referenced |
| `runtime_hints` | `list[str]` | E.g. `["docker"]`, `["podman"]` |
| `secrets_referenced` | `list[str]` | External secret names (no values) |
| `warnings` | `list[ConversionWarning]` | Parse issues |

---

## Built-in parsers

### Tier 1 — `docker_compose` ✓ implemented

**File:** `redeploy/iac/docker_compose.py`

Handles `docker-compose.yml`, `compose.yaml`, and override files.

Supported features:
- All common service keys: `image`, `build`, `ports`, `volumes`, `environment`,
  `env_file`, `networks`, `depends_on`, `healthcheck`, `restart`, `command`
- `deploy.replicas` (Swarm / Compose v3)
- Variable substitution: `${VAR}`, `${VAR:-default}` (reads `.env` in same dir)
- Multi-file merge: auto-loads `docker-compose.override.yml` if present
- Profiles: detected and recorded as `info` warning
- Long-form port/volume syntax

Not supported (recorded as warnings):
- Swarm-only keys: `deploy.placement`, `update_config`, `rollback_config`
- Runtime secret resolution (names collected, values ignored)

#### `can_parse()` detection order

1. Exact filename match (`docker-compose.yml`, `compose.yaml`, …)
2. Glob pattern match (`docker-compose.*.yml`)
3. Heuristic: `.yml`/`.yaml` file with `services:` in first 20 lines

---

### Tier 1 — GitHub Actions (planned)

Parses `.github/workflows/*.yml` → jobs as services, `on:` triggers as metadata.

### Tier 1 — Kubernetes (planned)

Parses `Deployment`, `Service`, `ConfigMap` manifests → services + ports.

### Tier 2 — GitLab CI (planned)

Parses `.gitlab-ci.yml` → stages/jobs.

### Tier 2 — Ansible (planned)

Parses playbooks → task groups as services.

### Tier 2 — Dockerfile (planned)

Parses single `Dockerfile` → one service with `EXPOSE` ports and build context.

### Tier 2 — systemd units (planned)

Parses `.service` files → one service per unit.

---

## Writing a custom parser

Implement the `Parser` protocol and register:

```python
from pathlib import Path
from redeploy.iac import Parser, ParsedSpec, ServiceInfo, parser_registry

class MyFormatParser:
    name = "my_format"
    format_label = "My Format"
    extensions = [".myext"]
    path_patterns = ["myapp.conf"]

    def can_parse(self, path: Path) -> bool:
        return path.suffix == ".myext"

    def parse(self, path: Path) -> ParsedSpec:
        spec = ParsedSpec(source_file=path, source_format=self.name)
        # ... populate spec.services, spec.networks, etc.
        spec.confidence = 0.9
        return spec

parser_registry.register(MyFormatParser())
```

After registration `redeploy import myapp.conf` will use your parser automatically.

---

## CLI reference

### `redeploy import SOURCE [OPTIONS]`

| Option | Default | Description |
|---|---|---|
| `-o / --output PATH` | auto | Output file path |
| `--target-host TEXT` | — | SSH host to embed in migration.yaml |
| `--target-strategy TEXT` | auto | Override strategy (e.g. `docker_full`) |
| `--dry-run` | off | Parse + display, no file written |
| `--format [yaml\|json\|summary]` | `yaml` | Output format |
| `--parser TEXT` | auto | Force specific parser by name |

### `redeploy diff [OPTIONS]`  *(Phase 3 — planned)*

Compare parsed IaC spec vs live SSH probe for drift detection.

---

## Phase roadmap

| Phase | Features |
|---|---|
| **0** ✓ | `Parser` protocol, `ParsedSpec`, `ParserRegistry`, `DockerComposeParser`, CLI `import` |
| **1** | GitHub Actions parser, Kubernetes parser |
| **2** | GitLab CI, Ansible, Dockerfile, systemd parsers |
| **3** | `redeploy diff` — drift detection (IaC vs live) |
| **4** | Bidirectional: `redeploy export` live→IaC |

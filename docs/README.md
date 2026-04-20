# redeploy — documentation index

![version](https://img.shields.io/badge/version-0.2.0-blue) ![python](https://img.shields.io/badge/python-%3E%3D3.11-blue) ![tests](https://img.shields.io/badge/tests-797-green)

Infrastructure migration toolkit: **detect → plan → apply**  
**Repository:** [https://github.com/maskservice/redeploy](https://github.com/maskservice/redeploy)

## Documentation

| Module | Description |
|---|---|
| [parsers/README.md](parsers/README.md) | IaC parser framework — `redeploy import`, `DockerComposeParser` |
| [patterns.md](patterns.md) | Deploy patterns — BlueGreen, Canary, RollbackOnFailure |
| [observe.md](observe.md) | Audit log, deploy reports — `DeployAuditLog`, `DeployReport` |
| [fleet.md](fleet.md) | Fleet management — `Fleet`, `FleetConfig`, `DeviceRegistry` |

---

## Installation

```bash
pip install redeploy
# or from source:
pip install -e .
```

---

## Quick start

```bash
# Full pipeline: detect → plan → apply
redeploy migrate --host root@10.0.0.1 --app myapp --strategy docker_full

# Or step by step:
redeploy detect --host root@10.0.0.1
redeploy plan   --strategy docker_full
redeploy apply  --dry-run

# From migration.yaml spec:
redeploy run migration.yaml --dry-run
redeploy run migration.yaml --env prod
```

---

## CLI commands (v0.2.0)

| Command | Description |
|---|---|
| `detect` | Probe host → `infra.yaml` |
| `plan` | `infra.yaml` + target → `migration-plan.yaml` |
| `apply` | Execute `migration-plan.yaml` |
| `migrate` | Full pipeline: detect → plan → apply |
| `run` | Single `migration.yaml` spec |
| `devices` | List device registry |
| `scan` | Discover devices on local network |
| `target` | Deploy spec to a registered device |
| `fleet` | Fleet view (fleet.yaml + registry) |
| `audit` | Deploy history from `audit.jsonl` |
| `patterns` | List/inspect deploy patterns |
| `import` | Parse IaC file → migration.yaml scaffold |
| `diff` | *(planned)* IaC vs live drift detection |

---

## Python public API (v0.2.0)

```python
import redeploy

# Core pipeline
redeploy.Planner(state, target).run()      # → MigrationPlan
redeploy.Executor(plan, dry_run=True)      # auto-writes audit log

# Deploy patterns
redeploy.BlueGreenPattern(app, remote_dir, verify_url).expand()
redeploy.CanaryPattern(app, remote_dir, stages=[10,50,100]).expand()
redeploy.RollbackOnFailurePattern(app, remote_dir).expand()
redeploy.get_pattern("blue_green")
redeploy.list_patterns()

# Observability
redeploy.DeployAuditLog().tail(10)
redeploy.DeployReport(entry).text()
redeploy.DeployReport(entry).summary_line()

# Fleet
redeploy.Fleet.from_file("fleet.yaml").prod().reachable()
redeploy.Fleet.from_registry().by_tag("kiosk")

# IaC parsers
from redeploy.iac import parse_file, parse_dir, parser_registry
parse_file("docker-compose.yml")           # → ParsedSpec
```

All public names are listed in `redeploy.__all__` and guaranteed stable from 0.2.0.

---

## Deploy strategies

| Strategy | Description |
|---|---|
| `docker_full` | Docker Compose (pull + up) |
| `podman_quadlet` | Podman Quadlet (systemd units) |
| `k3s` | Kubernetes via k3s |
| `native_kiosk` | Raspberry Pi kiosk (openbox + chromium) |
| `docker_kiosk` | Docker-based kiosk |
| `kiosk_appliance` | Kiosk appliance (doql `build/` sync + systemd) |
| `systemd` | Generic systemd service |

Strategy aliases (for `doql` compatibility): `docker`, `kiosk`, `appliance`.

---

## Deploy patterns

| Pattern | Steps | Description |
|---|---|---|
| `blue_green` | 7 | Zero-downtime via Traefik label swap |
| `canary` | N×(health+wait) +2 | Gradual rollout with per-stage checks |
| `rollback_on_failure` | 4 | Snapshot + auto-rollback on failure |

See [patterns.md](patterns.md) for full documentation.

---

## Module structure

```
redeploy/
├── __init__.py          # public API (__all__, 38 symbols)
├── models.py            # Pydantic models: InfraState, TargetConfig, MigrationPlan, …
├── fleet.py             # Fleet, FleetConfig, FleetDevice, Stage, DeviceExpectation
├── patterns.py          # BlueGreenPattern, CanaryPattern, RollbackOnFailurePattern
├── observe.py           # DeployAuditLog, AuditEntry, DeployReport
├── steps.py             # StepLibrary (named MigrationSteps)
├── cli.py               # Click CLI (14 commands)
├── ssh.py               # SshClient, SshResult
├── verify.py            # VerifyContext
├── detect/              # Detector, DetectionWorkflow, templates
├── plan/                # Planner
├── apply/               # Executor, ProgressEmitter
└── iac/                 # IaC parsers (DockerComposeParser, ParserRegistry)
```

---

## Requirements

- Python ≥ 3.11
- `pydantic ≥ 2.0`, `pyyaml ≥ 6.0`, `click ≥ 8.0`
- `loguru ≥ 0.7`, `paramiko ≥ 3.0`, `httpx ≥ 0.25`, `rich ≥ 13.0`

---

## Development

```bash
pip install -e ".[dev]"
pytest redeploy/tests/        # 797 tests
```

---

## Changelog

See [CHANGELOG.md](../CHANGELOG.md) for full release notes.
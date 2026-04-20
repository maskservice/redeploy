# redeploy — Examples

This directory contains deployment examples in multiple formats:

- **`yaml/`** — Traditional YAML format (migration.yaml)
- **`md/`** — Markdown format with markpact blocks (migration.md) — **NEW**

## Format Comparison

| Format | Status | Best For |
|--------|--------|----------|
| YAML | Stable | Simple, declarative deployments |
| Markdown (markpact) | **NEW** | Complex, multi-language deployments |

## Quick Start

### YAML Format (Traditional)
```bash
redeploy run examples/yaml/01-vps-version-bump/migration.yaml --dry-run
```

### Markdown Format (markpact) — NEW
```bash
# Via markpact runtime
python -m markpact.runtime.cli examples/md/01-rpi5-deploy/migration.md --dry-run

# Via redeploy (when integrated)
redeploy run examples/md/01-rpi5-deploy/migration.md --dry-run
```

```
```
examples/
├── yaml/                        # YAML format examples
│   ├── 01-vps-version-bump/
│   ├── 02-k3s-to-docker/
│   ├── 03-docker-to-podman-quadlet/
│   ├── 04-rpi-kiosk/
│   └── ... (13+ examples)
└── md/                          # Markdown format examples (markpact)
    ├── 01-rpi5-deploy/
    ├── 02-multi-language/
    └── README.md
```
```

## Quick reference

| # | Scenario | Strategies | Key feature |
|---|----------|-----------|-------------|
| 01 | VPS version bump | docker_full → docker_full | Named library step `flush_k3s_iptables` |
| 02 | k3s → Docker | k3s → docker_full | Auto conflict-fix: delete ingresses, stop k3s |
| 03 | Docker → Quadlet | docker_full → podman_quadlet | rootless systemd, daemon-reload |
| 04 | RPi kiosk | native_kiosk → native_kiosk | systemd + Chromium restart |
| 05 | IoT OTA | docker_full → docker_full | DB backup, image prune, VERSION file |
| 06 | Local dev | docker_full (local) | `host: local` — no SSH |
| 07 | Staging → Prod | docker_full → docker_full | smoke test, `insert_before`, webhooks |
| 08 | Rollback | docker_full → docker_full | source/target swapped, audit log |
| 09 | Fleet YAML | all strategies | `Stage`, `DeviceExpectation` |
| 10 | Multi-env | docker_full | `dev.yaml` / `staging.yaml` / `prod.yaml` |
| 11 | Traefik TLS | docker_full | cert upload, force-recreate Traefik |
| 12 | CI Pipeline | docker_full | GitHub Actions + GitLab CI workflows |
| 13 | Monorepo | docker_full | multiple apps, rsync + promote compose |

## Run any example

```bash
# Dry-run (no changes)
redeploy run examples/01-vps-version-bump/migration.yaml --dry-run

# Live probe + plan + apply
redeploy run examples/02-k3s-to-docker/migration.yaml --detect

# Save plan to file without applying
redeploy run examples/07-staging-to-prod/migration.yaml --detect --plan-out /tmp/plan.yaml
```

## Named library steps

Several examples use **named library steps** — just `id:`, no `action:` needed:

```yaml
extra_steps:
  - id: flush_k3s_iptables   # StepLibrary fills in action + command
  - id: docker_prune
  - id: stop_nginx
```

Full list: `python -c "from redeploy.steps import StepLibrary; print(StepLibrary.list())"`

---

## markpact Format — NEW

**markpact** is a universal deployment specification format based on markdown.
It allows embedding multiple languages (YAML, TOML, JSON, Python, Bash) in a single file.

### Benefits over YAML

| Feature | YAML | markpact |
|---------|------|----------|
| Shell commands | Inline strings | Dedicated code blocks |
| Multi-language | ❌ N/A | ✅ Python, Bash, etc. |
| Documentation | Separate file | Embedded in markdown |
| Extensibility | Limited | Plugin system |
| IDE support | Schema validation | Full language support |

### Example markpact file

```markdown
# My Deployment

```markpact:config yaml
name: "my-deployment"
version: "1.0.0"
```

```markpact:steps yaml
extra_steps:
  - id: deploy
    action: docker
    description: "Deploy with Docker"
    host: user@example.com
```

```markpact:python
# Custom verification logic
print("Deployment complete!")
```
```

### Running markpact files

```bash
# Via markpact runtime (standalone)
python -m markpact.runtime.cli examples/md/01-rpi5-deploy/migration.md

# With dry-run
python -m markpact.runtime.cli examples/md/01-rpi5-deploy/migration.md --dry-run

# Via redeploy (when integrated)
redeploy run examples/md/01-rpi5-deploy/migration.md --dry-run
```

### Plugin System

markpact supports custom plugins from filesystem:

```yaml
plugins:
  - path: ./custom_plugins
  - path: ~/.markpact/plugins
  - module: my_package.plugins
```

See [examples/md/README.md](md/README.md) for complete documentation.

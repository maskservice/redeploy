# redeploy — Examples

Each subdirectory is a self-contained scenario with `migration.yaml` + `redeploy.yaml` + `README.md`.

```
examples/
├── 01-vps-version-bump/          # Bump Docker version on VPS (same strategy)
│   ├── migration.yaml
│   ├── redeploy.yaml
│   └── README.md
├── 02-k3s-to-docker/             # Migrate from k3s + ingress-nginx → Docker + Traefik
│   ├── migration.yaml
│   ├── redeploy.yaml
│   └── README.md
├── 03-docker-to-podman-quadlet/  # Docker Compose → Podman Quadlet (rootless systemd)
│   ├── migration.yaml
│   ├── redeploy.yaml
│   └── README.md
├── 04-rpi-kiosk/                 # Raspberry Pi native kiosk (systemd + Chromium)
│   ├── migration.yaml
│   ├── redeploy.yaml
│   └── README.md
├── 05-iot-fleet-ota/             # IoT edge node OTA via Docker
│   ├── migration.yaml
│   ├── redeploy.yaml
│   └── README.md
├── 06-local-dev/                 # Local Docker Compose dev iteration (no SSH)
│   ├── migration.yaml
│   ├── redeploy.yaml
│   └── README.md
├── 07-staging-to-prod/           # Promote staging image to prod with webhooks
│   ├── migration.yaml
│   ├── redeploy.yaml
│   └── README.md
├── 08-rollback/                  # Emergency rollback to previous version
│   ├── migration.yaml
│   ├── redeploy.yaml
│   └── README.md
├── 09-fleet-yaml/                # fleet.yaml with stages/tags/expectations
│   ├── fleet.yaml
│   ├── redeploy.yaml
│   └── README.md
├── 10-multienv/                  # dev/staging/prod specs in one directory
│   ├── dev.yaml
│   ├── staging.yaml
│   ├── prod.yaml
│   ├── redeploy.yaml
│   └── README.md
├── 11-traefik-tls/               # Add TLS termination to Traefik via cert files
│   ├── migration.yaml
│   ├── redeploy.yaml
│   ├── traefik/dynamic/tls.yml
│   └── README.md
├── 12-ci-pipeline/               # GitHub Actions / GitLab CI automated deploy
│   ├── migration.yaml
│   ├── redeploy.yaml
│   ├── deploy.github.yml
│   ├── deploy.gitlab.yml
│   └── README.md
└── 13-multi-app-monorepo/        # Multiple apps from one monorepo to single VPS
    ├── migration.yaml
    ├── redeploy.yaml
    ├── fleet.yaml
    └── README.md
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

# 01 — VPS Version Bump

Rebuild and redeploy a Docker Compose stack with a new app version. No strategy change.

## When to use

- Routine release: bump `VERSION`, rebuild images, roll containers
- Same infra, new code

## Prerequisites

- VPS reachable via SSH (`root@<ip>`)
- Docker Compose stack already running
- `envs/vps.env` with updated `SERVICE_VERSION`

## Run

```bash
# Dry-run — see plan without applying
redeploy run examples/01-vps-version-bump/migration.yaml --dry-run

# Live probe + plan + apply
redeploy run examples/01-vps-version-bump/migration.yaml --detect
```

## What happens

| Step | Action |
|------|--------|
| `flush_k3s_iptables` | Flush stale k3s CNI chains (if k3s was ever installed) |
| `sync_env` | Copy updated `.env` to remote |
| `docker_build_pull` | `docker compose build` on remote |
| `docker_compose_up` | `docker compose up -d --build` |
| `wait_startup` | Wait 30 s |
| `http_health_check` | `curl .../api/v1/health` → expect `healthy` |
| `version_check` | `curl .../api/v1/health` → expect `1.0.20` |

## Notes

- `flush_k3s_iptables` is a **named library step** — no `action:` field needed in YAML
- Cloudflare "Full" SSL mode required (origin cert in `traefik/certs/`)

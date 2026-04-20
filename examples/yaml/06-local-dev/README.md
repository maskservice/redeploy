# 06 — Local Dev

Local Docker Compose rebuild for development iteration.

## When to use

- Developing locally with `docker compose`
- Want redeploy's plan/verify flow without SSH

## How `host: local` works

When `host` is `local` (or empty), redeploy skips SSH and runs `docker compose` locally.
No remote connection needed.

## Run

```bash
# From project root
redeploy run examples/06-local-dev/migration.yaml
```

## What happens

| Step | Action |
|------|--------|
| `docker_build_pull` | `docker compose build` (local) |
| `docker_compose_up` | `docker compose up -d` |
| `wait_startup` | 30 s |
| `http_health_check` | `curl localhost:8000/api/v1/health` |
| `version_check` | Verify version |

## Notes

- No `sync_env` step — `.env` is already local
- Pair with `redeploy.yaml` in project root to skip passing migration path each time

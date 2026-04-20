# 08 — Emergency Rollback

Revert to a previous known-good version after a failed deploy.

## When to use

- Bad version deployed, health check failing
- Need to restore previous image quickly

## Prerequisites

- Previous image (`1.0.19`) still in remote Docker cache or registry
- `envs/vps.env` updated to `SERVICE_VERSION=1.0.19`

## Run

```bash
# Verify the plan
redeploy run examples/08-rollback/migration.yaml --detect --dry-run

# Apply rollback
redeploy run examples/08-rollback/migration.yaml --detect
```

## What happens

Rollback is structurally identical to a version bump — `source` and `target` are swapped:

| Step | Action |
|------|--------|
| `tag_rollback_event` | Write audit log entry |
| `flush_k3s_iptables` | Flush stale iptables |
| `sync_env` | Upload `.env` with old version |
| `docker_build_pull` | Pull/build 1.0.19 image |
| `docker_compose_up` | Roll back containers |
| `wait_startup` | 30 s |
| `http_health_check` | Verify health restored |
| `version_check` | Confirm 1.0.19 running |

## Notes

- If image was pruned: set `extra_steps` to `docker pull <image>:1.0.19` before compose up
- For DB migrations: rollback may require a DB schema downgrade step — add `ssh_cmd` manually
- Keep last 2 versions in registry to enable fast rollback without rebuild

# 07 — Staging → Prod Promotion

Promote a validated staging image to production with pre-flight smoke test and webhook notifications.

## When to use

- Two-environment pipeline: staging → prod
- Need to verify staging is healthy before touching prod
- Notify Slack/PagerDuty on deploy start/end

## Run

```bash
# Check plan against prod (--detect probes the TARGET host)
redeploy run examples/07-staging-to-prod/migration.yaml --detect --dry-run

# Apply
redeploy run examples/07-staging-to-prod/migration.yaml --detect
```

## What happens

| Step | Action | Note |
|------|--------|-------|
| `smoke_test_staging` | curl staging health | `insert_before: sync_env` — fail fast |
| `notify_deploy_start` | POST webhook | before sync |
| `flush_k3s_iptables` | flush stale rules | |
| `sync_env` | upload prod `.env` | |
| `docker_build_pull` | build on prod | |
| `docker_compose_up` | roll containers | |
| `wait_startup` | 30 s | |
| `http_health_check` | prod health check | |
| `version_check` | version verify | |
| `notify_deploy_done` | POST webhook | |

## Notes

- `insert_before: sync_env` — smoke test runs before any prod changes
- Replace `hooks.example.com` with real Slack/PagerDuty/custom webhook
- Both staging and prod must have the same `version` in `target`

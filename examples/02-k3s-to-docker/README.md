# 02 — k3s → Docker Compose

Migrate a VPS from k3s + ingress-nginx to Docker Compose + Traefik.

## When to use

- k3s proved too heavy for a single-node VPS
- Switching to simpler `docker compose` stack
- k3s iptables rules (CNI-HOSTPORT-DNAT) are stealing ports 80/443

## Run

```bash
redeploy run examples/02-k3s-to-docker/migration.yaml --detect --dry-run
redeploy run examples/02-k3s-to-docker/migration.yaml --detect
```

## What happens

| Step | Action |
|------|--------|
| `delete_k3s_ingresses` | `kubectl delete ingress --all-namespaces` |
| `stop_k3s` | `systemctl stop k3s` |
| `disable_k3s` | `systemctl disable k3s` |
| `flush_k3s_iptables` | Flush CNI-HOSTPORT-DNAT + KUBE-* chains |
| `sync_env` | Upload `.env` |
| `docker_build_pull` | Build images |
| `docker_compose_up` | Start stack |
| `wait_startup` | 30 s |
| `http_health_check` | Health check |
| `version_check` | Version verify |

## Notes

- Run `--detect` so redeploy probes live iptables and generates the right conflict-fix steps
- k3s binary stays on disk — only systemd unit is stopped/disabled

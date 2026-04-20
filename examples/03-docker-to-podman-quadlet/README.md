# 03 — Docker Compose → Podman Quadlet

Migrate from Docker Compose to rootless Podman Quadlet (systemd-managed containers).

## When to use

- Moving away from Docker daemon (security, licensing)
- Rootless containers managed by systemd
- Podman Quadlet available (RHEL 9+, Fedora 37+, Debian 12+)

## Prerequisites

- Podman ≥ 4.4 installed on remote
- `.container` / `.network` Quadlet unit files in `~/c2004/quadlets/`

## Run

```bash
redeploy run examples/03-docker-to-podman-quadlet/migration.yaml --dry-run
redeploy run examples/03-docker-to-podman-quadlet/migration.yaml
```

## What happens

| Step | Action |
|------|--------|
| `docker_compose_down` | Stop existing Docker stack |
| `sync_env` | Upload `.env` |
| `copy_quadlet_files` | Copy `.container`/`.network` to `/etc/containers/systemd/` |
| `podman_daemon_reload` | `systemctl daemon-reload` |
| `stop_c2004` | Stop old unit (if exists) |
| `start_c2004` | `systemctl start c2004.service` |
| `enable_linger` | `loginctl enable-linger` |
| `wait_startup` | 15 s |
| `http_health_check` | Health verify |
| `version_check` | Version verify |

## Notes

- Quadlet units live in `/etc/containers/systemd/` (system) or `~/.config/containers/systemd/` (rootless)
- Check logs: `journalctl -u c2004-backend -f`

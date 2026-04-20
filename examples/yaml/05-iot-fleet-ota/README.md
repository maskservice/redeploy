# 05 — IoT Fleet OTA Update

Over-the-air update for a Docker-based IoT edge node (RPi, Jetson, etc.).

## When to use

- Edge node running Docker Compose
- Need to update firmware/app version without physical access
- SD card space is limited — prune old images

## Run

```bash
# Check current state first
redeploy run examples/05-iot-fleet-ota/migration.yaml --detect --dry-run

# Apply
redeploy run examples/05-iot-fleet-ota/migration.yaml --detect
```

## What happens

| Step | Action |
|------|--------|
| `backup_local_db` | Backup SQLite DB with timestamp |
| `sync_env` | Upload `.env` with new version |
| `docker_build_pull` | Pull/build new image |
| `docker_compose_up` | Roll container |
| `docker_prune` | Prune old images (saves space) |
| `wait_startup` | 30 s |
| `http_health_check` | Verify health |
| `version_check` | Verify version |
| `write_version_file` | Write VERSION file |

## Fleet-wide OTA pattern

```bash
# Run against a list of nodes using fleet.yaml
for node in node-01 node-02 node-03; do
  sed "s/pi@192.168.1.42/pi@$node/" migration.yaml | redeploy run /dev/stdin
done
```

## Rollback

Re-run with `source` and `target` swapped, or restore the DB backup:
```bash
ssh pi@<node> "mv /var/lib/iot-agent/telemetry.db.bak.* /var/lib/iot-agent/telemetry.db"
```

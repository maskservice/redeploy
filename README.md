# redeploy

![PyPI](https://img.shields.io/badge/pypi-redeploy-blue) ![Version](https://img.shields.io/badge/version-0.1.2-blue) ![Python](https://img.shields.io/badge/python-3.10+-blue) ![License](https://img.shields.io/badge/license-Apache--2.0-green)

Infrastructure migration and device deploy toolkit — VPS, Raspberry Pi kiosk, Podman Quadlet, k3s.

```
redeploy detect   →  live probe host        (what is there now)
redeploy plan     →  migration-plan.yaml    (what to do)
redeploy apply    →  execute plan           (do it)
redeploy run      →  detect + plan + apply  (all at once from spec)
redeploy scan     →  find devices on LAN    (device registry)
redeploy target   →  deploy to named device (fleet)
```

## Install

```bash
pip install redeploy

# With doql integration (generates migration.yaml from app.doql):
pip install doql[deploy]
```

## Quick start — VPS production deploy

```bash
# 1. Create spec file (or use redeploy init)
cat > migration.yaml << 'EOF'
name: "myapp deploy"
source:
  strategy: docker_full
  host: root@YOUR_VPS_IP
  app: myapp
  version: "1.0.19"
target:
  strategy: docker_full
  host: root@YOUR_VPS_IP
  app: myapp
  version: "1.0.20"
  domain: myapp.example.com
  env_file: .env
  verify_url: https://myapp.example.com/api/health
EOF

# 2. Preview steps (no SSH)
redeploy run migration.yaml --plan-only

# 3. Dry run (SSH connect, no changes)
redeploy run migration.yaml --dry-run

# 4. Deploy
redeploy run migration.yaml --detect
```

## Quick start — Raspberry Pi kiosk

```bash
# Register the RPi in the device registry
redeploy device-add pi@192.168.1.42 \
  --tag kiosk --tag rpi4 \
  --strategy native_kiosk \
  --app kiosk-app \
  --name "Workshop kiosk #1"

# Preview deploy plan
redeploy target pi@192.168.1.42 migration.yaml --plan-only

# Dry run
redeploy target pi@192.168.1.42 migration.yaml --dry-run

# Deploy
redeploy target pi@192.168.1.42 migration.yaml --detect
```

## Device registry — find and manage devices

```bash
# Discover SSH-accessible devices on local network (passive: known_hosts + ARP + mDNS)
redeploy scan

# Active ICMP ping sweep (sends packets)
redeploy scan --ping --subnet 192.168.1.0/24

# Try specific SSH users
redeploy scan --user pi --user ubuntu --timeout 8

# List all known devices
redeploy devices

# Filter by tag or strategy
redeploy devices --tag kiosk
redeploy devices --strategy native_kiosk
redeploy devices --reachable          # seen in last 5 minutes

# JSON output for scripting
redeploy devices --json | jq '.[] | select(.tags | index("prod"))'

# Add device manually
redeploy device-add root@10.0.0.5 --tag prod --strategy docker_full --app myapp

# Remove device
redeploy device-rm root@10.0.0.5
```

Registry is stored at `~/.config/redeploy/devices.yaml` (chmod 600 — safe for SSH key paths).

## CLI reference

### `redeploy run SPEC [options]`

Execute deploy from a YAML spec file (or `redeploy.yaml` project manifest if no arg).

| Option | Description |
|--------|-------------|
| `--plan-only` | Show steps without connecting via SSH |
| `--dry-run` | Connect, show steps, make no changes |
| `--detect` | Live-probe host before planning (recommended for prod) |
| `--plan-out FILE` | Save generated plan to file |

### `redeploy scan [options]`

Discover SSH-accessible devices on the local network.

| Source | Network activity | Requires |
|--------|-----------------|---------|
| `known_hosts` | none | `~/.ssh/known_hosts` |
| `arp` | none | `ip neigh` / `arp -a` |
| `mdns` | passive listen | `avahi-browse` |
| `ping_sweep` | ICMP — **active** | `--ping` flag |

All SSH-reachable devices are saved to registry. Existing entries updated (last_seen, mac, hostname). Old entries never deleted.

### `redeploy target DEVICE_ID [SPEC] [options]`

Deploy a spec to a registered device. Device's `host`, `strategy`, `app`, `domain` are overlaid onto the spec.

```bash
redeploy target pi@192.168.1.42                           # uses migration.yaml in cwd
redeploy target pi@192.168.1.42 custom.yaml --dry-run
redeploy target prod-vps --detect --plan-only
```

After successful deploy, a `DeployRecord` is saved to the device in registry (timestamp, strategy, version, ok/fail).

### `redeploy detect / plan / apply / migrate / init / status`

```bash
redeploy detect --host root@VPS_IP --app myapp -o infra.yaml
redeploy plan   --infra infra.yaml --target target.yaml -o plan.yaml
redeploy apply  --plan plan.yaml
redeploy migrate --host root@VPS_IP --app myapp --target target.yaml  # all in one
redeploy init                        # scaffold migration.yaml + redeploy.yaml
redeploy status                      # show project manifest summary
```

## Deployment strategies

| Strategy | Description | Use case |
|----------|-------------|----------|
| `docker_full` | Docker Compose — build + up | VPS production |
| `podman_quadlet` | Rootless Podman systemd units | Quadlet/rootless VPS |
| `native_kiosk` | systemd + Chromium Openbox | RPi kiosk (no Docker) |
| `docker_kiosk` | Podman Quadlet in kiosk mode | RPi kiosk with container |
| `k3s` | Kubernetes/k3s | K3s cluster |
| `systemd` | Native systemd service | Bare metal |

### `native_kiosk` plan steps

Generated automatically when `strategy: native_kiosk`:

```
rsync_build            → sync build/ to device
run_kiosk_installer    → bash build/infra/install-kiosk.sh
install_kiosk_service  → scp kiosk.service → /etc/systemd/system/
enable_kiosk_service   → systemctl enable --now
wait_kiosk_start       → 20s
http_health_check      → curl http://localhost:8080
```

### `docker_kiosk` plan steps

```
rsync_build            → sync build/ to device
install_kiosk_quadlet  → cp *.container → ~/.config/containers/systemd/ + daemon-reload
start_kiosk_container  → systemctl --user restart app.service
wait_kiosk_start       → 20s
http_health_check      → curl http://localhost:8080
```

## `migration.yaml` spec format

```yaml
name: "myapp deploy 1.0.19 → 1.0.20"
description: "Production VPS version bump"

source:
  strategy: docker_full       # docker_full | podman_quadlet | native_kiosk | docker_kiosk | k3s | systemd
  host: root@87.106.87.183   # SSH target (user@ip) or "local"
  app: myapp
  version: "1.0.19"
  domain: myapp.example.com
  remote_dir: ~/myapp

target:
  strategy: docker_full
  host: root@87.106.87.183
  app: myapp
  version: "1.0.20"
  domain: myapp.example.com
  remote_dir: ~/myapp
  compose_files:
    - docker-compose.vps.yml
  env_file: envs/vps.env
  verify_url: https://myapp.example.com/api/v1/health
  verify_version: "1.0.20"

extra_steps:                  # optional — appended after generated steps
  - id: flush_k3s_iptables    # named step from StepLibrary
  - id: notify_slack
    action: ssh_cmd
    description: "Send deploy notification"
    command: "curl -s -X POST $SLACK_WEBHOOK -d '{\"text\":\"deployed 1.0.20\"}'"
    risk: low
```

## `redeploy.yaml` project manifest

Place in project root — `redeploy run` (no args) uses it automatically:

```yaml
spec: migration.yaml          # default spec file
host: root@87.106.87.183
app: myapp
domain: myapp.example.com
ssh_port: 22
env_file: envs/vps.env
```

## doql integration

redeploy is the deploy engine for [doql](https://github.com/softreck/doql) declarative apps.

```bash
# Install with doql integration
pip install doql[deploy]

# doql build generates build/infra/migration.yaml automatically
DEPLOY_HOST=root@YOUR_VPS doql build

# Then deploy — no args needed
doql deploy              # calls redeploy API internally
doql deploy --plan-only
doql deploy --dry-run
doql quadlet --install   # installs Quadlet units via redeploy
```

doql `DEPLOY.target` → redeploy `strategy` mapping:

| doql | redeploy |
|------|---------|
| `docker-compose` | `docker_full` |
| `quadlet` | `podman_quadlet` |
| `kiosk-appliance` | `native_kiosk` |
| `kubernetes` | `k3s` |

## Examples

| Directory | Scenario | Strategy |
|-----------|----------|----------|
| `01-vps-version-bump` | VPS Docker version bump | `docker_full → docker_full` |
| `02-k3s-to-docker` | Migrate off k3s | `k3s → docker_full` |
| `03-docker-to-podman-quadlet` | Move to rootless Podman | `docker_full → podman_quadlet` |
| `04-rpi-kiosk` | Raspberry Pi kiosk update | `native_kiosk → native_kiosk` |
| `05-iot-fleet-ota` | IoT fleet OTA update | `docker_full → docker_full` |
| `09-fleet-yaml` | Fleet with stages + scan | fleet + `redeploy target` |
| `11-traefik-tls` | Traefik + Let's Encrypt | `docker_full → podman_quadlet` |
| `12-ci-pipeline` | GitHub Actions / GitLab CI | CI-triggered `docker_full` |

```bash
# Run any example in dry-run mode (no SSH required):
redeploy run examples/01-vps-version-bump/migration.yaml --plan-only
redeploy run examples/04-rpi-kiosk/migration.yaml --plan-only
```

## License

Licensed under Apache-2.0.

# redeploy


## AI Cost Tracking

![PyPI](https://img.shields.io/badge/pypi-costs-blue) ![Version](https://img.shields.io/badge/version-0.2.9-blue) ![Python](https://img.shields.io/badge/python-3.9+-blue) ![License](https://img.shields.io/badge/license-Apache--2.0-green)
![AI Cost](https://img.shields.io/badge/AI%20Cost-$4.20-orange) ![Human Time](https://img.shields.io/badge/Human%20Time-8.0h-blue) ![Model](https://img.shields.io/badge/Model-openrouter%2Fqwen%2Fqwen3--coder--next-lightgrey)

- 🤖 **LLM usage:** $4.2000 (28 commits)
- 👤 **Human dev:** ~$802 (8.0h @ $100/h, 30min dedup)

Generated on 2026-04-20 using [openrouter/qwen/qwen3-coder-next](https://openrouter.ai/qwen/qwen3-coder-next)

---

![PyPI](https://img.shields.io/badge/pypi-redeploy-blue) ![Version](https://img.shields.io/badge/version-0.2.9-blue) ![Python](https://img.shields.io/badge/python-3.10+-blue) ![License](https://img.shields.io/badge/license-Apache--2.0-green)

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
# Recommended — installs CLI globally (no venv conflicts)
pipx install redeploy

# Or inside a venv
pip install redeploy

# With doql integration (generates migration.yaml from app.doql):
pip install doql[deploy]
```

## Quick start — VPS production deploy

```bash
# 1. Create spec file
cat > migration.yaml << 'EOF'
name: "myapp deploy 1.0.19 → 1.0.20"
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
  env_file: envs/prod.env
  compose_files:
    - docker-compose.prod.yml
  verify_url: https://myapp.example.com/api/v1/health
  verify_version: "1.0.20"
EOF

# 2. Preview steps (no SSH needed)
redeploy run migration.yaml --plan-only

# 3. Dry run (connects via SSH, makes no changes)
redeploy run migration.yaml --dry-run

# 4. Full deploy (live detect → plan → apply)
redeploy run migration.yaml --detect

# Or without --detect (faster, uses spec source as-is)
redeploy run migration.yaml
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
| `--env NAME` | Use named environment from `redeploy.yaml` (e.g. `prod`, `rpi5`) |
| `--plan-out FILE` | Save generated plan to file |

```bash
redeploy run --env prod             # use prod env from redeploy.yaml
redeploy run --env rpi5 --detect    # deploy to rpi5 with live probe
redeploy run --dry-run              # uses .env DEPLOY_* vars if no redeploy.yaml
```

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

### `podman_quadlet` plan steps

```
sync_env               → scp .env to remote
install_quadlet_files  → cp *.container *.network *.volume → ~/.config/containers/systemd/
podman_daemon_reload   → systemctl --user daemon-reload
stop_<app>             → systemctl --user stop <app>.service
start_<app>            → systemctl --user start <app>.service
wait_startup           → 15s
http_health_check      → verify_url health endpoint
version_check          → verify_version match
```

For system (root) mode, set `stop_services: true` in `target` — switches to `systemctl` (no `--user`) and `/etc/containers/systemd/`.

### `docker_full` plan steps

```
sync_env               → scp env_file → remote_dir/.env
docker_build_pull      → docker compose build (on remote)
docker_compose_up      → docker compose up -d --build
wait_startup           → 30s
http_health_check      → verify_url health endpoint
version_check          → verify_version match
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

extra_steps:                   # optional — appended or inserted
  - id: flush_k3s_iptables     # StepLibrary name — no action needed
    insert_before: docker_build_pull   # inject before specific step
  - id: docker_prune           # StepLibrary: prune unused images
  - id: notify_slack           # custom step (needs action:)
    action: ssh_cmd
    description: "Send deploy notification"
    command: "curl -s -X POST $SLACK_WEBHOOK -d '{\"text\":\"deployed 1.0.20\"}'"
    risk: low
```

## StepLibrary — reusable named steps

Reference any step by `id` alone — no `action` needed. Fields can be overridden:

```yaml
extra_steps:
  - id: flush_k3s_iptables           # use as-is
  - id: stop_k3s
  - id: http_health_check
    url: https://myapp.example.com/health   # override url
  - id: wait_startup_long            # 60s instead of 30s
```

| ID | Action | Description |
|----|--------|-------------|
| `flush_k3s_iptables` | `ssh_cmd` | Flush CNI-HOSTPORT-DNAT + KUBE-* chains (stale k3s rules block Docker-proxy on 80/443) |
| `delete_k3s_ingresses` | `kubectl_delete` | Delete all k3s ingresses |
| `stop_k3s` | `systemctl_stop` | Stop k3s service |
| `disable_k3s` | `systemctl_disable` | Disable k3s on boot |
| `stop_nginx` | `systemctl_stop` | Stop host nginx (port 80 conflict) |
| `restart_traefik` | `ssh_cmd` | Restart Traefik container |
| `docker_prune` | `ssh_cmd` | Prune unused images + build cache |
| `docker_compose_down` | `docker_compose_down` | Stop Docker Compose stack |
| `wait_startup` | `wait` | Wait 30s |
| `wait_startup_long` | `wait` | Wait 60s |
| `http_health_check` | `http_check` | Verify health endpoint (`expect: healthy`) |
| `version_check` | `version_check` | Verify deployed version |
| `sync_env` | `scp` | Copy .env to remote |
| `podman_daemon_reload` | `systemctl_start` | `systemctl --user daemon-reload` |
| `stop_podman` | `systemctl_stop` | Stop all Podman containers via systemd |
| `enable_podman_unit` | `systemctl_start` | `systemctl daemon-reload && enable --now {service}.service` |
| `systemctl_restart` | `systemctl_start` | Restart a systemd service (`command=` to override) |
| `systemctl_daemon_reload` | `ssh_cmd` | `systemctl daemon-reload` |
| `git_pull` | `ssh_cmd` | `git pull --ff-only` with rollback (`git reset --hard HEAD@{1}`) |

### `insert_before`

By default extra steps are appended after all generated steps. Use `insert_before: <step_id>` to inject at a specific position:

```yaml
extra_steps:
  - id: flush_k3s_iptables
    insert_before: docker_build_pull   # runs before build, not after verify
```

## Plugin system

Extend the step pipeline with custom action types using `action: plugin`:

```yaml
extra_steps:
  - id: reload_kiosk
    action: plugin
    plugin_type: browser_reload
    description: Reload kiosk browser after deploy
    plugin_params:
      port: 9222
      ignore_cache: true
      url_contains: "localhost:8100"
```

### Built-in plugins

| `plugin_type` | Description | `plugin_params` |
|---------------|-------------|-----------------|
| `browser_reload` | Reload Chromium via CDP (Chrome DevTools Protocol) over SSH | `port` (9222), `ignore_cache` (true), `url_contains` ("") |

### Writing a custom plugin

Place a `.py` file in `./redeploy_plugins/` (project-local) or `~/.redeploy/plugins/` (user-global):

```python
# ./redeploy_plugins/notify.py
from redeploy.plugins import register_plugin, PluginContext
from redeploy.models import StepStatus

@register_plugin("notify_slack")
def notify_slack(ctx: PluginContext) -> None:
    webhook = ctx.params["webhook"]
    ctx.probe.run(f"curl -X POST {webhook} -d '{{\"text\":\"deployed!\"}}'")
    ctx.step.result = "notified"
    ctx.step.status = StepStatus.DONE
```

`PluginContext` fields:

| Field | Type | Description |
|-------|------|-------------|
| `step` | `MigrationStep` | Current step — set `result` and `status` here |
| `host` | `str` | SSH host (e.g. `pi@192.168.1.5`) |
| `probe` | `RemoteProbe` | Call `probe.run(cmd)` for remote SSH commands |
| `emitter` | `ProgressEmitter?` | Emit mid-step progress: `emitter.progress(step.id, msg)` |
| `params` | `dict` | Shortcut for `step.plugin_params` |
| `dry_run` | `bool` | Skip side-effects if True |



Place in project root — `redeploy run` (no args) uses it automatically.
Supports **named environments** for multi-target projects:

```yaml
spec: migration.yaml          # default spec file
app: myapp

environments:
  prod:
    host: root@87.106.87.183
    strategy: docker_full
    domain: myapp.example.com
    env_file: envs/vps.env
    verify_url: https://myapp.example.com/api/v1/health
  rpi5:
    host: pi@192.168.188.108
    strategy: systemd
    env_file: .env
    verify_url: http://192.168.188.108:8000/api/v1/health
  dev:
    host: local
    strategy: docker_full
    env_file: .env.local
    verify_url: http://localhost:8000/api/v1/health
```

Fallback: if no `redeploy.yaml` found, `redeploy run` reads `DEPLOY_*` vars from `.env`:

```bash
# .env
DEPLOY_HOST=pi@192.168.1.5
DEPLOY_APP=myapp
DEPLOY_DOMAIN=myapp.local
DEPLOY_ENV_FILE=.env
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

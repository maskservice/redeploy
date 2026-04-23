# redeploy


## AI Cost Tracking

![PyPI](https://img.shields.io/badge/pypi-costs-blue) ![Version](https://img.shields.io/badge/version-0.2.68-blue) ![Python](https://img.shields.io/badge/python-3.9+-blue) ![License](https://img.shields.io/badge/license-Apache--2.0-green)
![AI Cost](https://img.shields.io/badge/AI%20Cost-$7.50-orange) ![Human Time](https://img.shields.io/badge/Human%20Time-35.1h-blue) ![Model](https://img.shields.io/badge/Model-openrouter%2Fqwen%2Fqwen3--coder--next-lightgrey)

- 🤖 **LLM usage:** $7.5000 (89 commits)
- 👤 **Human dev:** ~$3512 (35.1h @ $100/h, 30min dedup)

Generated on 2026-04-23 using [openrouter/qwen/qwen3-coder-next](https://openrouter.ai/qwen/qwen3-coder-next)

---

![PyPI](https://img.shields.io/badge/pypi-redeploy-blue) ![Version](https://img.shields.io/badge/version-0.2.68-blue) ![Python](https://img.shields.io/badge/python-3.10+-blue) ![License](https://img.shields.io/badge/license-Apache--2.0-green)

Infrastructure migration and device deploy toolkit — VPS, Raspberry Pi kiosk, Podman Quadlet, k3s.

```
redeploy detect   →  live probe host        (what is there now)
redeploy plan     →  migration-plan.yaml    (what to do)
redeploy apply    →  execute plan           (do it)
redeploy run      →  detect + plan + apply  (all at once from spec)
redeploy fix      →  bump + run + LLM heal  (smart self-healing deploy)
redeploy bump     →  bump version in spec   (patch/minor/major)
redeploy prompt   →  NLP → command via LLM  (natural language interface)
redeploy mcp      →  start MCP server       (Claude Desktop / VS Code / remote API)
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

## Declarative config workflow

redeploy supports a declarative configuration workflow for hardware settings — scan to YAML, edit locally, and apply to device:

```bash
# 1. Scan hardware state to YAML
redeploy hardware pi@192.168.188.109 > hardware.yaml
redeploy device-map pi@192.168.188.109 > device-map.yaml

# 2. Edit YAML locally (e.g., change display rotation)
# hardware.yaml:
#   drm_outputs:
#   - name: card0-DSI-2
#     connector: DSI-2
#     transform: '270'  # ← edit this value

# 3. Apply config to remote device
redeploy hardware pi@192.168.188.109 --apply-config hardware.yaml
redeploy device-map pi@192.168.188.109 --apply-config device-map.yaml
```

**What `--apply-config` does:**
- Applies display transforms via `wlr-randr` (Wayland compositor)
- Updates kanshi config (`~/.config/kanshi/config`) for persistent display rotation
- Sets backlight brightness and power state
- Supports both YAML and JSON config files

**Supported commands:**
- `redeploy hardware --apply-config FILE`
- `redeploy device-map --apply-config FILE`
- `redeploy blueprint show FILE --apply-config FILE`

## JMESPath query support

Extract specific values from YAML/JSON output using JMESPath query language (similar to XPath for XML):

```bash
# Simple path queries
redeploy hardware pi@192.168.188.109 --query "drm_outputs[0].transform"
redeploy hardware pi@192.168.188.109 --query "kernel"
redeploy device-map pi@192.168.188.109 --query "host"

# Filter queries
redeploy hardware pi@192.168.188.109 --query "backlights[?name==\`11-0045\`].brightness"
redeploy hardware pi@192.168.188.109 --query "drm_outputs[?connector==\`DSI-2\`].transform"

# From saved YAML files
redeploy blueprint show blueprint.yaml --query "hardware.drm_outputs[0].transform"
redeploy device-map --show device-map.yaml --query "tags"

# JSON output
redeploy hardware pi@192.168.188.109 --query "tags" --format json
```

**JMESPath features:**
- **Simple paths:** `kernel`, `host`, `board`
- **Array indexing:** `drm_outputs[0].transform`
- **Filtering:** `[?name==\`11-0045\`]`
- **Projections:** `backlights[0].[name,brightness]`
- **Wildcards:** `drm_outputs[*].transform`

**Supported commands:**
- `redeploy hardware --query EXPR`
- `redeploy device-map --query EXPR`
- `redeploy blueprint show FILE --query EXPR`

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

### Generic pipeline hooks (recommended)

Use top-level `hooks:` in your migration spec to run custom actions in specific phases.

Supported phases:
- `before_apply`
- `before_step`
- `after_step`
- `on_step_failure`
- `on_step_retry`
- `after_apply`
- `on_failure`
- `always`

Minimal example:

```yaml
hooks:
  - id: refresh_cache
    phase: after_apply
    action: local_cmd
    command: "curl -fsS -X POST http://localhost:8100/api/v3/cache/clear || true"
    on_failure: warn

  - id: open_browser
    phase: after_apply
    action: open_url
    url: http://localhost:8100/
    on_failure: warn

  - id: before_sync_env_note
    phase: before_step
    when: "step.id == 'sync_env'"
    action: local_cmd
    command: "echo '[hook] about to run sync_env'"
    on_failure: continue
```

Notes:
- `when:` currently supports simple conditions like `step.id == 'sync_env'` and `step.id != 'sync_env'`.
- Legacy `post_deploy`/`pre_deploy` blocks are still accepted and auto-migrated internally.
- New specs should use `hooks:` only.

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

## Inline Scripts

Execute multiline bash scripts directly from YAML without external files:

```yaml
extra_steps:
  - id: configure_kiosk
    action: inline_script
    description: "Deploy kiosk launch script"
    command: |
      #!/bin/bash
      mkdir -p ~/c2004/config
      cat > ~/c2004/config/kiosk-launch.sh << 'EOF'
      #!/bin/bash
      if command -v chromium-browser >/dev/null 2>&1; then
        chromium-browser --kiosk http://localhost:8100
      elif command -v firefox >/dev/null 2>&1; then
        firefox --kiosk http://localhost:8100
      fi
      EOF
      chmod +x ~/c2004/config/kiosk-launch.sh
    risk: medium
    timeout: 60
```

The script is base64-encoded and executed via SSH with automatic temp file cleanup. Use `command` field for multiline script content (YAML `|` preserves newlines).

### Script References (`command_ref`)

Instead of duplicating scripts in YAML, reference a script defined in a markdown codeblock:

```yaml
extra_steps:
  - id: configure_kiosk
    action: inline_script
    description: "Execute kiosk script from markdown"
    command_ref: "#kiosk-browser-configuration-script"
    risk: medium
```

In your migration markdown file, define the script in a section:

```markdown
## Kiosk Browser Configuration Script

```bash
#!/bin/bash
# Auto-detect browser...
if command -v chromium-browser >/dev/null 2>&1; then
  chromium-browser --kiosk http://localhost:8100
fi
```
```

**Benefits:**
- Single source of truth — script lives in one place (markdown codeblock)
- No duplication between markdown documentation and YAML
- Easy to read and maintain
- Changes to the codeblock automatically apply to the deployment

**Reference formats:**
- `"#section-id"` — script from section in current spec file
- `"./file.md#section-id"` — script from section in specific file

The section ID is derived from the heading: spaces become hyphens, lowercase.
Example: `## Kiosk Browser Configuration Script` → `#kiosk-browser-configuration-script`

### Execute Script by Reference (`redeploy exec`)

Run a single script from markdown without running the full migration:

```bash
# Execute script from codeblock on remote host
redeploy exec '#kiosk-browser-configuration-script' \
    --host pi@192.168.188.108 \
    --file migration.podman-rpi5-resume.md

# With file in reference
redeploy exec './migration.md#install-deps' --host root@server.com

# Using markpact:ref (more explicit)
redeploy exec 'kiosk-script-id' --host pi@192.168.188.108 --file migration.md

# Dry-run to preview script
redeploy exec '#backup-script' --host pi@192.168.188.108 --file ops.md --dry-run
```

This is useful for:
- One-off operations defined in markdown docs
- Testing individual scripts before full migration
- Running maintenance tasks

### Execute Multiple Scripts (`redeploy exec-multi`)

Test multiple scripts at once:

```bash
# Execute multiple scripts by ref
redeploy exec-multi 'kiosk-script,install-deps,cleanup' \
    --host pi@192.168.188.108 \
    --file migration.md

# Mix of markpact:ref and section headings
redeploy exec-multi 'script1,#section2,script3' \
    --host root@server.com \
    --file deploy.md \
    --dry-run
```

### Marking Codeblocks with `markpact:ref`

For more explicit script identification, use `markpact:ref <id>` in codeblock:

```markdown
```bash markpact:ref kiosk-browser-configuration-script
#!/bin/bash
# Auto-detect browser...
if command -v chromium-browser >/dev/null 2>&1; then
  chromium-browser --kiosk http://localhost:8100
fi
```
```

Benefits of `markpact:ref`:
- Explicit ID assignment (not derived from heading)
- Multiple scripts per section
- Can reference by simple ID instead of full heading
- Self-documenting in markdown



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

IaC/CI config coverage (via `redeploy import`, used by doql/redeploy workflows):
- Docker Compose + Dockerfile
- nginx configs (`nginx.conf`, `*.conf`)
- Kubernetes manifests (`apiVersion` + `kind` YAML)
- Terraform (`*.tf`, `*.tfvars`)
- TOML (`pyproject.toml`, app/tool TOML)
- Vite config (`vite.config.ts/js/mjs/cjs`)
- CI/CD: GitHub Actions, GitLab CI, Jenkinsfile

Parser plugin extension:
- Python entry points: `redeploy.iac.parsers`
- Project-local parsers: `./redeploy_iac_parsers/*.py`
- User-global parsers: `~/.redeploy/iac_parsers/*.py`

Built-in template generator:
- `redeploy import --list-plugin-templates`
- `redeploy import --plugin-template helm-kustomize`
- `redeploy import --plugin-template argocd-flux --plugin-dir redeploy_iac_parsers`

Example external plugin (Helm + Ansible):
- Source template: `examples/redeploy_iac_parsers/helm_ansible.py`
- Quick start:
  1. `mkdir -p redeploy_iac_parsers`
  2. `cp examples/redeploy_iac_parsers/helm_ansible.py redeploy_iac_parsers/`
  3. `redeploy import path/to/Chart.yaml`
  4. `redeploy import path/to/playbook.yml`

Example external plugin (Helm templates + Kustomize):
- Source template: `examples/redeploy_iac_parsers/helm_kustomize.py`
- Quick start:
  1. `mkdir -p redeploy_iac_parsers`
  2. `cp examples/redeploy_iac_parsers/helm_kustomize.py redeploy_iac_parsers/`
  3. `redeploy import path/to/chart/templates/deployment.yaml`
  4. `redeploy import path/to/kustomization.yaml`

Example external plugin (ArgoCD Application + Flux Kustomization):
- Source template: `examples/redeploy_iac_parsers/argocd_flux.py`
- Quick start:
  1. `mkdir -p redeploy_iac_parsers`
  2. `cp examples/redeploy_iac_parsers/argocd_flux.py redeploy_iac_parsers/`
  3. `redeploy import path/to/argocd-application.yaml`
  4. `redeploy import path/to/flux-kustomization.yaml`

Example external plugin (GitOps CI for ArgoCD/Flux):
- Source template: `examples/redeploy_iac_parsers/gitops_ci.py`
- Quick start:
  1. `mkdir -p redeploy_iac_parsers`
  2. `cp examples/redeploy_iac_parsers/gitops_ci.py redeploy_iac_parsers/`
  3. `redeploy import .github/workflows/deploy-gitops.yml`
  4. `redeploy import .gitlab-ci.yml`

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

## Self-healing deploy — `redeploy fix`

`redeploy fix` is the recommended day-to-day deploy command. It:
1. bumps the patch version in `VERSION` + spec header
2. applies the migration spec with `--heal` enabled
3. if a step fails, calls an LLM (via LiteLLM / OpenRouter) to suggest a fix and retries automatically

```bash
# Self-healing deploy: bump version → run → LLM retry on failure
redeploy fix .
redeploy fix redeploy/pi109/migration.md

# With a problem hint for the LLM
redeploy fix . --hint "service not starting after update"
redeploy fix . --hint "brak ikon SVG w menu"

# Preview only (no apply)
redeploy fix . --dry-run

# Bump minor version instead of patch
redeploy fix . --minor

# Bump major version
redeploy fix . --major
redeploy fix . --retries 5

# Skip version bump
redeploy fix . --no-bump
```

Spec discovery from `.`:
- `./migration.md` or `./migration.yaml` — direct match
- `./redeploy/<target>/migration.md` — project pattern (lists targets, asks if multiple)
- Recursive fallback anywhere under the directory

`redeploy fix` automatically discovers migration specs — running from project root
with multiple targets prompts interactively.

### Version management — `redeploy bump`

```bash
# Bump patch (default): 1.0.31 → 1.0.32
redeploy bump .
redeploy bump redeploy/pi109/migration.md

# Bump minor: 1.0.31 → 1.1.0
redeploy bump . --minor

# Bump major: 1.0.31 → 2.0.0
redeploy bump . --major
```

Updates `VERSION` file and all version references in the migration spec
(`version:`, `name: "... vX.Y.Z"`, `description: "... vX.Y.Z"`).

### LLM self-healing on `redeploy run`

`redeploy run` also supports `--heal` mode (enabled by default):

```bash
# Run with LLM self-healing (default)
redeploy run migration.yaml

# Disable healing
redeploy run migration.yaml --no-heal

# Pass problem description to LLM
redeploy run migration.yaml --fix "nginx port conflict"

# Max heal retries
redeploy run migration.yaml --max-heal-retries 5
```

LLM reads the failed step output, runs SSH diagnostics, and patches the spec YAML.
Repairs are logged to `REPAIR_LOG.md` next to the spec.

Requires `OPENROUTER_API_KEY` (or `OPENAI_API_KEY`) in `.env` or `~/.redeploy/.env`.
Model defaults to `openrouter/qwen/qwen3-coder-next` (override with `LLM_MODEL=...`).

---

## Natural language interface — `redeploy prompt`

```bash
# Map a natural language instruction to a redeploy command
redeploy prompt "deploy c2004 to pi109"
redeploy prompt "pokaż plan deployu na pi109"
redeploy prompt "bump version and redeploy" --yes
redeploy prompt "what specs are available?" --schema-only

# Force dry-run on generated command
redeploy prompt "run the pi109 migration" --dry-run

# Skip confirmation
redeploy prompt "fix the frontend service" --yes

# Preview the workspace schema sent to the LLM
redeploy prompt "..." --show-schema
```

The LLM receives a workspace schema (discovered specs, version, git branch, command catalogue)
and maps the instruction to a concrete `redeploy` invocation.

Language is auto-detected — Polish, English, or any language the model supports.

---

## MCP server — `redeploy mcp`

redeploy exposes an [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server,
letting AI assistants (Claude Desktop, VS Code Copilot, custom agents) call redeploy operations
as structured tools.

### Start

```bash
# stdio — for Claude Desktop / VS Code local integration
redeploy mcp

# HTTP SSE — for remote/shared access
redeploy mcp --transport sse --port 8811

# Streamable HTTP
redeploy mcp --transport http --port 8811

# Standalone binary (no CLI wrapper)
redeploy-mcp --transport sse
```

### Available MCP tools

| Tool | Description |
|------|-------------|
| `schema` | Discover workspace: specs, version, git branch, command catalogue |
| `list_specs` | List all migration specs found in a directory |
| `plan_spec` | Preview a spec (dry-run) — safe, no changes |
| `run_spec` | Apply a migration spec |
| `fix_spec` | Self-healing deploy: bump → apply → LLM retry |
| `bump_version` | Bump patch/minor/major version |
| `diagnose` | SSH diagnostics on a remote host |
| `exec_ssh` | Run an ad-hoc command on a remote host |
| `nlp_command` | Translate NLP instruction → redeploy command |

### MCP resources

| URI | Description |
|-----|-------------|
| `redeploy://workspace` | Current workspace schema as JSON |
| `redeploy://spec/{path}` | Raw content of a migration spec file |

### Claude Desktop integration

Add to `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "redeploy": {
      "command": "redeploy",
      "args": ["mcp"]
    }
  }
}
```

### VS Code Copilot integration

Add to `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "redeploy": {
      "type": "stdio",
      "command": "redeploy",
      "args": ["mcp"]
    }
  }
}
```

Or for an SSE server already running on a remote machine:

```json
{
  "servers": {
    "redeploy-remote": {
      "type": "sse",
      "url": "http://192.168.188.109:8811/sse"
    }
  }
}
```

### Install with MCP dependencies

```bash
pip install "redeploy[mcp]"
```

---

## Hardware diagnostics commands

### `redeploy hardware HOST [options]`


Probe and diagnose hardware on a remote host (DSI display, DRM connectors, backlight, I2C, config.txt, Wayland compositor).

| Option | Description |
|--------|-------------|
| `--format [yaml|json]` | Output format (default: yaml) |
| `--fix` | Print fix commands for all issues found |
| `--apply-fix COMPONENT` | Run fix for specific component via SSH |
| `--panel PANEL_ID` | Specify panel ID explicitly |
| `--list-panels` | List available panel definitions |
| `--set-transform TRANSFORM` | Set display rotation for DSI output (normal, 90, 180, 270, flipped, etc.) |
| `--apply-config FILE` | Apply display settings from YAML/JSON config file |
| `--query EXPR` | Extract specific values using JMESPath query |
| `--ssh-key PATH` | SSH private key path |

```bash
redeploy hardware pi@192.168.188.109
redeploy hardware pi@192.168.188.109 --fix
redeploy hardware pi@192.168.188.109 --set-transform 270
redeploy hardware pi@192.168.188.109 --apply-config hardware.yaml
redeploy hardware pi@192.168.188.109 --query "drm_outputs[0].transform"
```

### `redeploy device-map HOST [options]`

Generate full device snapshot (hardware + infra + diagnostics).

| Option | Description |
|--------|-------------|
| `--name TEXT` | Human-friendly device label |
| `--tag TEXT` | Tag(s) to attach (repeatable) |
| `--save` | Persist map to `~/.config/redeploy/device-maps/` |
| `--out PATH` | Save to specific file |
| `--format [yaml|json]` | Output format (default: yaml) |
| `--no-infra` | Skip infra probe (hardware only) |
| `--list` | List saved device maps |
| `--show PATH` | Load and display saved device-map file |
| `--diff PATH...` | Diff two saved device-map files |
| `--apply-config FILE` | Apply hardware/infra settings from YAML config file |
| `--query EXPR` | Extract specific values using JMESPath query |
| `--ssh-key PATH` | SSH private key path |

```bash
redeploy device-map pi@192.168.188.109 --save --name "kiosk-lab"
redeploy device-map --list
redeploy device-map --show ~/.config/redeploy/device-maps/pi_at_192.168.188.109.yaml
redeploy device-map pi@192.168.188.109 --apply-config device-map.yaml
redeploy device-map pi@192.168.188.109 --query "hardware.drm_outputs[0].transform"
```

### `redeploy blueprint [command]`

Manage device blueprints (capture, show, list, twin, migrate).

#### `redeploy blueprint capture HOST [options]`

Capture device state as blueprint.

| Option | Description |
|--------|-------------|
| `--format [yaml|json]` | Output format (default: yaml) |
| `--save` | Persist to `~/.config/redeploy/blueprints/` |
| `--out PATH` | Save to specific file |
| `--ssh-key PATH` | SSH private key path |

#### `redeploy blueprint show FILE [options]`

Display saved blueprint.

| Option | Description |
|--------|-------------|
| `--format [yaml|json]` | Output format (default: yaml) |
| `--apply-config FILE` | Apply blueprint settings from YAML config file |
| `--query EXPR` | Extract specific values using JMESPath query |

```bash
redeploy blueprint capture pi@192.168.188.109 > blueprint.yaml
redeploy blueprint show blueprint.yaml --apply-config blueprint.yaml
redeploy blueprint show blueprint.yaml --query "hardware.drm_outputs[0].transform"
```

## License

Licensed under Apache-2.0.

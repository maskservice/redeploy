# 09 — Fleet YAML + redeploy.yaml

Full `fleet.yaml` example with stages, tags, expectations and a `redeploy.yaml` project manifest.

## Files

| File | Purpose |
|------|---------|
| `fleet.yaml` | Device inventory with stage/tags/expectations |
| `redeploy.yaml` | Project manifest — redeploy picks up host/domain automatically |

## Key concepts

### Stage

```yaml
stage: prod   # local | dev | staging | prod | ci
```

Stage determines default expectations automatically:
- `prod` → `[has_docker, has_docker_compose, ssh_reachable, https_reachable, no_k3s]`
- `dev`  → `[has_docker, ssh_reachable]`
- `local`→ `[has_docker]`

### DeviceExpectation tags

```yaml
expectations:
  - has_docker
  - has_traefik
  - no_k3s          # fail if k3s is active (conflicts with Docker on 80/443)
  - https_reachable
  - disk_ok
```

Use `device.verify_expectations(infra_state)` to cross-check after `detect`.

### Query helpers

```python
from redeploy.fleet import FleetConfig, Stage

fleet = FleetConfig.from_file("examples/09-fleet-yaml/fleet.yaml")

# All prod devices
fleet.prod_devices()

# All VPS devices
fleet.by_tag("vps")

# All docker_full devices
fleet.by_strategy("docker_full")

# Verify expectations against detected state
device = fleet.get_device("vps-prod")
failures = device.verify_expectations(infra_state)
```

### redeploy.yaml

Place `redeploy.yaml` in project root — then `redeploy run` with no args uses it:

```bash
cd myproject
redeploy run          # reads spec/host/domain from redeploy.yaml
redeploy run --detect # live probe + plan + apply
```

## Run

```bash
# Parse fleet.yaml and check expectations
redeploy devices

# Discover new devices on local network
redeploy scan

# Deploy to a specific device from fleet
redeploy target vps-prod examples/09-fleet-yaml/migration.yaml --plan-only
redeploy target vps-prod examples/09-fleet-yaml/migration.yaml --detect
```

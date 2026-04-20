# redeploy Fleet & Device Registry

`redeploy.fleet` — unified first-class view over `FleetConfig` (static fleet
manifest `fleet.yaml`) and `DeviceRegistry` (dynamic registry `devices.yaml`).

---

## Concepts

| Model | File | Source |
|---|---|---|
| `FleetConfig` / `FleetDevice` | `fleet.yaml` | Static manifest, version-controlled |
| `DeviceRegistry` / `KnownDevice` | `~/.config/redeploy/devices.yaml` | Dynamic, updated by `redeploy scan` |
| `Fleet` | both | Unified query API over either or both |

`Fleet` merges both sources: registry metadata (last_seen, ssh_ok) enriches
fleet.yaml devices; `DeviceRegistry`-only devices become plain `FleetDevice`s.

---

## Quick start

```python
from redeploy import Fleet

# Load from fleet.yaml
fleet = Fleet.from_file("fleet.yaml")

# Load from device registry
fleet = Fleet.from_registry()

# Merge both (registry metadata wins on id collision)
fleet = Fleet.from_file("fleet.yaml").merge(Fleet.from_registry())

# Query
prod_devices = fleet.prod()
kiosk_devices = fleet.by_tag("kiosk")
reachable     = fleet.reachable()
rpi_devices   = fleet.by_strategy("native_kiosk")
```

CLI:

```bash
redeploy fleet                        # list all from fleet.yaml + registry
redeploy fleet --tag kiosk
redeploy fleet --stage prod
redeploy fleet --reachable
redeploy devices                      # registry-only view
```

---

## `Fleet`

Unified, iterable collection of `FleetDevice` instances.

```python
from redeploy import Fleet, FleetDevice

# Construct directly
fleet = Fleet([
    FleetDevice(id="prod-1", ssh_host="root@10.0.0.1", tags=["prod"]),
    FleetDevice(id="dev-1",  ssh_host="root@10.0.0.2", tags=["dev"]),
])

len(fleet)       # → 2
list(fleet)      # → [FleetDevice(...), FleetDevice(...)]
fleet.get("prod-1")  # → FleetDevice(id='prod-1', ...)
```

### Class methods

#### `Fleet.from_file(path) → Fleet`

Load from `fleet.yaml`.

```python
fleet = Fleet.from_file("fleet.yaml")
fleet = Fleet.from_file(Path("/etc/redeploy/fleet.yaml"))
```

#### `Fleet.from_registry(path=None) → Fleet`

Load from `~/.config/redeploy/devices.yaml` (or custom path).
Converts `KnownDevice` → `FleetDevice`.

```python
fleet = Fleet.from_registry()
fleet = Fleet.from_registry(path=Path("./devices.yaml"))
```

#### `Fleet.from_config(config) → Fleet`

Wrap an existing `FleetConfig`.

```python
from redeploy import FleetConfig

config = FleetConfig.from_file("fleet.yaml")
fleet  = Fleet.from_config(config)
```

### Instance methods

#### `merge(other) → Fleet`

Union of two fleets.  `other` wins on `id` collision (registry metadata
enriches static manifest).

```python
static   = Fleet.from_file("fleet.yaml")
dynamic  = Fleet.from_registry()
combined = static.merge(dynamic)
```

#### `by_tag(tag) → Fleet`

Filter devices that have the given tag.

```python
kiosks = fleet.by_tag("kiosk")
```

#### `by_stage(stage) → Fleet`

Filter by deployment stage (`prod`, `staging`, `dev`, `lab`, …).

```python
prod = fleet.by_stage("prod")
```

#### `prod() → Fleet`

Shorthand for `by_stage("prod")`.

```python
prod_fleet = fleet.prod()
```

#### `by_strategy(strategy) → Fleet`

Filter by deploy strategy value string.

```python
docker_devices = fleet.by_strategy("docker_full")
kiosk_devices  = fleet.by_strategy("native_kiosk")
```

#### `reachable(max_age_hours=24) → Fleet`

Filter devices seen within `max_age_hours`.  Devices from `fleet.yaml` without
registry entry are included optimistically (no `last_seen` data).

```python
online = fleet.reachable()
online = fleet.reachable(max_age_hours=1)
```

#### `get(device_id) → FleetDevice | None`

Return device by id or None.

```python
device = fleet.get("rpi-kitchen")
```

### Dunder methods

```python
len(fleet)          # number of devices
list(fleet)         # iterate over FleetDevice instances
repr(fleet)         # Fleet(3 devices)
```

---

## `FleetDevice`

Single device in the fleet.

```python
from redeploy import FleetDevice, Stage, DeployStrategy

device = FleetDevice(
    id="rpi-kitchen",
    ssh_host="root@192.168.1.10",
    stage=Stage.PROD,
    tags=["kiosk", "rpi4"],
    strategy=DeployStrategy.NATIVE_KIOSK,
    app="kiosk-station",
    description="Kitchen display kiosk",
    last_seen=datetime.now(timezone.utc),
)
```

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | — | Unique device identifier |
| `ssh_host` | `str` | — | SSH address (`user@host`) |
| `stage` | `Stage` | `UNKNOWN` | Deployment stage |
| `tags` | `list[str]` | `[]` | Free-form tags |
| `strategy` | `DeployStrategy \| None` | `None` | Deploy strategy |
| `app` | `str \| None` | `None` | Primary app name |
| `description` | `str` | `""` | Human-readable label |
| `last_seen` | `datetime \| None` | `None` | Last registry update |
| `arch` | `DeviceArch \| None` | `None` | CPU architecture |
| `expectations` | `list[DeviceExpectation]` | `[]` | Pre-deploy checks |

---

## `FleetConfig` — static fleet manifest

Fleet manifest format (`fleet.yaml`):

```yaml
name: homelab-fleet
description: Production kiosks + development devices

stages:
  prod:
    expectations:
      - type: ssh_reachable
      - type: disk_free_gb
        threshold: 5
  dev:
    expectations: []

devices:
  - id: rpi-kitchen
    ssh_host: root@192.168.1.10
    stage: prod
    tags: [kiosk, rpi4]
    strategy: native_kiosk
    app: kiosk-station

  - id: rpi-office
    ssh_host: root@192.168.1.11
    stage: prod
    tags: [kiosk, rpi4]
    strategy: native_kiosk
    app: kiosk-station

  - id: dev-laptop
    ssh_host: root@192.168.1.50
    stage: dev
    tags: [dev, x86]
    strategy: docker_full
    app: myapp
```

```python
from redeploy import FleetConfig

config = FleetConfig.from_file("fleet.yaml")
print(config.devices)   # list[FleetDevice]
print(config.stages)    # dict[str, Stage]
```

---

## `DeviceRegistry` — dynamic device registry

Updated by `redeploy scan`.  Stored at `~/.config/redeploy/devices.yaml` (chmod 600).

```python
from redeploy import DeviceRegistry

reg = DeviceRegistry.load()

# Query
device = reg.get("rpi-kitchen")
if reg.is_reachable("rpi-kitchen"):
    print("online")

# Update
from redeploy import KnownDevice
from datetime import datetime, timezone

reg.upsert(KnownDevice(
    id="new-device",
    host="root@192.168.1.99",
    last_seen=datetime.now(timezone.utc),
    last_ssh_ok=True,
    strategy="docker_full",
    tags=["new"],
))
reg.save()
```

### `KnownDevice` fields

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique identifier (usually `user@ip`) |
| `host` | `str` | SSH address |
| `last_seen` | `datetime \| None` | Last scan timestamp |
| `last_ssh_ok` | `bool` | SSH connection succeeded on last scan |
| `strategy` | `str` | Detected deploy strategy |
| `app` | `str \| None` | Detected application |
| `tags` | `list[str]` | Tags set during scan or manually |
| `arch` | `str \| None` | CPU architecture |
| `is_reachable` | `bool` (property) | `last_seen` within last 24h and `last_ssh_ok` |

---

## Combining fleet + registry

```python
from redeploy import Fleet

# Merge: fleet.yaml provides structure, registry provides freshness
fleet = Fleet.from_file("fleet.yaml").merge(Fleet.from_registry())

# Only consider devices actually seen in the last hour
for device in fleet.reachable(max_age_hours=1).prod():
    print(f"Deploying to {device.id} @ {device.ssh_host}")
```

---

## Stage system

`Stage` enum values:

| Value | Description |
|---|---|
| `prod` | Production |
| `staging` | Pre-production / staging |
| `dev` | Development |
| `lab` | Lab / experimental |
| `unknown` | Not yet classified |

`STAGE_DEFAULT_EXPECTATIONS` provides sane defaults per stage (e.g. `prod`
requires `ssh_reachable` and `disk_free_gb ≥ 5`; `dev` has no mandatory checks).

```python
from redeploy import STAGE_DEFAULT_EXPECTATIONS, Stage

print(STAGE_DEFAULT_EXPECTATIONS[Stage.PROD])
```

---

## CLI

```bash
# Fleet view (fleet.yaml + registry merged)
redeploy fleet
redeploy fleet --tag kiosk
redeploy fleet --stage prod
redeploy fleet --reachable
redeploy fleet --json

# Registry-only view
redeploy devices
redeploy devices --tag kiosk
redeploy devices --reachable

# Update registry via scan
redeploy scan
redeploy scan --ping --subnet 192.168.1.0/24

# Deploy to a specific device from registry
redeploy target rpi-kitchen --strategy native_kiosk
```

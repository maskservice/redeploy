# redeploy Deploy Patterns

`redeploy.patterns` — pre-built multi-step deployment strategies that expand
into `MigrationStep` lists.  Set `pattern` in your target config or
`migration.yaml` to activate.

---

## Quick start

```bash
# List available patterns
redeploy patterns

# Show steps for a specific pattern
redeploy patterns blue_green
redeploy patterns canary
redeploy patterns rollback_on_failure

# Use in migration.yaml
redeploy run migration.yaml
```

In `migration.yaml` or target YAML:

```yaml
target:
  strategy: docker_full
  app: myapp
  remote_dir: ~/myapp
  verify_url: https://myapp.example.com/health
  pattern: blue_green
  pattern_config:
    traefik_network: proxy
    green_suffix: "-green"
```

Python API:

```python
from redeploy.patterns import BlueGreenPattern, get_pattern, list_patterns

# List all registered patterns
print(list_patterns())
# → ['blue_green', 'canary', 'rollback_on_failure']

# Expand to steps
p = BlueGreenPattern(app="myapp", remote_dir="~/myapp",
                     verify_url="http://localhost:8080")
for step in p.expand():
    print(step.id, step.action.value)
```

---

## Built-in patterns

### `blue_green` — Zero-downtime via Traefik label swap

Deploy new (green) version alongside existing (blue), verify health, swap
routing labels, retire blue.

**Requirements:**
- Traefik running in Docker with label-based routing
- Sufficient disk for two concurrent stacks

**Steps:**

| # | ID | Action | Rollback |
|---|---|---|---|
| 1 | `bg_sync_env` *(optional)* | `scp` | — |
| 2 | `bg_clone_green` | `ssh_cmd` | `rm -rf ~/myapp-green` |
| 3 | `bg_deploy_green` | `docker_build` | `compose down` on green |
| 4 | `bg_health_green` | `http_check` | — |
| 5 | `bg_swap_labels` | `ssh_cmd` | restore blue routing |
| 6 | `bg_verify_main` | `http_check` | — |
| 7 | `bg_retire_blue` | `docker_compose_down` | — |

**Configuration:**

```yaml
pattern: blue_green
pattern_config:
  green_suffix: "-green"       # appended to remote_dir and app name
  traefik_network: proxy       # Docker network Traefik listens on
  # env_file: .env             # if set, synced to green dir first
```

**Python:**

```python
from redeploy.patterns import BlueGreenPattern

p = BlueGreenPattern(
    app="myapp",
    remote_dir="~/myapp",
    verify_url="https://myapp.example.com/health",
    green_suffix="-green",
    traefik_network="proxy",
    env_file=".env",           # optional
)
steps = p.expand()
```

---

### `canary` — Gradual rollout with per-stage health checks

Deploy canary alongside main, scale up in configurable stages.
At 100% the canary directory is promoted to main.

**Steps** (with default stages `[10, 25, 50, 100]`):

| # | ID | Action | Notes |
|---|---|---|---|
| 1 | `canary_clone` | `ssh_cmd` | Copy main → canary dir |
| 2 | `canary_deploy` | `docker_build` | Start canary with 1 replica |
| 3 | `canary_health_10pct` | `http_check` | |
| 4 | `canary_wait_10pct` | `wait` | `stage_wait_seconds` |
| 5 | `canary_health_25pct` | `http_check` | |
| 6 | `canary_wait_25pct` | `wait` | |
| … | … | … | |
| N-1 | `canary_promote` | `ssh_cmd` | Rename canary → main |
| N | `canary_retire_old` | `ssh_cmd` | Remove old main |

**Configuration:**

```yaml
pattern: canary
pattern_config:
  canary_suffix: "-canary"     # appended to remote_dir / app
  stages: [10, 25, 50, 100]   # percentages (informational — no real traffic split)
  stage_wait_seconds: 60       # 0 = skip wait steps entirely
```

**Python:**

```python
from redeploy.patterns import CanaryPattern

p = CanaryPattern(
    app="myapp",
    remote_dir="~/myapp",
    verify_url="https://myapp.example.com/health",
    stages=[10, 50, 100],
    stage_wait_seconds=30,
    canary_suffix="-canary",
)
steps = p.expand()
```

> **Note:** The traffic-split percentages in stage names are informational.
> Actual traffic distribution depends on your proxy/load-balancer configuration.
> The pattern manages directory promotion, not proxy weights.

---

### `rollback_on_failure` — Auto-rollback on step failure

Snapshots current image tags before deploying.  Each step that can fail carries
a `rollback_command` that the `Executor` runs automatically on failure.

**Steps:**

| # | ID | Action | Rollback |
|---|---|---|---|
| 1 | `rob_snapshot` | `ssh_cmd` | — |
| 2 | `rob_deploy` | `docker_build` | restore previous image tag |
| 3 | `rob_health` | `http_check` | — |
| 4 | `rob_cleanup_snapshot` | `ssh_cmd` | — |

**Configuration:**

```yaml
pattern: rollback_on_failure
pattern_config:
  snapshot_file: .deploy-snapshot   # stored in remote_dir
```

**Python:**

```python
from redeploy.patterns import RollbackOnFailurePattern

p = RollbackOnFailurePattern(
    app="myapp",
    remote_dir="~/myapp",
    verify_url="https://myapp.example.com/health",
    snapshot_file=".deploy-snapshot",
)
steps = p.expand()
```

---

## Pattern lookup API

```python
from redeploy.patterns import get_pattern, list_patterns, pattern_registry

# All registered names
list_patterns()
# → ['blue_green', 'canary', 'rollback_on_failure']

# Get class by name (returns None for unknown)
cls = get_pattern("blue_green")     # BlueGreenPattern
cls = get_pattern("nonexistent")    # None

# Full registry dict
print(pattern_registry)
# → {'blue_green': BlueGreenPattern, 'canary': CanaryPattern, ...}
```

---

## Writing a custom pattern

```python
from redeploy.patterns import DeployPattern
from redeploy.models import MigrationStep, StepAction, ConflictSeverity

class MyCustomPattern(DeployPattern):
    name = "my_custom"
    description = "Custom deploy with manual approval gate"

    def __init__(self, app: str, remote_dir: str, approver_url: str = ""):
        self.app = app
        self.remote_dir = remote_dir
        self.approver_url = approver_url

    def expand(self) -> list[MigrationStep]:
        return [
            MigrationStep(
                id="pre_deploy_backup",
                action=StepAction.SSH_CMD,
                description="Backup current state",
                command=f"cp -r {self.remote_dir} {self.remote_dir}.bak",
                risk=ConflictSeverity.LOW,
                rollback_command=f"rm -rf {self.remote_dir}.bak || true",
            ),
            MigrationStep(
                id="deploy_new",
                action=StepAction.DOCKER_BUILD,
                description=f"Deploy new version of {self.app}",
                command=f"cd {self.remote_dir} && docker compose up -d --build",
                timeout=1800,
                risk=ConflictSeverity.MEDIUM,
            ),
        ]

# Register globally
from redeploy.patterns import pattern_registry
pattern_registry["my_custom"] = MyCustomPattern
```

After registration, `pattern: my_custom` in YAML and `redeploy patterns my_custom`
in CLI both work automatically.

---

## How patterns integrate with `Planner`

When `TargetConfig.pattern` is set, `Planner._plan_pattern()` runs instead of
`_plan_deploy_new()`:

1. Looks up class via `get_pattern(target.pattern)`
2. Merges `pattern_config` with defaults derived from `TargetConfig` fields
3. Instantiates the pattern and calls `expand()`
4. Appends all returned steps via `_add_step()`
5. Appends note `"Deploy pattern: <name>"` to `MigrationPlan.notes`

Unknown pattern name → falls back to standard deploy + warning note.

```python
from redeploy import Planner, TargetConfig
from redeploy.models import InfraState, RuntimeInfo, DeployStrategy

state = InfraState(
    host="root@10.0.0.1", app="myapp",
    runtime=RuntimeInfo(docker="24.0"),
    detected_strategy=DeployStrategy.DOCKER_FULL,
)
target = TargetConfig(
    strategy="docker_full",
    app="myapp",
    remote_dir="~/myapp",
    verify_url="https://myapp.example.com/health",
    pattern="blue_green",
    pattern_config={"traefik_network": "proxy"},
)
plan = Planner(state, target).run()
# plan.steps contains bg_clone_green, bg_deploy_green, …
# plan.notes contains "Deploy pattern: blue_green"
```

---

## Examples

See `examples/` for complete YAML files:

- `examples/14-blue-green.yaml` — full blue/green deploy spec
- `examples/15-canary.yaml` — canary with 4 stages
- `examples/16-auto-rollback.yaml` — rollback-on-failure pattern

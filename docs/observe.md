# redeploy Observability — Audit Log & Deploy Reports

`redeploy.observe` — structured deploy history, per-deployment step reports, and
CI-friendly YAML output.  Automatically integrated into `Executor`.

---

## Quick start

```python
from redeploy.observe import DeployAuditLog, DeployReport

# Read last 10 deployments
log = DeployAuditLog()
for entry in log.tail(10):
    print(DeployReport(entry).summary_line())

# Full report for most recent deploy
entry = log.tail(1)[0]
print(DeployReport(entry).text())
```

CLI equivalent:

```bash
redeploy audit                        # last 20 entries, table view
redeploy audit --last 50 --failed     # only failures
redeploy audit --app myapp --host prod
redeploy audit --report 1             # full DeployReport for entry #1
redeploy audit --json | jq .ok        # raw JSONL
redeploy audit --clear                # truncate (with confirmation)
```

---

## How it works

`Executor.run()` automatically writes an audit entry after every deployment
(success or failure), unless `audit_log=False` is passed.  The entry is
appended to `~/.config/redeploy/audit.jsonl` in newline-delimited JSON format.

```python
from redeploy import Planner, Executor
from redeploy.observe import DeployAuditLog, DeployReport

plan = Planner(state, target).run()

# Default: audit_log=True writes to ~/.config/redeploy/audit.jsonl
executor = Executor(plan, dry_run=True)
ok = executor.run()

# Or with custom path:
executor = Executor(plan, audit_path=Path("/var/log/redeploy/audit.jsonl"))
ok = executor.run()

# Or opt out entirely:
executor = Executor(plan, audit_log=False)
```

---

## `AuditEntry`

Immutable snapshot of one deployment, loaded from the JSONL file.

```python
from redeploy.observe import AuditEntry

entry = AuditEntry({
    "ts": "2026-04-20T14:30:00+00:00",
    "host": "root@10.0.0.1",
    "app": "myapp",
    "from_strategy": "k3s",
    "to_strategy": "docker_full",
    "ok": True,
    "dry_run": False,
    "elapsed_s": 42.3,
    "steps_total": 7,
    "steps_ok": 7,
    "steps_failed": 0,
    "pattern": "blue_green",
    "steps": [...],
})
```

### Properties

| Property | Type | Description |
|---|---|---|
| `ts` | `str` | ISO-8601 UTC timestamp |
| `host` | `str` | SSH host or `local` |
| `app` | `str` | Application name |
| `from_strategy` | `str` | Strategy before migration |
| `to_strategy` | `str` | Strategy after migration |
| `ok` | `bool` | `True` if all steps succeeded |
| `dry_run` | `bool` | `True` if `--dry-run` was used |
| `elapsed_s` | `float` | Total wall-clock time in seconds |
| `steps_total` | `int` | Number of steps in plan |
| `steps_ok` | `int` | Steps that completed successfully |
| `steps_failed` | `int` | Steps that failed (0 on success) |
| `pattern` | `str \| None` | Deploy pattern used, if any |
| `error` | `str \| None` | First failure message |
| `steps` | `list[dict]` | Per-step snapshot: id, action, status, result, error |

---

## `DeployAuditLog`

Persistent JSONL audit log.  Default path: `~/.config/redeploy/audit.jsonl`.

```python
from pathlib import Path
from redeploy.observe import DeployAuditLog

# Default path
log = DeployAuditLog()

# Custom path (e.g. project-local)
log = DeployAuditLog(path=Path("./deploy-audit.jsonl"))
```

### Methods

#### `record(plan, completed_steps, *, ok, elapsed_s, dry_run) → AuditEntry`

Build and persist an entry from a finished plan execution.  Called automatically
by `Executor` — you only need this if you build a custom executor.

```python
entry = log.record(plan, executor.completed_steps, ok=True, elapsed_s=18.5)
```

#### `load(limit=100) → list[AuditEntry]`

Return up to `limit` most-recent entries (oldest first).

```python
all_entries = log.load(limit=500)
```

#### `tail(n=10) → list[AuditEntry]`

Shorthand for the `n` most-recent entries.

```python
recent = log.tail(5)
```

#### `filter(host, app, ok, since) → list[AuditEntry]`

Filter entries.  All parameters are optional.

```python
from datetime import datetime, timezone

# Failed deploys on production host in the last 7 days
import datetime as dt
week_ago = datetime.now(timezone.utc) - dt.timedelta(days=7)
failures = log.filter(host="prod", ok=False, since=week_ago)
```

| Parameter | Type | Description |
|---|---|---|
| `host` | `str \| None` | Substring match on `entry.host` |
| `app` | `str \| None` | Exact match on `entry.app` |
| `ok` | `bool \| None` | `True` = only successes, `False` = only failures |
| `since` | `datetime \| None` | Entries at or after this timestamp |

#### `clear()`

Truncate the log file (irreversible).

---

## `DeployReport`

Human-readable or machine-readable report from an `AuditEntry`.

```python
from redeploy.observe import DeployReport

report = DeployReport(entry)

# Boxed text table (for terminal / CI logs)
print(report.text())

# YAML (for CI artifact storage / parsing)
with open("deploy-report.yaml", "w") as f:
    f.write(report.yaml())

# Single line (for commit messages, Slack notifications)
print(report.summary_line())
# → [ok] myapp @ root@10.0.0.1: k3s→docker_full 7/7 steps in 42.3s
```

### `text()` output example

```
┌─ Deploy report ──────────────────────────────
│  host     : root@10.0.0.1
│  app      : myapp
│  strategy : k3s → docker_full
│  pattern  : blue_green
│  result   : SUCCESS
│  steps    : 7/7 ok
│  elapsed  : 42.3s
│  at       : 2026-04-20T14:30:00+00:00
├─ Steps ─────────────────────────────────────────
│  ✓ bg_clone_green               ssh_cmd
│  ✓ bg_deploy_green              docker_build
│  ✓ bg_health_green              http_check
│  ✓ bg_swap_labels               ssh_cmd
│  ✓ bg_verify_main               http_check
│  ✓ bg_retire_blue               docker_compose_down
│  ✓ http_health_check            http_check
└─────────────────────────────────────────────────
```

Step status icons:

| Icon | Meaning |
|---|---|
| `✓` | done |
| `✗` | failed |
| `⤼` | skipped |
| `▶` | running |
| `·` | pending |

---

## JSONL format

Each line in `audit.jsonl` is a self-contained JSON object:

```json
{
  "ts": "2026-04-20T14:30:00+00:00",
  "host": "root@10.0.0.1",
  "app": "myapp",
  "from_strategy": "k3s",
  "to_strategy": "docker_full",
  "ok": true,
  "dry_run": false,
  "elapsed_s": 42.3,
  "steps_total": 7,
  "steps_ok": 7,
  "steps_failed": 0,
  "pattern": "blue_green",
  "steps": [
    {"id": "bg_clone_green", "action": "ssh_cmd", "status": "done", "result": null, "error": null},
    {"id": "bg_deploy_green", "action": "docker_build", "status": "done", "result": null, "error": null}
  ]
}
```

The file is append-only and safe to `tail -f` or parse with `jq`:

```bash
# Last 5 deployments (jq)
tail -n 5 ~/.config/redeploy/audit.jsonl | jq '{app, ok, elapsed_s}'

# All failures
cat ~/.config/redeploy/audit.jsonl | jq 'select(.ok == false)'

# Average deploy time for myapp
cat ~/.config/redeploy/audit.jsonl \
  | jq 'select(.app == "myapp") | .elapsed_s' \
  | awk '{sum+=$1; n++} END {print sum/n "s avg"}'
```

---

## Integration with CI/CD

```yaml
# .github/workflows/deploy.yml (excerpt)
- name: Deploy
  run: redeploy run --env prod

- name: Show deploy report
  if: always()
  run: redeploy audit --report 1

- name: Upload audit artifact
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: deploy-audit
    path: ~/.config/redeploy/audit.jsonl
```

---

## `Executor` parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `audit_log` | `bool` | `True` | Enable automatic audit entry after `run()` |
| `audit_path` | `Path \| None` | `None` | Override default `~/.config/redeploy/audit.jsonl` |

`completed_steps` property returns the list of successfully executed steps —
useful for building `AuditEntry` manually or for post-deploy inspection.

# Markpact v3: State Reconciliation Example

This example demonstrates **true idempotency** using `check_cmd` (v3 feature).

Unlike v2 (which only tracked execution history), v3 checks **current state** on the target host.

## Configuration

```markpact:config yaml
name: "v3-state-reconciliation-demo"
version: "3.0.0"
target:
  host: pi@192.168.188.108
```

## Steps with check_cmd (True Idempotency)

```markpact:steps yaml
extra_steps:
  # This step will ONLY execute if docker is NOT installed
  - id: install_docker
    action: ssh_cmd
    description: "Install Docker (only if not present)"
    host: pi@192.168.188.108
    command: "curl -fsSL https://get.docker.com | sh"
    check_cmd: "docker_installed"  # Skip if docker is already installed
    risk: medium
    timeout: 120
    retry: 2

  # This step will ONLY execute if the c2004 container is NOT running
  - id: deploy_c2004
    action: ssh_cmd
    description: "Deploy c2004 (only if not running)"
    host: pi@192.168.188.108
    command: "cd ~/c2004 && docker compose up -d"
    check_cmd: "docker_running:c2004"  # Skip if container already running
    risk: low
    timeout: 300
    rollback_cmd: "cd ~/c2004 && docker compose down"

  # This step will ONLY execute if the directory does NOT exist
  - id: create_data_dir
    action: ssh_cmd
    description: "Create data directory (only if missing)"
    host: pi@192.168.188.108
    command: "mkdir -p ~/c2004/data && chmod 755 ~/c2004/data"
    check_cmd: "dir_exists:~/c2004/data"  # Skip if directory exists
    risk: low
    timeout: 30

  # This step will ONLY execute if the file does NOT exist
  - id: copy_env_file
    action: scp
    description: "Copy .env file (only if missing)"
    src: ./.env.example
    dst: pi@192.168.188.108:~/c2004/.env
    check_cmd: "file_exists:~/c2004/.env"  # Skip if file exists
    risk: low
    timeout: 30
```

## How check_cmd Works

| check_cmd | Meaning | When Step Executes |
|-----------|---------|-------------------|
| `docker_installed` | Check if docker command exists | Only if docker NOT installed |
| `docker_running:c2004` | Check if container 'c2004' is running | Only if container NOT running |
| `file_exists:/path` | Check if file exists | Only if file does NOT exist |
| `dir_exists:/path` | Check if directory exists | Only if directory does NOT exist |
| `command_succeeds:"cmd"` | Check if command returns exit 0 | Only if command FAILS |

## Usage

```bash
# Plan mode: Preview what would change (Terraform-style)
python -m markpact.runtime.cli migration.md --plan

# Example output:
# [PLAN] Processing 4 steps...
#   [1/4] SKIP install_docker: check passed: docker_installed
#   [2/4] PLAN deploy_c2004: would ssh_cmd (check failed: docker_running:c2004)
#   [3/4] SKIP create_data_dir: check passed: dir_exists:~/c2004/data
#   [4/4] SKIP copy_env_file: check passed: file_exists:~/c2004/.env
#
# [PLAN SUMMARY]
#   Total steps: 4
#   Would execute: 1
#   Would skip: 3

# Apply changes (reconcile)
python -m markpact.runtime.cli migration.md

# Check current state on target
python -m markpact.runtime.cli migration.md --check-state

# Reset and start fresh
python -m markpact.runtime.cli migration.md --reset-state
```

## v3 vs v2 Idempotency

| Feature | v2 (History-based) | v3 (State-based) |
|---------|-------------------|------------------|
| Tracks | Steps executed | Current state on host |
| Skip if | `step.id in steps_done` | `check_cmd` returns true |
| Detects changes | ❌ No | ✅ Yes (step hash) |
| Re-runs if | Manual reset | Step definition changes |
| Mindset | Execute steps | Reconcile state |

## Change Detection (Step Hashing)

v3 also tracks step definition hashes. If you modify a step:

```yaml
# Original
- id: deploy
  command: "docker compose up"

# Modified
- id: deploy
  command: "docker compose up -d"  # Added -d flag
```

v3 will detect the hash change and **re-execute** the step even if it was previously completed:

```
[RECONCILE] deploy → definition changed (hash: a1b2c3d4 → e5f6g7h8)
```

This is **true idempotency** - combining:
1. Current state checks (`check_cmd`)
2. Definition change detection (step hashing)
3. Execution history (for steps without `check_cmd`)

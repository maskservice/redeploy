# Complete Action Types Example

> Status: prototype only. This file intentionally shows aspirational fields and
> actions for a future markdown runtime; it does not match the current
> `redeploy` execution model one-to-one.

This example demonstrates ALL action types available in markpact runtime,
similar to what was available in YAML format.

## Configuration

```markpact:config yaml
name: "all-actions-demo"
version: "1.0.0"
target:
  host: pi@192.168.188.108
plugins:
  - path: ./plugins
```

## 1. SSH Command (ssh_cmd)

Execute commands on remote hosts via SSH.

```markpact:steps yaml
extra_steps:
  - id: check_host
    action: ssh_cmd
    description: "Check remote host availability"
    host: pi@192.168.188.108
    command: "uptime && uname -a"
    risk: low
    timeout: 30

  - id: install_deps
    action: ssh_cmd
    description: "Install dependencies if needed"
    host: pi@192.168.188.108
    command: "apt-get update && apt-get install -y docker.io"
    when: "docker_not_running"  # Only if docker not installed
    risk: medium
    timeout: 120
    retry: 2
```

## 2. Rsync (rsync)

Synchronize files with remote host.

```markpact:steps yaml
extra_steps:
  - id: deploy_code
    action: rsync
    description: "Deploy application code"
    src: ./app/
    dst: pi@192.168.188.108:~/app/
    excludes:
      - .git
      - node_modules
      - __pycache__
      - "*.pyc"
      - .env.local
    delete: false  # Keep extra files on destination
    risk: low
    timeout: 300
    retry: 2
```

## 3. SCP (scp)

Copy single files via SCP.

```markpact:steps yaml
extra_steps:
  - id: copy_env
    action: scp
    description: "Copy environment file"
    src: ./.env.production
    dst: pi@192.168.188.108:~/app/.env
    risk: low
    timeout: 30

  - id: copy_ssl_cert
    action: scp
    description: "Copy SSL certificate"
    src: ./ssl/cert.pem
    dst: pi@192.168.188.108:~/app/ssl/
    risk: medium
    timeout: 30
```

## 4. Docker (docker)

Docker Compose operations.

```markpact:steps yaml
extra_steps:
  - id: docker_build
    action: docker
    description: "Build and start containers"
    docker_action: compose_up
    host: pi@192.168.188.108
    project_dir: ~/app
    files:
      - docker-compose.yml
    env_file: .env
    build: true
    wait_healthy: false
    rollback_cmd: "cd ~/app && docker compose down"
    risk: low
    timeout: 600
    retry: 1

  - id: wait_containers
    action: docker
    description: "Wait for healthy containers"
    docker_action: wait_healthy
    host: pi@192.168.188.108
    project: app
    risk: low
    timeout: 120
```

## 5. HTTP (http)

HTTP health checks.

```markpact:steps yaml
extra_steps:
  - id: check_api
    action: http
    description: "Verify API health"
    url: http://192.168.188.108:8080/api/health
    expect: "healthy"
    retries: 5
    risk: low
    timeout: 60

  - id: check_frontend
    action: http
    description: "Verify frontend accessible"
    url: http://192.168.188.108:80/
    expect: "<!DOCTYPE html>"
    retries: 3
    risk: low
    timeout: 30
```

## 6. Shell (shell)

Local shell commands.

```markpact:steps yaml
extra_steps:
  - id: local_prep
    action: shell
    description: "Local preparation"
    command: |
      echo "Preparing deployment..."
      ./scripts/validate-config.sh
      echo "Config valid"
    risk: low
    timeout: 60

  - id: generate_report
    action: shell
    description: "Generate deployment report"
    command: |
      echo "# Deployment Report" > report.md
      echo "Date: $(date)" >> report.md
      echo "Status: SUCCESS" >> report.md
    skip_if: "file_exists:./report.md"
    risk: low
    timeout: 30
```

## 7. Plugin (plugin)

Custom plugin actions.

```markpact:steps yaml
extra_steps:
  - id: reload_browser
    action: plugin
    description: "Reload kiosk browser"
    plugin_type: browser_reload
    host: 192.168.188.108
    port: 9222
    ignore_cache: true
    risk: low
    timeout: 30

  - id: send_notification
    action: plugin
    description: "Send deployment notification"
    plugin_type: slack_notify
    channel: "#deployments"
    message: "Deployment completed successfully"
    risk: low
    timeout: 10
```

## Idempotency Examples

Steps that won't re-run if already completed:

```markpact:steps yaml
extra_steps:
  - id: setup_db
    action: ssh_cmd
    description: "Initialize database (run once)"
    host: pi@192.168.188.108
    command: "cd ~/app && docker compose exec db psql -c 'CREATE DATABASE app;'"
    when: "dir_not_exists:~/app/db_data"
    risk: high
    timeout: 60

  - id: seed_data
    action: ssh_cmd
    description: "Seed initial data"
    host: pi@192.168.188.108
    command: "cd ~/app && docker compose exec app python seed.py"
    skip_if: "step_completed:seed_data"
    risk: medium
    timeout: 120
```

## Rollback Plan

Rollback steps executed in reverse order on failure:

```markpact:rollback yaml
steps:
  - id: stop_containers
    action: ssh_cmd
    host: pi@192.168.188.108
    command: "cd ~/app && docker compose down"
    
  - id: notify_failure
    action: plugin
    plugin_type: slack_notify
    channel: "#alerts"
    message: "Deployment failed! Containers stopped."
```

## Python Extension Block

Optional Python for complex logic:

```markpact:python
import urllib.request
import json

def verify_all_services():
    services = [
        "http://192.168.188.108:8080/api/health",
        "http://192.168.188.108:3000/health",
    ]
    
    all_healthy = True
    for url in services:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read())
                status = data.get("status", "unknown")
                print(f"✓ {url}: {status}")
                if status != "healthy":
                    all_healthy = False
        except Exception as e:
            print(f"✗ {url}: {e}")
            all_healthy = False
    
    return all_healthy

if not verify_all_services():
    print("Some services not healthy!")
    exit(1)

print("All services verified!")
```

## Final Verification

```markpact:run
#!/bin/bash
# Final sanity checks
echo "=== Deployment Verification ==="
curl -sf http://192.168.188.108:8080/api/health && echo "✓ API healthy" || exit 1
curl -sf http://192.168.188.108:80/ && echo "✓ Frontend accessible" || exit 1
ssh pi@192.168.188.108 "docker compose ps" && echo "✓ Containers running" || exit 1
echo "=== All Checks Passed ==="
```

## Usage

```bash
# Dry run (show what would be done)
python -m markpact.runtime.cli migration.md --dry-run

# Execute with retries
python -m markpact.runtime.cli migration.md --retry 2

# Show which steps are already done
python -m markpact.runtime.cli migration.md --list-steps

# Reset and fresh start
python -m markpact.runtime.cli migration.md --reset-state

# Resume after failure (skips completed steps)
python -m markpact.runtime.cli migration.md
```

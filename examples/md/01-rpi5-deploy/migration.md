# c2004 RPi5 Deployment 1.0.22

> Status: prototype only. This markdown file documents a proposed markpact-style
> runtime. It uses features outside the currently supported `redeploy`
> markdown subset.

Markpact deployment specification for deploying c2004 to Raspberry Pi 5.

This example demonstrates the markpact format with embedded YAML configuration,
imperative steps, and final verification.

## Configuration

```markpact:config yaml
name: "c2004 rpi5 docker_full deploy"
version: "1.0.22"
target:
  host: pi@192.168.188.108
  strategy: docker_full
  remote_dir: ~/c2004
```

## Pre-deployment Steps

Optional: Uncomment to restart RPi5 before deployment for a clean state.

```markpact:steps yaml
extra_steps:
  - id: restart_rpi5
    action: ssh_cmd
    description: "Restart RPi5 to ensure clean state"
    command: "sudo shutdown -r now"
    risk: high
    timeout: 120
```

## Main Deployment Steps

This section demonstrates various action types supported by markpact runtime:

### 1. SSH Command (`ssh_cmd`)

```markpact:steps yaml
extra_steps:
  - id: install_docker
    action: ssh_cmd
    description: "Install Docker if not present on RPi (ARM64)"
    command: |
      if ! command -v docker >/dev/null 2>&1; then
        curl -fsSL https://get.docker.com | sh &&
        sudo usermod -aG docker pi &&
        sudo systemctl enable docker &&
        sudo systemctl start docker &&
        echo docker-installed;
      else
        docker --version && echo docker-ok;
      fi
    when: "docker_not_running"  # Idempotent condition
    risk: medium
    timeout: 120

  - id: create_directories
    action: ssh_cmd
    description: "Ensure data/db directories exist on RPi"
    command: "mkdir -p ~/c2004/db/main ~/c2004/db/menu ~/c2004/db/config ~/c2004/logs && echo dirs-ok"
    skip_if: "dir_exists:~/c2004/db"  # Skip if already exists
    risk: low
    timeout: 30

  - id: arm_platform_check
    action: ssh_cmd
    description: "Verify ARM64 platform (RPi5) is supported"
    command: "uname -m && docker info --format '{{.Architecture}}' 2>/dev/null && echo platform-ok"
    risk: low
    timeout: 30
```

### 2. Rsync (`rsync`)

```markpact:steps yaml
extra_steps:
  - id: rsync_code
    action: rsync
    description: "Rsync c2004 source code to RPi5"
    src: /home/tom/github/maskservice/c2004/
    dst: pi@192.168.188.108:~/c2004/
    excludes:
      - .git
      - .venv
      - node_modules
      - __pycache__
      - "*.pyc"
      - "*.egg-info"
      - .pytest_cache
      - dist
      - screenshots
      - playwright-report
      - db
      - logs
    delete: false  # Don't delete extra files on destination
    risk: low
    timeout: 300
    retry: 2  # Retry on network timeout
```

### 3. SCP (`scp`)

```markpact:steps yaml
extra_steps:
  - id: sync_env
    action: scp
    description: "Copy environment file to remote"
    src: /home/tom/github/maskservice/c2004/.env
    dst: pi@192.168.188.108:~/c2004/.env
    risk: low
    timeout: 30
```

### 4. Docker Compose (`docker`)

```markpact:steps yaml
extra_steps:
  - id: docker_build
    action: docker
    description: "Build and deploy Docker images on remote"
    docker_action: compose_up
    host: pi@192.168.188.108
    project_dir: ~/c2004
    files:
      - docker-compose.yml
    env_file: .env
    build: true
    wait_healthy: false  # We'll check health separately
    rollback_cmd: "cd ~/c2004 && docker compose down"  # Rollback on failure
    risk: low
    timeout: 600
    retry: 1  # Retry once on build failure

  - id: wait_healthy
    action: docker
    description: "Wait until all containers are healthy/running"
    docker_action: wait_healthy
    host: pi@192.168.188.108
    project: c2004
    risk: low
    timeout: 120

  - id: container_logs
    action: shell
    description: "Tail container logs after startup"
    host: pi@192.168.188.108
    command: "cd ~/c2004 && docker compose logs --tail=20"
    risk: low
    timeout: 30
```

### 5. HTTP Health Check (`http`)

```markpact:steps yaml
extra_steps:
  - id: http_health_check
    action: http
    description: "Verify backend health endpoint"
    url: http://192.168.188.108:8101/api/v3/health
    expect: healthy
    retries: 5
    risk: low
    timeout: 60
```

### 6. Plugin (`plugin`)

```markpact:steps yaml
extra_steps:
  - id: browser_reload
    action: plugin
    description: "Reload kiosk browser (Chromium CDP) after deploy"
    plugin_type: browser_reload
    host: 192.168.188.108
    port: 9222
    ignore_cache: true
    risk: low
    timeout: 30
```

### 7. Shell Command (`shell`)

```markpact:steps yaml
extra_steps:
  - id: version_check
    action: shell
    description: "Verify deployed version matches manifest"
    host: pi@192.168.188.108
    command: "cat ~/c2004/VERSION"
    risk: low
    timeout: 30
```

## Python Extension (Optional)

You can also include Python code blocks for complex logic:

```markpact:python
# Custom verification logic
def verify_deployment():
    import urllib.request
    import json
    
    url = "http://192.168.188.108:8101/api/v3/health"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read())
            assert data["status"] == "healthy"
            print(f"✓ Health check passed: {data}")
            return True
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return False

verify_deployment()
```

## Final Verification

```markpact:run
#!/bin/bash
# Final sanity checks
echo "=== Deployment Verification ==="
curl -sf http://192.168.188.108:8101/api/v3/health && echo "✓ Backend healthy" || echo "✗ Backend not responding"
curl -sf http://192.168.188.108:8100/ && echo "✓ Frontend accessible" || echo "✗ Frontend not responding"
echo "=== Deployment Complete ==="
```

## Notes

- RPi5 (8GB): pi@192.168.188.108, deploy dir ~/c2004 — ARM64 (aarch64)
- Docker will be installed if not present
- Build on RPi5 can take 5-10 minutes for ARM64 images
- Kiosk browser will be reloaded via CDP if running

## Run this migration

```bash
# Via markpact runtime (standalone)
python -m markpact.runtime.cli examples/md/01-rpi5-deploy/migration.md

# Dry run
python -m markpact.runtime.cli examples/md/01-rpi5-deploy/migration.md --dry-run

# List steps
python -m markpact.runtime.cli examples/md/01-rpi5-deploy/migration.md --list-steps

# Via redeploy (when integrated)
redeploy run examples/md/01-rpi5-deploy/migration.md --detect
```

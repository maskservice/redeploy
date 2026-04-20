# Python-native DSL for redeploy

## Overview

The Python-native DSL provides an alternative to YAML migration specs, offering:

- **Full Python power** — loops, conditionals, variables, imports
- **Type hints & IDE support** — autocomplete, error detection, refactoring
- **Testability** — unit test migrations with pytest
- **Debuggability** — breakpoints, stack traces, profiling
- **Composability** — reusable step definitions via imports

## Quick Start

### 1. Create `migration.py`

```python
from redeploy.dsl_python import migration, step, ssh, rsync, docker, http_expect

RPI5_HOST = "pi@192.168.188.108"
PROJECT_DIR = "~/c2004"

@migration(
    name="c2004 rpi5 deploy",
    version="1.0.22",
    description="Deploy to Raspberry Pi 5"
)
def deploy():
    with step("rsync_code", risk="low", timeout=300):
        rsync(
            src="/home/tom/c2004/",
            dst=f"{RPI5_HOST}:{PROJECT_DIR}/",
            exclude=[".git", ".venv", "__pycache__"]
        )

    with step("docker_deploy", risk="low", timeout=600):
        docker.compose_up(
            host=RPI5_HOST,
            project_dir=PROJECT_DIR,
            files=["docker-compose.yml"],
            build=True,
            wait_healthy=True
        )

    with step("verify", risk="low"):
        http_expect(
            "http://192.168.188.108:8101/api/v3/health",
            expect="healthy"
        )
```

### 2. Run the migration

```bash
# Direct execution
python migration.py

# Via redeploy CLI (when supported)
redeploy run migration.py

# With dry-run
redeploy run migration.py --dry-run
```

## Core Concepts

### @migration Decorator

Marks a function as a migration and provides metadata:

```python
@migration(
    name="my-deployment",        # Required: migration name
    version="1.0.0",             # Required: version being deployed
    description="Human-readable", # Optional: description
    author="Your Name"           # Optional: author
)
def my_migration():
    ...
```

### step Context Manager

Defines a single deployment step with risk level and timeout:

```python
with step("step_name", risk="low", timeout=300, retries=0):
    # Step implementation
    pass
```

**Risk levels:** `low`, `medium`, `high`

**Timeouts:** Fail step if it exceeds specified seconds

### Available Actions

#### SSH Commands

```python
# Execute command on remote host
output = ssh("user@host", "ls -la", timeout=60)

# Wait for SSH availability
ssh_available("user@host", timeout=120)
```

#### File Operations

```python
# Rsync with exclusions
rsync(
    src="/local/path/",
    dst="user@host:/remote/path/",
    exclude=[".git", "node_modules"],
    delete=False
)

# SCP single file
scp("local.env", "user@host:/remote/.env")
```

#### Docker Operations

```python
# Docker Compose up
docker.compose_up(
    host="user@host",           # Optional (local if None)
    project_dir="~/myapp",
    files=["docker-compose.yml"],
    env_file=".env",
    build=True,
    wait_healthy=True,
    timeout=600
)

# Docker Compose down
docker.compose_down(host="user@host", project_dir="~/myapp")

# Wait for healthy containers
docker.wait_healthy(host="user@host", project="myapp", timeout=120)

# Get logs
docker.logs(host="user@host", project_dir="~/myapp", tail=50)
```

#### Verification

```python
# HTTP health check
http_expect(
    url="http://host/api/health",
    expect="healthy",
    timeout=30,
    retries=3
)

# Version verification
version_check(
    manifest_path=".redeploy/version.yaml",
    expect="@manifest",  # Read from manifest
    host="user@host"
)
```

#### Utilities

```python
# Wait
wait(90, "Waiting for restart...")
```

## Advanced Usage

### Conditional Logic

```python
@migration(name="conditional-deploy", version="1.0.0")
def deploy():
    # Check if restart needed
    uptime = ssh(RPI5_HOST, "awk '{print $1}' /proc/uptime | cut -d. -f1")
    if int(uptime) > 86400:  # Uptime > 24h
        with step("restart", risk="high"):
            ssh(RPI5_HOST, "sudo shutdown -r now")
            wait(90)
            ssh_available(RPI5_HOST, timeout=120)

    # Check platform and adapt
    arch = ssh(RPI5_HOST, "uname -m")
    if "aarch64" in arch:
        build_flags = "--platform linux/arm64"
    else:
        build_flags = ""

    with step("build", risk="low"):
        ssh(RPI5_HOST, f"docker build {build_flags} .")
```

### Loops & Iteration

```python
@migration(name="multi-host", version="1.0.0")
def deploy():
    hosts = [
        "pi@192.168.188.108",
        "pi@192.168.188.109",
        "pi@192.168.188.110",
    ]

    for host in hosts:
        with step(f"deploy_{host}", risk="medium"):
            rsync(src="./", dst=f"{host}:~/app/")
            docker.compose_up(host=host, project_dir="~/app")
```

### Reusable Step Functions

```python
# shared_steps.py
from redeploy.dsl_python import step, ssh, docker

def restart_service(host: str, service: str) -> None:
    """Restart a systemd service on remote host."""
    with step(f"restart_{service}", risk="medium"):
        ssh(host, f"sudo systemctl restart {service}")
        # Verify
        status = ssh(host, f"sudo systemctl is-active {service}")
        if status != "active":
            raise RuntimeError(f"Service {service} failed to start")

def deploy_docker_compose(host: str, project: str) -> None:
    """Standard Docker Compose deployment."""
    with step("docker_deploy", risk="low", timeout=300):
        docker.compose_up(
            host=host,
            project_dir=f"~/{project}",
            files=["docker-compose.yml"],
            build=True,
            wait_healthy=True
        )
```

```python
# migration.py
from redeploy.dsl_python import migration, step
from shared_steps import restart_service, deploy_docker_compose

@migration(name="my-app", version="1.0.0")
def deploy():
    restart_service("pi@192.168.188.108", "nginx")
    deploy_docker_compose("pi@192.168.188.108", "myapp")
```

### Error Handling & Retries

```python
from redeploy.dsl_python.exceptions import StepError, TimeoutError

@migration(name="resilient-deploy", version="1.0.0")
def deploy():
    for attempt in range(3):
        try:
            with step("deploy", risk="medium", timeout=300):
                docker.compose_up(host=RPI5_HOST, ...)
                break  # Success
        except TimeoutError:
            print(f"Attempt {attempt + 1} timed out, retrying...")
            if attempt == 2:
                raise  # Final failure
        except StepError as e:
            print(f"Step failed: {e}")
            raise
```

## Testing Migrations

### Unit Testing

```python
# test_migration.py
import pytest
from unittest.mock import patch, MagicMock
from migration import deploy

def test_deployment(mocker):
    # Mock all external calls
    with patch("migration.ssh") as mock_ssh, \
         patch("migration.rsync") as mock_rsync, \
         patch("migration.docker") as mock_docker:

        # Configure mocks
        mock_ssh.return_value = "success"
        mock_docker.compose_up.return_value = MagicMock(success=True)

        # Run migration
        deploy()

        # Verify calls
        mock_ssh.assert_called()
        mock_rsync.assert_called_once()
        mock_docker.compose_up.assert_called_once()
```

### Integration Testing

```python
# test_integration.py
import pytest
from migration import deploy, RPI5_HOST

def test_real_deployment():
    """Requires actual RPi5."""
    # Pre-check
    assert ssh_available(RPI5_HOST, timeout=10)

    # Run deployment
    deploy()

    # Post-check
    result = ssh(RPI5_HOST, "docker compose ps")
    assert "healthy" in result or "running" in result
```

## Comparison with YAML

| Feature | YAML | Python DSL |
|---------|------|------------|
| Shell commands | Strings | Type-checked functions |
| Conditionals | N/A | Full if/else |
| Loops | N/A | for/while/ comprehensions |
| Variables | YAML anchors | Python variables |
| Functions | N/A | def/import |
| Testing | Manual | pytest |
| Debugging | Print | Breakpoints, stack traces |
| IDE support | Schema validation | Full autocomplete |
| Composability | YAML includes | Python imports |

## Migration from YAML

### Before (YAML)

```yaml
extra_steps:
  - id: restart_rpi5
    action: ssh_cmd
    description: "Schedule RPi5 restart"
    insert_before: install_docker
    command: >-
      echo "Restarting..." &&
      (sleep 5 && sudo shutdown -r now) &
      echo "scheduled"
    risk: high
```

### After (Python DSL)

```python
with step("restart_rpi5", risk="high", timeout=180):
    ssh(RPI5_HOST, "sudo shutdown -r now")
    wait(90)
    ssh_available(RPI5_HOST, timeout=60)
```

## CLI Integration (Roadmap)

Future versions of redeploy will support:

```bash
# Run Python migration
redeploy run migration.py

# Dry-run
redeploy run migration.py --dry-run

# List available migrations
redeploy run --list migration.py

# Run specific migration
redeploy run migration.py::deploy

# Convert YAML to Python
redeploy convert migration.yaml --to python
```

## Best Practices

1. **Use constants** for hostnames, paths, versions
2. **Create shared modules** for reusable steps
3. **Add timeouts** to all network operations
4. **Handle exceptions** with try/except where needed
5. **Write tests** for complex migrations
6. **Use type hints** for better IDE support
7. **Document steps** with clear descriptions

## Examples

### Simple Single-Host Deployment

```python
from redeploy.dsl_python import *

HOST = "root@myserver.com"

@migration(name="simple-deploy", version="1.0.0")
def deploy():
    with step("upload", risk="low"):
        rsync("./app/", f"{HOST}:/var/www/app/")

    with step("restart", risk="medium"):
        ssh(HOST, "sudo systemctl restart myapp")
```

### Multi-Stage Deployment

```python
from redeploy.dsl_python import *

@migration(name="blue-green", version="2.0.0")
def deploy():
    # Blue deployment
    with step("deploy_blue", risk="low"):
        docker.compose_up(
            host="blue.example.com",
            project_dir="~/app",
            env_file=".env.blue"
        )

    # Verify blue
    with step("verify_blue", risk="medium"):
        http_expect("https://blue.example.com/health", "ok")

    # Switch traffic
    with step("switch_traffic", risk="high"):
        ssh("lb.example.com", "./switch-to-blue.sh")

    # Verify production
    with step("verify_prod", risk="medium"):
        http_expect("https://app.example.com/health", "ok")
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'redeploy'"

Add redeploy to Python path:

```python
import sys
sys.path.insert(0, "/home/tom/github/maskservice/redeploy")
```

Or install in editable mode:

```bash
cd /home/tom/github/maskservice/redeploy
pip install -e .
```

### SSH timeout

Increase timeout or check connectivity:

```python
ssh_available(RPI5_HOST, timeout=180)  # 3 minutes
```

### Docker build takes too long

Use longer timeout:

```python
with step("docker_build", risk="low", timeout=900):  # 15 minutes
    docker.compose_up(..., build=True)
```

## License

Same as redeploy project.

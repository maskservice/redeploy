# redeploy Examples — Markdown Format (markpact)

This directory contains examples using the **markpact** format — a universal
markdown-based deployment specification that supports multiple embedded
languages (YAML, TOML, JSON, Python, Bash).

## Structure

```
examples/md/
├── 01-rpi5-deploy/          # Raspberry Pi 5 deployment with markpact
│   └── migration.md
├── 02-multi-language/       # Multi-language example (YAML, TOML, JSON, Python)
│   └── migration.md
├── 03-all-actions/          # Complete demonstration of ALL action types
│   └── migration.md
└── README.md               # This file
```

### Examples Overview

| Example | Description | Action Types |
|---------|-------------|--------------|
| `01-rpi5-deploy` | Real-world c2004 deployment | ssh_cmd, rsync, scp, docker, http, plugin, shell |
| `02-multi-language` | YAML, TOML, JSON, Python, Bash | shell |
| `03-all-actions` | **Complete reference of all actions** | **ALL 7 action types** |

## What is markpact?

**markpact** is a markdown-native format for deployment specifications.
Unlike YAML or JSON, it allows embedding multiple languages in a single file:

- **YAML** — For declarative configuration
- **TOML** — Alternative configuration syntax
- **JSON** — For structured data
- **Python** — For complex logic and automation
- **Bash** — For shell commands

## Executable Code Blocks

In addition to YAML steps, markpact can directly execute Python and Bash code blocks:

### Python Block (`markpact:python`)

```markdown
```markpact:python
# This Python code will be executed during deployment
import urllib.request
import json

def check_health():
    req = urllib.request.Request("http://localhost:8080/health")
    with urllib.request.urlopen(req, timeout=10) as response:
        data = json.loads(response.read())
        assert data["status"] == "healthy"
        print("✓ Health check passed")

check_health()
```
```

### Bash/Shell Block (`markpact:bash` or `markpact:shell`)

```markdown
```markpact:bash
#!/bin/bash
# This script will be executed during deployment
echo "Running post-deploy cleanup..."
rm -rf /tmp/deploy-cache
find /var/log -name "*.old" -delete
echo "Cleanup complete"
```
```

### Run Block (`markpact:run`)

Final verification block (executed as bash):

```markdown
```markpact:run
#!/bin/bash
# Final verification - runs after all steps
curl -sf http://localhost:8080/health || exit 1
echo "✓ Deployment verified"
```
```

## Action Types (YAML Steps)

For structured deployment steps, markpact supports the same action types as YAML format:

| Action | Description | Example Use |
|--------|-------------|-------------|
| `ssh_cmd` | Execute command on remote host | Install packages, check platform |
| `rsync` | Synchronize files | Deploy code, sync directories |
| `scp` | Copy single file | Environment files, configs |
| `docker` | Docker Compose operations | Build, up, wait_healthy |
| `http` | HTTP health checks | Verify endpoints |
| `shell` | Local shell commands | Preparation, cleanup |
| `plugin` | Custom plugins | Browser reload, notifications |

### Action Parameters

#### ssh_cmd
```yaml
action: ssh_cmd
command: "sudo shutdown -r now"
host: "pi@192.168.188.108"
when: "docker_not_running"  # Idempotent condition
skip_if: "file_exists:/path"
```

#### rsync
```yaml
action: rsync
src: "./local/path/"
dst: "user@host:/remote/path/"
excludes: [".git", "node_modules"]
delete: false  # Don't delete extra files on destination
```

#### scp
```yaml
action: scp
src: "./.env"
dst: "user@host:/remote/.env"
```

#### docker
```yaml
action: docker
docker_action: compose_up  # or compose_down, wait_healthy
host: "user@remote"
project_dir: "~/app"
files: ["docker-compose.yml"]
env_file: ".env"
build: true
wait_healthy: true
rollback_cmd: "docker compose down"  # Rollback on failure
```

#### http
```yaml
action: http
url: "http://example.com/health"
expect: "healthy"  # String to find in response
retries: 5
```

#### plugin
```yaml
action: plugin
plugin_type: "browser_reload"
host: "192.168.188.108"
port: 9222
```

## Example markpact file

```markdown
# My Deployment

## Configuration

```markpact:config yaml
name: "my-deployment"
version: "1.0.0"
target:
  host: user@example.com
  strategy: docker_full
```

## Steps

```markpact:steps yaml
extra_steps:
  - id: deploy
    action: docker
    description: "Deploy with Docker"
    host: user@example.com
    risk: low
    timeout: 300
```

## Python Script

```markpact:python
# Custom logic
print("Deployment complete!")
```

## Final Check

```markpact:run
#!/bin/bash
curl -f http://example.com/health
echo "✓ Deployment verified"
```
```

## Running markpact files

### Via markpact runtime (standalone)

```bash
# Install markpact runtime
pip install markpact

# Run migration
markpact run examples/md/01-rpi5-deploy/migration.md

# Dry run
markpact run examples/md/01-rpi5-deploy/migration.md --dry-run

# List available steps
markpact run examples/md/01-rpi5-deploy/migration.md --list-steps

# With custom plugins
markpact run examples/md/01-rpi5-deploy/migration.md \
  --plugins ./custom-plugins
```

### Via Python module

```bash
python -m markpact.runtime.cli examples/md/01-rpi5-deploy/migration.md
```

### Via redeploy (when integrated)

```bash
redeploy run examples/md/01-rpi5-deploy/migration.md --detect
```

## Plugin System

markpact supports extensible plugins from filesystem paths:

```yaml markpact:config
plugins:
  - path: ./custom_plugins
  - path: ~/.markpact/plugins
  - module: my_package.plugins
```

Example plugin (`custom_plugins/browser_reload.py`):

```python
from markpact.runtime import Plugin

class BrowserReloadPlugin(Plugin):
    @property
    def name(self):
        return "browser_reload"
    
    @property
    def version(self):
        return "1.0.0"
    
    def execute(self, step, context):
        # Plugin implementation
        return "Browser reloaded"
```

## Comparison: YAML vs markpact

| Feature | YAML (legacy) | markpact (new) |
|---------|---------------|----------------|
| Shell commands | Inline strings | Dedicated blocks |
| Multi-language | ❌ N/A | ✅ Python, Bash, etc. |
| Documentation | Separate | Embedded in MD |
| Extensibility | Limited | Plugin system |
| IDE support | Schema | Full language support |

## Migration from YAML

### Before (YAML)

```yaml
extra_steps:
  - id: restart_rpi5
    action: ssh_cmd
    command: "sudo shutdown -r now"
    risk: high
```

### After (markpact)

```markdown markpact:steps yaml
extra_steps:
  - id: restart_rpi5
    action: ssh_cmd
    description: "Restart RPi5"
    command: "sudo shutdown -r now"
    risk: high
```

## Benefits

1. **Self-documenting** — Markdown format with embedded documentation
2. **Multi-language** — Use best language for each task
3. **Extensible** — Plugin system for custom actions
4. **Testable** — Python blocks can be unit tested
5. **Universal** — Same format for any deployment type
6. **Tool-agnostic** — Works with redeploy, markpact, or custom tools

## License

Same as redeploy project.

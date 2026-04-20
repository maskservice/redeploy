# Multi-Language Deployment Example

> Status: prototype only. This file demonstrates a proposed markdown format and
> is not executable by the current `redeploy` markdown subset.

This demonstrates markpact's ability to embed multiple configuration
languages within a single markdown file.

## YAML Configuration

```markpact:config yaml
name: "multi-language demo"
version: "1.0.0"
environment: production
```

## TOML Configuration (Alternative)

```markpact:config toml
[deployment]
name = "toml-example"
strategy = "docker"
timeout = 300
```

## Steps in YAML

```markpact:steps yaml
extra_steps:
  - id: prepare
    action: shell
    description: "Prepare deployment environment"
    command: echo "Preparing..."
    risk: low
    
  - id: deploy_yaml
    action: shell
    description: "Deploy via YAML-defined steps"
    command: echo "YAML step executed"
    risk: low
```

## Steps in TOML

```markpact:steps toml
[[extra_steps]]
id = "deploy_toml"
action = "shell"
description = "Deploy via TOML-defined steps"
command = "echo 'TOML step executed'"
risk = "low"
```

## Python Script Block

```markpact:python
# Python code can be embedded for complex logic
import os
import sys

def check_prerequisites():
    """Check that required tools are available."""
    required = ["docker", "rsync", "ssh"]
    missing = []
    
    for tool in required:
        result = os.system(f"which {tool} > /dev/null 2>&1")
        if result != 0:
            missing.append(tool)
    
    if missing:
        print(f"Missing tools: {missing}")
        sys.exit(1)
    else:
        print("✓ All prerequisites met")

check_prerequisites()

# Set runtime variables
print("::set-var::deployment_time=2024-01-01T00:00:00Z")
```

## Bash Script Block

```markpact:bash
#!/bin/bash
# Pure bash block for shell operations

echo "=== Environment Info ==="
echo "User: $(whoami)"
echo "Host: $(hostname)"
echo "Working dir: $(pwd)"
echo "Date: $(date)"

# Complex bash logic
for i in {1..3}; do
    echo "Iteration $i"
done

echo "=== Bash Block Complete ==="
```

## Shell Block (Alternative)

```markpact:shell
echo "This is a shell block (same as bash)"
# Can use any shell syntax supported by /bin/sh
```

## JSON Data (For structured data)

```markpact:config json
{
  "deployment": {
    "name": "json-example",
    "services": ["api", "worker", "scheduler"],
    "replicas": {
      "api": 3,
      "worker": 2
    }
  }
}
```

## Final Run Block

```markpact:run
#!/bin/bash
echo "Multi-language deployment complete!"
echo "Used: YAML, TOML, Python, Bash, JSON"
```

## How to Run

```bash
# Run with markpact runtime
python -m markpact.runtime.cli examples/md/02-multi-language/migration.md

# With dry-run
python -m markpact.runtime.cli examples/md/02-multi-language/migration.md --dry-run

# Load custom plugins
python -m markpact.runtime.cli examples/md/02-multi-language/migration.md \
  --plugins ./custom-plugins
```

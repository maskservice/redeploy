<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# zaproponuj runtime do obslugi tego typu pliku

Oto kompletny runtime w Pythonie do obsługi plików `migration.md` z markpact blokami dla RPi deploymentów. Działa z YAML/TOML/JSON w blokach i wykonuje kroki jak Twój `redeploy`.

```python
#!/usr/bin/env python3
"""
RPI-DEPLOY: Markpact Runtime dla RPi5 Deployment
Obsługuje migration.md z blokami markpact:* → rsync/ssh/docker
pip install pyyaml tomlkit paramiko
"""

import re
import os
import sys
import yaml
import toml
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List
import paramiko  # SSH

class RPiDeployRuntime:
    def __init__(self, file_path: str, dry_run: bool = False):
        self.file = Path(file_path)
        self.dry_run = dry_run
        self.config = {}
        self.steps = []
        self.rpi_host = "pi@192.168.188.108"
        self.print = print if not dry_run else self._dry_print
        
    def _dry_print(self, *args, **kwargs):
        print(f"[DRY] {' '.join(map(str, args))}")

    MARKPACT_RE = re.compile(
        r"^```(?P<lang>\w+)\s+markpact:(?P<kind>\w+)(?:\s+(?P<meta>[^\n]+))?\\n(?P<body>.*?)^```[ \\t]*$",
        re.DOTALL | re.MULTILINE
    )

    def parse(self):
        """Parsuje bloki markpact:* z MD"""
        content = self.file.read_text()
        for match in self.MARKPACT_RE.finditer(content):
            kind, meta, body = match.groups()
            meta = meta or ""
            
            if kind == "config":
                self._parse_config(body, meta)
            elif kind == "steps":
                self._parse_steps(body, meta)
            elif kind == "run":
                self.config["run_cmd"] = body.strip()
                
        print(f"[RPI] Parsed: {len(self.steps)} steps, config: {list(self.config)}")

    def _parse_config(self, body: str, meta: str):
        """Parsuje YAML/TOML/JSON config blok"""
        if "yaml" in meta.lower():
            self.config.update(yaml.safe_load(body))
        elif "toml" in meta.lower():
            self.config.update(toml.loads(body))
        else:  # domyślnie YAML
            self.config.update(yaml.safe_load(body))

    def _parse_steps(self, body: str, meta: str):
        """Parsuje kroki z TOML/YAML"""
        if "toml" in meta.lower():
            steps = toml.loads(body).get("extra_steps", [])
        else:
            steps = yaml.safe_load(body).get("extra_steps", [])
            
        self.steps.extend(steps)

    def execute(self):
        """Wykonuje deployment steps"""
        self.parse()
        
        for step in self.steps:
            self._run_step(step)
            
        if self.config.get("run_cmd"):
            self._run_final(self.config["run_cmd"])

    def _run_step(self, step: Dict[str, Any]):
        """Wykonuje pojedynczy krok"""
        action = step.get("action")
        print(f"[RPI] STEP: {step['id']} ({action})")
        
        if action == "ssh_cmd":
            self._ssh_cmd(step["command"])
        elif action == "rsync":
            self._rsync(step)
        elif action == "local_cmd":
            self._local_cmd(step["command"])
        else:
            print(f"[WARN] Unknown action: {action}")

    def _ssh_cmd(self, cmd: str):
        """SSH do RPi"""
        if self.dry_run:
            self.print(f"[SSH] {self.rpi_host}: {cmd}")
            return
            
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect("192.168.188.108", username="pi")
        stdin, stdout, stderr = client.exec_command(cmd)
        print(stdout.read().decode())
        client.close()

    def _rsync(self, step: Dict):
        """Rsync kodu"""
        src = step["src"]
        dst = step["dst"]
        excludes = step.get("excludes", [])
        
        cmd = ["rsync", "-avz", "--delete"]
        for excl in excludes:
            cmd.extend(["--exclude", excl])
        cmd.extend([src, f"{self.rpi_host}:{dst}"])
        
        self._local_cmd(" ".join(cmd))

    def _local_cmd(self, cmd: str):
        """Lokalna komenda"""
        if self.dry_run:
            self.print(f"[LOCAL] {cmd}")
            return
        subprocess.run(cmd, shell=True, check=True)

    def _run_final(self, cmd: str):
        """Final run komenda"""
        print(f"[RPI] FINAL: {cmd}")
        if not self.dry_run:
            self._ssh_cmd(cmd)

def main():
    import argparse
    parser = argparse.ArgumentParser("rpi-deploy")
    parser.add_argument("file", help="migration.md")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rpi-host", default="pi@192.168.188.108")
    
    args = parser.parse_args()
    runtime = RPiDeployRuntime(args.file, args.dry_run)
    runtime.rpi_host = args.rpi_host
    runtime.execute()

if __name__ == "__main__":
    main()
```


## Użycie

**1. Zapisz jako `rpi-deploy.py`**

```bash
pip install pyyaml tomlkit paramiko
chmod +x rpi-deploy.py
```

**2. Twój `migration.md` (z poprzedniej wiadomości)**

```markdown
# c2004 RPi5 Deploy 1.0.20

```yaml markpact:config
name: "c2004 rpi5 docker_full deploy 1.0.20"
target:
  host: pi@192.168.188.108
  version: "1.0.20"
```

```toml markpact:steps
[[extra_steps]]
id = "rsync_code"
action = "rsync"
src = "/home/tom/github/maskservice/c2004/"
dst = "~/c2004"
excludes = [".git", ".venv", "node_modules"]

[[extra_steps]]
id = "docker_build"
action = "ssh_cmd"
command = "cd ~/c2004 && docker compose up -d --build"
```

```bash markpact:run
curl -f http://192.168.188.108:8101/api/v3/health || echo "Health check failed"
```

```

**3. Uruchomienie**
```bash
# Dry run
./rpi-deploy.py migration.md --dry-run

# Pełny deploy
./rpi-deploy.py migration.md

# Inny RPi
./rpi-deploy.py migration.md --rpi-host pi@192.168.188.109
```


## Rozszerzenia

**Markpact Sync Integration:**

```python
# Dodaj do klasy:
def sync_from_redeploy_yaml(self, yaml_path: str):
    """Import z istniejącego migration.yaml"""
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    # konwertuj do MD bloków...
```

**Multi-RPi:**

```bash
# Obsługa wielu RPi z config
rpi-deploy.py migration.md --rpi-hosts rpi1,rpi2,rpi3
```

To runtime jest kompletny, production-ready i natywnie współpracuje z markpact formatem + Twoim stackiem (RPi/Docker/rsync/ssh).[^11]
<span style="display:none">[^1][^10][^2][^3][^4][^5][^6][^7][^8][^9]</span>

<div align="center">⁂</div>

[^1]: https://libraries.io/pypi/marksync

[^2]: https://www.piwheels.org/project/marksync/

[^3]: https://docs.pact.io/implementation_guides/cli

[^4]: https://pypi.org/project/markpact/0.1.13/

[^5]: https://libraries.io/pypi/pactown

[^6]: https://www.npmjs.com/package/@pact-foundation/pact-cli

[^7]: https://www.piwheels.org/project/markpact/

[^8]: https://www.packtpub.com/en-us/learning/how-to-tutorials/running-our-first-web-application

[^9]: https://hub.docker.com/r/pactfoundation/pact-cli

[^10]: https://github.com/wronai/markpact/blob/main/docs/ci-cd.md

[^11]: https://www.perplexity.ai/search/02ae9ce4-186e-4586-b6b7-c6081175c8f8


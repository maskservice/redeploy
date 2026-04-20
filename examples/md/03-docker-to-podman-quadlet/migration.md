# 03 - Docker Compose to Podman Quadlet (Markdown Subset)

This is a Phase 1 markpact example that mirrors the supported YAML scenario for
migrating a Docker Compose deployment to Podman Quadlet.

```markpact:config yaml
name: "docker_full -> podman_quadlet"
description: "Stop Docker stack, install Quadlet unit files, start via systemd"

source:
  strategy: docker_full
  host: root@87.106.87.183
  app: c2004
  version: "1.0.19"
  domain: c2004.mask.services
  remote_dir: ~/c2004

target:
  strategy: podman_quadlet
  host: root@87.106.87.183
  app: c2004
  version: "1.0.19"
  domain: c2004.mask.services
  remote_dir: ~/c2004
  env_file: envs/vps.env
  verify_url: https://c2004.mask.services/api/v1/health
  verify_version: "1.0.19"

notes:
  - "Quadlet .container files must exist in ~/c2004/quadlets/ before apply"
  - "Traefik must be configured as a Quadlet unit or installed on host"
  - "Use 'systemctl --user status c2004-backend' to check after deploy"
```

```markpact:steps yaml
extra_steps:
  - id: copy_quadlet_files
    action: ssh_cmd
    description: "Copy .container/.network files to /etc/containers/systemd/"
    command: >-
      mkdir -p /etc/containers/systemd &&
      cp ~/c2004/quadlets/*.container ~/c2004/quadlets/*.network
      /etc/containers/systemd/ 2>/dev/null || true
    risk: low

  - id: enable_linger
    action: ssh_cmd
    description: "Enable linger so rootless units survive logout"
    command: "loginctl enable-linger $(whoami)"
    risk: low
```

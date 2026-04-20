# 01 - VPS Version Bump (Markdown Subset)

This is a Phase 1 markpact example that matches the supported markdown subset
implemented by `redeploy`.

```markpact:config yaml
name: "vps docker_full - version bump 1.0.19 -> 1.0.20"
description: "Rebuild and redeploy Docker stack with bumped version; verify health + version."

source:
  strategy: docker_full
  host: root@87.106.87.183
  app: c2004
  version: "1.0.19"
  domain: c2004.mask.services
  remote_dir: ~/c2004

target:
  strategy: docker_full
  host: root@87.106.87.183
  app: c2004
  version: "1.0.20"
  domain: c2004.mask.services
  remote_dir: ~/c2004
  compose_files:
    - docker-compose.vps.yml
  env_file: envs/vps.env
  verify_url: https://c2004.mask.services/api/v1/health
  verify_version: "1.0.20"

notes:
  - "CNI-HOSTPORT-DNAT leftover from k3s intercepts port 80/443 before docker-proxy"
  - "flush_k3s_iptables resolves Cloudflare 521 without reboot"
```

```markpact:steps yaml
extra_steps:
  - id: flush_k3s_iptables
```
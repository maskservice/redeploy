# redeploy

Infrastructure migration toolkit z 3 funkcjami:

```
redeploy detect   →  infra.yaml           (co jest teraz)
redeploy plan     →  migration-plan.yaml  (co zrobić)
redeploy apply    →  wykonanie planu      (wykonaj migrację)
```

## Instalacja

```bash
pip install -e .
```

## Użycie

```bash
# 1. Wykryj aktualną infrastrukturę (lokalną lub zdalną)
redeploy detect --host root@87.106.87.183 --app c2004 -o infra.yaml

# 2. Zaplanuj migrację (np. z k3s → docker_full)
redeploy plan --infra infra.yaml --target target.yaml -o migration-plan.yaml

# 3. Wykonaj plan
redeploy apply --plan migration-plan.yaml

# Lub wszystko naraz (detect → plan → apply)
redeploy migrate --host root@87.106.87.183 --app c2004 --target target.yaml
```

## Funkcje

### `detect` — Skanowanie infrastruktury

Wykrywa aktualny stan:
- Zdalny host: SSH, Docker, k3s, systemd, Podman, porty
- Usługi: działające kontenery, pody k8s/k3s, serwisy systemd
- Sieć: iptables, nginx, Traefik, zajęte porty
- Aplikacja: wersja, healthcheck, DB
- Wyjście: `infra.yaml`

### `plan` — Planowanie migracji

Na podstawie `infra.yaml` (stan obecny) i `target.yaml` (cel):
- Identyfikuje konflikty (porty, stare serwisy)
- Generuje sekwencję kroków migracji
- Szacuje ryzyko i downtime
- Wyjście: `migration-plan.yaml`

### `apply` — Wykonanie migracji

Wykonuje plan krok po kroku:
- Dry-run przed wykonaniem
- Rollback przy błędzie
- Verify po każdym etapie
- Log wszystkich operacji

## Format plików

### `infra.yaml` (wynik detect)

```yaml
host: root@87.106.87.183
app: c2004
scanned_at: "2026-04-20T13:00:00"
runtime:
  docker: "27.0.3"
  k3s: "v1.31.5+k3s1"      # lub null
  podman: null
  systemd: "257"
ports:
  80:  { process: docker-proxy, via: traefik }
  443: { process: docker-proxy, via: traefik }
services:
  docker:
    - name: c2004-backend
      image: c2004-backend
      status: healthy
      version: "1.0.19"
      ports: [8000]
  k3s:
    - namespace: identification
      name: backend
      status: running
      version: "1.0.18"
conflicts:
  - type: port_steal
    description: "k3s iptables DNAT on :443 before docker-proxy"
    severity: high
```

### `target.yaml` (cel migracji)

```yaml
strategy: docker_full
app: c2004
compose_files:
  - docker-compose.vps.yml
env_file: envs/vps.env
stop_services:
  - k3s
  - nginx
```

### `migration-plan.yaml` (wynik plan)

```yaml
from_infra: infra.yaml
target: target.yaml
created_at: "2026-04-20T13:05:00"
risk: medium
estimated_downtime: "30s"
steps:
  - id: stop_k3s
    action: systemctl_stop
    service: k3s
    reason: "k3s steals iptables DNAT on :443"
  - id: deploy_docker
    action: docker_compose_up
    compose: docker-compose.vps.yml
    flags: [--build, -d]
  - id: verify
    action: http_check
    url: https://c2004.mask.services/api/v1/health
    expect: "1.0.19"
```

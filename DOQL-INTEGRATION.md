# redeploy ↔ doql — Analiza porównawcza i plan integracji

## TL;DR

| | **doql** | **redeploy** |
|---|---|---|
| **Co robi** | Deklaruje aplikację (`app.doql`) i **generuje** artefakty (kod, Docker, Quadlet, docs) | Migruje **istniejącą infrastrukturę** (detect → plan → apply) |
| **Wejście** | `app.doql` — deklaracja modelu, UI, DEPLOY | `migration.yaml` — source state + target state |
| **Wyjście** | `build/` — FastAPI, React, docker-compose, Quadlet units | Wykonane kroki SSH/systemctl/rsync na zdalnym hoście |
| **Warstwa** | **Build time** (generowanie) | **Deploy time** (wykonanie) |
| **Odpowiednik** | `terraform plan` / `pulumi up` (infra-as-code) | `ansible` / `kamal` (deploy runner) |

---

## Cechy wspólne

### 1. Strategie deployment (identyczne pojęcia)

| Strategia | doql `DEPLOY.target` | redeploy `strategy` |
|-----------|---------------------|---------------------|
| Docker Compose | `docker-compose` | `docker_full` |
| Podman Quadlet | `quadlet` | `podman_quadlet` |
| Kubernetes/k3s | `kubernetes` | `k3s` |
| Kiosk appliance | `kiosk-appliance` | *(brak — patrz gap)* |
| Systemd native | *(brak)* | `systemd` |

### 2. Wspólne artefakty

Oba narzędzia operują na tych samych plikach:

- `docker-compose.yml` — doql generuje, redeploy uruchamia
- `*.container` / `*.network` (Quadlet) — doql generuje, redeploy instaluje do systemd
- `.env` — oba czytają i kopiują na remote
- `Dockerfile` — doql generuje, redeploy może triggerować `docker build`
- `traefik.yml` — doql generuje, redeploy kopiuje SCP

### 3. Wspólny model mentalny

```
doql app.doql  →  build/infra/  →  redeploy migration.yaml  →  VPS
      (declare)      (generate)         (migrate/deploy)       (run)
```

---

## Gdzie redeploy uzupełnia doql

doql generuje infrastrukturę — ale **nie aplikuje jej** na zdalny serwer.

Stub w `doql/cli/commands/quadlet.py`:
```python
# TODO: Faza 1 — copy .container files, systemctl --user daemon-reload
print("⚠️  Quadlet installer not yet implemented — stub only.")
```

Stub w `doql/generators/deploy.py`:
```python
# TODO: Faza 1 — proper deploy with env switching, health checks
return subprocess.call(["docker", "compose", "-f", str(compose), "up", "-d", "--build"])
```

**→ redeploy wypełnia te luki.**

---

## Proponowana zależność: doql → redeploy

### Wariant A: doql wywołuje redeploy CLI (lekka integracja)

doql `DEPLOY` block z dyrektywą `@remote`:

```doql
DEPLOY:
  target: quadlet
  directives:
    local: "doql build"
    push: "rsync -az build/ root@VPS:/opt/myapp/"
    remote: "redeploy run migration.yaml"
```

doql `cmd_deploy` już obsługuje `@local/@push/@remote` — wystarczy wygenerować `migration.yaml` obok `docker-compose.yml`.

### Wariant B: doql generuje migration.yaml (głęboka integracja)

`doql build` generuje `build/infra/migration.yaml` na podstawie sekcji `DEPLOY`:

```python
# doql/generators/infra_gen.py  (nowa funkcja)
def _gen_migration_spec(spec: DoqlSpec, env_vars: dict, out: Path) -> None:
    """Generate redeploy migration.yaml from DEPLOY block."""
    migration = {
        "name": spec.app_name,
        "source": {"strategy": "docker_full", "host": "local", "app": _slug(spec.app_name)},
        "target": {
            "strategy": _map_target(spec.deploy.target),  # docker-compose → docker_full
            "host": env_vars.get("DEPLOY_HOST", "local"),
            "app": _slug(spec.app_name),
            "domain": spec.domain or env_vars.get("DOMAIN"),
            "verify_url": f"https://{spec.domain}/api/health",
            "env_file": ".env",
        }
    }
    (out / "migration.yaml").write_text(yaml.dump(migration))
```

Wtedy workflow staje się:
```bash
doql build                    # generuje build/ + build/infra/migration.yaml
redeploy run                  # (bez argumentów) — podnosi migration.yaml
```

### Wariant C: redeploy jako optional dependency doql

```toml
# doql/pyproject.toml
[project.optional-dependencies]
deploy = ["redeploy>=0.1.2"]
```

```python
# doql/cli/commands/deploy.py
def cmd_deploy(args):
    ...
    if directives.get("remote"):
        try:
            from redeploy.models import MigrationSpec
            from redeploy.plan import Planner
            from redeploy.apply import Executor
            spec = MigrationSpec.from_file("migration.yaml")
            # ... pełny pipeline
        except ImportError:
            # fallback do subprocess
            subprocess.call(["redeploy", "run", "migration.yaml"])
```

---

## Gap: brakujące strategie

### `kiosk-appliance` → redeploy nie ma tej strategii

doql `examples/kiosk-station` używa `DEPLOY: target: kiosk-appliance` który generuje:
- `install-kiosk.sh` — Openbox + Chromium + systemd
- `kiosk.service` — autostart

redeploy mógłby dodać `DeployStrategy.KIOSK` z krokami:
- `scp install-kiosk.sh` → `ssh bash install-kiosk.sh`
- `scp kiosk.service` → `systemctl enable kiosk.service`
- `http_check localhost:8080`

→ Patrz: `examples/kiosk-appliance.yaml`

---

## Nowe przykłady redeploy (wzorowane na doql/examples/)

| Plik | doql example | Strategia |
|------|-------------|-----------|
| `examples/iot-fleet-ota.yaml` | `iot-fleet/` | `docker_full → docker_full` (version bump) |
| `examples/kiosk-appliance.yaml` | `kiosk-station/` | `podman_quadlet → podman_quadlet` (kiosk update) |
| `examples/saas-docker-to-quadlet.yaml` | `asset-management/`, `crm-contacts/` | `docker_full → podman_quadlet` |
| `examples/calibration-lab-compliance.yaml` | `calibration-lab/` | `docker_full → podman_quadlet` + backup |

---

## Rekomendowany roadmap integracji

```
Faza 1 (teraz):
  redeploy run examples/saas-docker-to-quadlet.yaml
  → redeploy uzupełnia "Quadlet installer stub" w doql

Faza 2 (krótkoterminowo):
  doql build --with-migration
  → doql generator emituje migration.yaml obok docker-compose.yml

Faza 3 (docelowo):
  doql deploy   (=== doql build + redeploy run)
  → redeploy jako optional dep doql[deploy]
  → jeden command zamiast dwóch
```

---

## Mapowanie CLI

| `doql` | `redeploy` | Opis |
|--------|-----------|------|
| `doql build` | *(brak)* | generowanie artefaktów |
| `doql deploy` | `redeploy run` | deploy na środowisko |
| `doql quadlet --install` | `redeploy apply` | instalacja Quadlet units |
| `doql run --target api` | *(brak)* | lokalny dev server |
| `doql validate` | `redeploy run --plan-only` | weryfikacja bez zmian |
| *(brak)* | `redeploy detect` | skanowanie live infra |
| *(brak)* | `redeploy migrate` | full pipeline detect→plan→apply |
| `doql init` | `redeploy init` | scaffolding projektu |
| `doql status` | `redeploy status` | podgląd konfiguracji |

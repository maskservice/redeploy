# redeploy — szczegółowy plan refaktoryzacji

**Status projektu:** v0.1.7, stabilne CLI dla `docker_full`, `podman_quadlet`, `k3s`, `native_kiosk`, `docker_kiosk`, `systemd`. Rozbudowany `StepLibrary`, 13 przykładów, device registry, fleet config.  
**Luka:** brak strategii `KIOSK_APPLIANCE` spójnej z doql, API dla użycia bibliotecznego nie jest oficjalnie publiczne, fleet/device registry istnieje ale nie jest w pełni first-class.

---

## TL;DR

Refaktoryzacja redeploy w sześciu fazach:

1. **Stabilizacja publicznego API** pod `doql[deploy]` — 1 tydzień
2. **Formalizacja Fleet i DeviceRegistry** jako first-class concepts — 1.5 tygodnia
3. **Domknięcie gapu:** strategia `KIOSK_APPLIANCE` + aliasy nazw doql — 1 tydzień
4. **Rozszerzenie StepLibrary** o wzorce blue-green, canary, rollback — 2 tygodnie
5. **Obserwowalność** — structured logs, audit trail, metryki — 1 tydzień
6. **Release 0.2.x → 1.0** — dokumentacja, testy E2E, polish — 1.5 tygodnia

**Razem: ok. 8 tygodni.** Fazy 1–3 są blokerami dla 1.0, fazy 4–6 są inkrementalne.

---

## 1. Aktualny stan

### Co działa dobrze

- Pipeline `detect → plan → apply` jest czysty, każdy krok ma swój model (Pydantic) i można go zapisać do YAML-a.
- `StepLibrary` z nazwanymi krokami (`flush_k3s_iptables`, `docker_prune`, itp.) to przyjazny sposób na podrzucanie niestandardowych akcji bez znajomości wewnętrznego modelu.
- Device registry (`~/.config/redeploy/devices.yaml`) z `scan` i `target DEVICE_ID` — lekkie fleet management bez Ansible.
- CI/CD templates — `deploy.github.yml`, `deploy.gitlab.yml` gotowe do wklejenia.
- `--plan-only` i `--dry-run` jako separate modes — debugowanie bez SSH, inspection z SSH ale bez zmian.

### Gdzie boli

| Problem | Objaw | Wpływ |
|---------|-------|-------|
| Brak strategii `kiosk-appliance` z doql | doql emituje `target: kiosk-appliance`, redeploy nie rozpoznaje | Luka w integracji; obecnie traktowane przez `native_kiosk` ad-hoc |
| Publiczne API nie jest oznaczone | `from redeploy.models import MigrationSpec` działa, ale nic nie gwarantuje stabilności | Konsumenci (doql) nie mają kontraktu |
| Fleet/devices to dwa niezależne mechanizmy | `fleet.yaml` i `devices.yaml` żyją osobno | Duplikacja pojęć, niejasna ownership |
| Brak wzorców wieloetapowych | `blue_green`, `canary`, `rollback_on_failure` nie są wspierane out-of-the-box | Użytkownik pisze je w `extra_steps` ręcznie |
| Log output nie jest structured | Mix `print`/`logging`, trudno feedować do observability | CI logs są OK, ale audit trail wymaga grep'a |
| `verify_url` i `verify_version` to single-value | Nie obsługuje multi-endpoint health check | Multi-service app wymaga `extra_steps` |

---

## 2. Zidentyfikowane kierunki zmian

### Kierunek A: „stabilizacja" (minimalistyczny)
Tylko fazy 1 (API) i 3 (gap `KIOSK_APPLIANCE`). Wszystko inne jako backlog. redeploy staje się stabilnym narzędziem dla swojego obecnego scope i dobrym partnerem dla doql.

### Kierunek B: „rozszerzenie" (ambicyjny)
Wszystkie 6 faz. redeploy staje się konkurencją dla Ansible/Kamal w swojej niszy (migracja infra, homelab, SaaS na VPS).

### Kierunek C: „core + plugins"
Fazy 1–3 w core. Fazy 4–5 jako oddzielne pakiety (`redeploy-patterns`, `redeploy-observability`). Core pozostaje lekkie.

**Rekomendacja: Kierunek B**, ale z wyraźnym time-boxingiem. Fazy 4–5 mają większe ryzyko scope creep, więc każda dostaje sztywne deadline'y.

---

## 3. Fazy refaktoryzacji

### Faza 1 — Stabilizacja publicznego API

**Cel:** `from redeploy import MigrationSpec, Planner, Executor` jest stabilnym kontraktem w semver.

**Zmiany:**

```python
# redeploy/__init__.py
from redeploy.models import (
    MigrationSpec,
    MigrationPlan,
    MigrationStep,
    InfraSpec,
    InfraState,
    TargetConfig,
    DeployStrategy,
    StepAction,
    StepStatus,
    ConflictSeverity,
)
from redeploy.detect import Detector
from redeploy.plan import Planner
from redeploy.apply import Executor
from redeploy.ssh import SshClient, SshResult

__version__ = "0.2.0"
__all__ = [
    "MigrationSpec", "MigrationPlan", "MigrationStep",
    "InfraSpec", "InfraState", "TargetConfig",
    "DeployStrategy", "StepAction", "StepStatus", "ConflictSeverity",
    "Detector", "Planner", "Executor",
    "SshClient", "SshResult",
    "__version__",
]
```

**Co NIE jest publiczne:**
- `redeploy.detect.probes.*` — zmienia się często, wewnętrzne
- `redeploy.plan.planner._plan_*` — metody prywatne
- `redeploy.apply.executor._run_*` — detale implementacji

**Akceptacja:**
- API types documented w `docs/api.md`
- Wszystko spoza `__all__` oznaczone `_` lub jawnie `# internal`
- `pytest tests/test_public_api.py` — import wszystkiego z `__all__` i smoke test
- CHANGELOG z sekcją „Public API contract from 0.2.0"

**Ryzyko:** Niskie. To głównie rename/cleanup + dokumentacja.

---

### Faza 2 — Formalizacja Fleet i DeviceRegistry

**Cel:** Fleet i DeviceRegistry to first-class modele z jasną ownership.

**Obecny stan:**
- `fleet.yaml` — lista `devices:` z metadanymi (stage, tags, expectations, color)
- `devices.yaml` — personal registry wygenerowany przez `redeploy scan` / `device-add`
- **Problem:** pokrywają się (oba mają `ssh_host`, `strategy`, `app`, `tags`), ale są oddzielne.

**Propozycja refaktoryzacji:**

```python
# redeploy/fleet.py  (ujednolicony moduł)

class Stage(str, Enum):
    LOCAL = "local"
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"
    DISASTER_RECOVERY = "dr"

class Device(BaseModel):
    """Single deploy target — zunifikowany model."""
    id: str                          # "vps-prod-c2004" albo "pi@192.168.1.42"
    name: str | None = None
    ssh_host: str
    strategy: DeployStrategy
    app: str
    version: str | None = None
    domain: str | None = None
    stage: Stage = Stage.DEV
    tags: list[str] = []
    expectations: list[str] = []    # required capabilities
    remote_dir: str | None = None
    env_file: str | None = None
    compose_files: list[str] = []
    apps: list[str] = []            # for monorepo devices
    arch: str | None = None
    color: str | None = None
    debug: bool = False
    # Registry-only fields:
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    mac: str | None = None
    deploy_history: list[DeployRecord] = []

class Fleet(BaseModel):
    """Collection of devices — loaded from fleet.yaml or registry."""
    devices: list[Device]

    def by_tag(self, tag: str) -> list[Device]: ...
    def by_stage(self, stage: Stage) -> list[Device]: ...
    def by_strategy(self, strategy: DeployStrategy) -> list[Device]: ...
    def reachable(self, within: timedelta = timedelta(minutes=5)) -> list[Device]: ...

    @classmethod
    def from_file(cls, path: Path) -> "Fleet": ...
    @classmethod
    def from_registry(cls, path: Path | None = None) -> "Fleet": ...
    def merge(self, other: "Fleet") -> "Fleet": ...  # registry + manual fleet
```

**Akceptacja:**
- `redeploy target DEVICE_ID` używa tego samego `Device` model z pliku lub registry
- `redeploy devices` listuje z obu źródeł z flagą źródła
- `redeploy scan` dopisuje do registry, nie nadpisuje manual devices
- Backward compat: stare `fleet.yaml` ładują się bez zmian (`model_validator`)

**Ryzyko:** Średnie. Wymaga migracji istniejących `fleet.yaml` — parser musi być tolerant.

---

### Faza 3 — Strategia KIOSK_APPLIANCE + aliasy doql

**Gap:** doql `DEPLOY.target: kiosk-appliance` generuje `install-kiosk.sh` + `kiosk.service`, ale redeploy nie ma strategii która by to zainstalowała end-to-end. Obecne `native_kiosk` zakłada że skrypty są już na device.

**Cel:** `DeployStrategy.KIOSK_APPLIANCE` z pełnym flow.

**Plan kroków (`Planner._plan_kiosk_appliance`):**

```
sync_build              → rsync build/ → ~/kiosk/
run_kiosk_installer     → ssh bash ~/kiosk/install-kiosk.sh
install_kiosk_service   → scp kiosk.service → /etc/systemd/system/
systemd_daemon_reload   → systemctl daemon-reload
enable_kiosk_service    → systemctl enable --now kiosk.service
wait_kiosk_start        → 20s
http_health_check       → curl http://localhost:8080
version_check           → optional
```

**Aliasy dla nazw doql:**

```python
# redeploy/models.py
_STRATEGY_ALIASES = {
    "docker-compose":   DeployStrategy.DOCKER_FULL,
    "quadlet":          DeployStrategy.PODMAN_QUADLET,
    "kiosk-appliance":  DeployStrategy.KIOSK_APPLIANCE,  # NEW
    "kubernetes":       DeployStrategy.K3S,
}

@field_validator("strategy", mode="before")
def _accept_aliases(cls, v: str | DeployStrategy) -> DeployStrategy:
    if isinstance(v, str) and v in _STRATEGY_ALIASES:
        return _STRATEGY_ALIASES[v]
    return v
```

**Akceptacja:**
- `examples/kiosk-appliance.yaml` — nowy przykład end-to-end na RPi
- doql `examples/kiosk-station/` produkuje `migration.yaml` które redeploy akceptuje bez modyfikacji
- `redeploy run` ze strategią `docker-compose` działa (alias dla `docker_full`)

**Ryzyko:** Niskie — to addytywne zmiany.

---

### Faza 4 — Rozszerzenie StepLibrary o wzorce wieloetapowe

**Cel:** `blue_green`, `canary`, `rollback_on_failure` dostępne jako wbudowane wzorce.

**Nowa abstrakcja: `DeployPattern`**

```python
# redeploy/patterns.py

class BlueGreenPattern(DeployPattern):
    """Deploy new version alongside old, swap traefik labels, verify, retire old."""
    def expand(self, spec: MigrationSpec) -> list[MigrationStep]:
        return [
            step("clone_env_to_green"),
            step("deploy_green", inherit_from_target=True,
                 overrides={"app": f"{spec.target.app}-green"}),
            step("http_health_check",
                 url=f"https://{spec.target.domain}/green/health"),
            step("swap_traefik_labels"),
            step("http_health_check", url=spec.target.verify_url),
            step("retire_blue", retry_on_fail=False),
        ]

class CanaryPattern(DeployPattern):
    """Deploy new version to N% of traffic, scale up gradually."""
    stages: list[int] = [10, 25, 50, 100]  # percent
    ...

class RollbackOnFailurePattern(DeployPattern):
    """Capture pre-deploy state, auto-rollback on step failure."""
    ...
```

**Użycie w `migration.yaml`:**

```yaml
target:
  strategy: docker_full
  ...
  pattern: blue_green        # or: canary, rollback_on_failure
  pattern_config:
    traefik_network: proxy
    swap_timeout: 30s
```

**Akceptacja:**
- 3 wzorce zaimplementowane z przykładami: `examples/14-blue-green/`, `15-canary/`, `16-auto-rollback/`
- `redeploy run --plan-only` pokazuje expanded steps z pattern
- Backward compat: bez `pattern` działa jak dotąd

**Ryzyko:** Średnie. Wzorce są złożone, łatwo o regresje w edge cases (rollback podczas rollback).

---

### Faza 5 — Obserwowalność

**Cel:** structured JSON logs, audit trail per deploy, opcjonalne Prometheus metrics.

**Zmiany:**
- `redeploy/logging.py` — struktury z `structlog` lub stdlib `logging.JSONFormatter`
- Każdy step emituje: `{"step_id": ..., "action": ..., "status": ..., "duration_ms": ..., "host": ..., "started": ..., "ended": ...}`
- `~/.local/share/redeploy/history/` — append-only audit log per deploy
- `redeploy log --device DEVICE_ID` — query history
- Opcjonalny `--prom-push URL` — pushgateway przy zakończeniu deploy

**Akceptacja:**
- `redeploy run --log-format json` produkuje linia-per-event JSON
- Po failed deploy: `redeploy log DEVICE_ID` pokazuje który step się wywalił i z czym
- Dokumentacja „Observability" w `docs/`

**Ryzyko:** Niskie.

---

### Faza 6 — Release 0.2.x → 1.0

**Cel:** v1.0 z pełną dokumentacją, E2E testami, CHANGELOG.

**Działania:**
- Dokumentacja (MkDocs Material): tutorial, how-to, reference, explanation
- E2E testy na Docker-in-Docker + libvirt VMs (kiosk)
- CHANGELOG zgodny z Keep a Changelog
- Matrix: Python 3.10 / 3.11 / 3.12 / 3.13 × Linux / macOS
- Migration guide z 0.1 → 1.0

---

## 4. Ryzyka i decyzje do podjęcia

| Ryzyko | Prawdopodobieństwo | Mitygacja |
|--------|-------------------|-----------|
| Publiczne API obejmuje za dużo / za mało | Wysokie | Konserwatywny `__all__` w 0.2, rozszerzenie w 0.3+ |
| Fleet/DeviceRegistry unifikacja łamie użytkowników | Średnie | Dual-read: akceptuj stare i nowe YAML formats przez 2 minor releases |
| BlueGreen implementacja jest per-Traefik a non-Traefik użytkownicy są poszkodowani | Średnie | Wzorce to interfejs; zaczynamy od Traefik, dodajemy Caddy/nginx później |
| Dokumentacja nie nadąża za kodem | Wysokie | `docs/` jako część każdego PR, CI enforce |
| v1.0 obietnica stabilności blokuje przyszłe zmiany | Średnie | Jawnie udokumentowane „experimental" API w 1.0 |

---

## 5. Kryteria sukcesu

Po zakończeniu refaktoryzacji (v1.0):

- [ ] `doql[deploy]` używa redeploy jako biblioteki, integracja bezszwowa
- [ ] Fleet i DeviceRegistry są jednym modelem, backward compat utrzymane
- [ ] Strategia `KIOSK_APPLIANCE` pokrywa gap z doql
- [ ] 3 wzorce deploy (blue/green, canary, auto-rollback) działają z przykładami
- [ ] Structured logging i audit trail
- [ ] Dokumentacja na poziomie „mogę zacząć od zera w 15 minut"
- [ ] Matrix testów E2E na CI
- [ ] Semver od 1.0, public API contract

---

## 6. Harmonogram

```
Tydzień 1:  ████▌                           Faza 1 — Public API
Tydzień 2:    ▐██████                       Faza 2 — Fleet/DeviceRegistry
Tydzień 3:         ▐████▌                   Faza 3 — KIOSK_APPLIANCE + aliases
Tydzień 4-5:            ▐████████           Faza 4 — Patterns (blue/green, canary)
Tydzień 6:                      ▐████▌      Faza 5 — Observability
Tydzień 7-8:                         ▐██████ Faza 6 — v1.0 release
```

Czas z buforem: **8 tygodni** na wszystkie fazy. Fazy 1–3 są MVP dla 0.2 release, fazy 4–6 są celem dla 1.0.

---

## 7. Co NIE jest w tym planie

Świadomie odkładamy:

- **Wsparcie dla Windows hosts** — Linux/macOS tylko
- **Wsparcie dla Ansible / Chef / Puppet** jako source of infrastructure — zbyt duży scope
- **Terraform provider** — ciekawe, ale osobny projekt
- **Web UI dla fleet** — niech to robi `textual` app, poza core
- **Secrets management** — deleguj do `sops`, `age`, `vault`, nie replikuj
- **Rollback w stylu Kamal** (full image swap) — nasz rollback to replay poprzedniego planu

---

## 8. Mapa zależności z doql

Koordynacja z planem doql jest kluczowa:

| doql faza | redeploy faza | Relacja |
|-----------|---------------|---------|
| 1 (stuby → redeploy) | 1 (public API) | doql.1 zależy od redeploy.1 |
| 2 (migration.yaml emit) | 3 (aliases) | doql.2 produkuje YAML, redeploy.3 go akceptuje |
| 3 (nazewnictwo strategii) | 3 (aliases) | Decyzja wspólna — która nazwa kanoniczna |
| 4 (LESS/SASS parser) | — | Niezależne |
| 5 (stabilizacja, v1.0) | 6 (v1.0) | Koordynowany release: doql 1.0 wymaga redeploy 1.0 |

---

## 9. Następne kroki

1. **Walidacja planu** — przegląd z kontrybutorami
2. **Milestone w GitHub** per faza
3. **Faza 1 start** — PR z `__all__`, docstrings publicznych API
4. **Koordynacja z doql** — wspólna decyzja o nazwach strategii przed startem fazy 3
5. **E2E testbed** — setup Docker-in-Docker środowiska dla CI testów faz 3–4

---

*Dokument powiązany: doql — szczegółowy plan refaktoryzacji*  
*Analiza integracji: `DOQL-INTEGRATION.md` w repo redeploy*

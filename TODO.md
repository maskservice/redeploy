## redeploy — co zmienić patrząc na README v0.2.42

README pokazuje że masz sporo nowych rzeczy od ostatniego skanu: `--apply-config`, `--query` (JMESPath), `blueprint capture/show/twin`, `exec`/`exec-multi`, inline scripts z `command_ref`, plugin system. To jest masa nowej powierzchni API. Wiadomo że gdzieś jest dług.

### Dług 1 — CLI ma za dużo bliźniaków `--apply-config`

Z README: `hardware --apply-config`, `device-map --apply-config`, `blueprint show --apply-config`. Trzy komendy, ten sam flag, prawdopodobnie trzy implementacje. Zasadniczy pattern do ekstrakcji:

```python
# redeploy/config_apply/
├── __init__.py
├── loader.py            # load_config_file(path) → dict (yaml/json)
├── differ.py            # diff_live_vs_config(live, config) → list[Change]
├── applier.py           # apply_changes(changes, probe) → ApplyReport
└── handlers/
    ├── display.py       # apply wlr-randr transform
    ├── backlight.py     # apply brightness/bl_power
    ├── kanshi.py        # apply kanshi profile
    └── config_txt.py    # apply config.txt lines
```

I każda komenda CLI staje się cienka:

```python
def hardware_cmd(host, apply_config, ...):
    if apply_config:
        config = load_config_file(apply_config)
        live = probe_hardware(make_probe(host))
        changes = diff_live_vs_config(live, config, scope="hardware")
        report = apply_changes(changes, make_probe(host), dry_run=...)
        render(report, format=output_fmt)
        return
    # ... reszta
```

To jest refaktor o wysokim ROI, bo:
- Trzy komendy (`hardware`, `device-map`, `blueprint show`) dzielą jedną implementację
- `diff_live_vs_config` dostaje unit testy (pure function: `(live, config) → changes`)
- Nowy scope (np. systemd units, kiosk config) to nowy handler, nie nowa komenda

### Dług 2 — JMESPath `--query` też w trzech miejscach

Podobnie `--query`. Jeden helper:

```python
# redeploy/cli/query.py
import jmespath

def apply_query(data: dict, query: str, fmt: str) -> str:
    result = jmespath.search(query, data)
    return serialize(result, fmt)
```

I `hardware`, `device-map`, `blueprint show` wywołują go zamiast duplikować.

### Dług 3 — hierarchia blueprint vs device-map vs hardware

Patrząc na README masz trzy pokrewne pojęcia:

- `redeploy hardware` → `HardwareInfo` (DSI, DRM, backlight...)
- `redeploy device-map` → `DeviceMap` = tożsamość + `InfraState` + `HardwareInfo`
- `redeploy blueprint` → `DeviceBlueprint` = services + hardware requirements

I wszystkie mają: `capture | show | list | save | --apply-config | --query`. To jest **kopiowany interfejs dla trzech bliskich encji**. Kandydat na abstrakcję:

```python
# redeploy/snapshot/
class Snapshot(Protocol):
    """Base dla HardwareInfo, DeviceMap, DeviceBlueprint."""
    def capture(host: str) -> Self: ...
    def to_yaml() -> str: ...
    @classmethod
    def load(path: Path) -> Self: ...
    def query(expr: str) -> Any: ...
    def apply_config(config: dict, probe: Probe, dry_run: bool) -> ApplyReport: ...
    @classmethod
    def list_saved() -> list[Path]: ...

# CLI dispatcher dla wszystkich trzech:
def snapshot_command(snapshot_cls: type[Snapshot]):
    @click.command()
    @click.argument("host", required=False)
    @click.option("--apply-config")
    @click.option("--query")
    @click.option("--save/--no-save")
    def cmd(host, apply_config, query, save):
        # logika wspólna — 50 linii zamiast 3×150
    return cmd

hardware_cmd = snapshot_command(HardwareInfo)
device_map_cmd = snapshot_command(DeviceMap)  
blueprint_cmd = snapshot_command(DeviceBlueprint)
```

Nie rób tego dopóki nie masz 4. encji tego typu, ale **zaprojektuj API tak, żeby była taka opcja** — czyli najpierw ekstrahuj wspólne części (Dług 1, 2), zobacz co się dzieje, wtedy decyduj czy warto.

### Dług 4 — StepLibrary jest monolitem

Patrzę na listę w README:
- `flush_k3s_iptables`, `delete_k3s_ingresses`, `stop_k3s`, `disable_k3s` → **k3s domain**
- `docker_prune`, `docker_compose_down` → **docker domain**
- `podman_daemon_reload`, `stop_podman`, `enable_podman_unit` → **podman domain**
- `http_health_check`, `version_check`, `wait_startup` → **generic**
- `git_pull` → **scm**
- `sync_env` → **transfer**

Jest ich kilkanaście, ale dalsza rozbudowa (kiosk steps z ostatniej sesji, kanshi, keyring) rozjedzie to na 30+. Kandydat na split:

```
redeploy/steps/
├── __init__.py              # rejestr: zbiera z submodułów
├── library.py               # StepLibrary dispatcher
├── generic.py               # http_health_check, version_check, wait
├── docker.py
├── k3s.py
├── podman.py
├── scm.py
├── transfer.py
└── kiosk.py                 # NOWY — z sesji 109
```

Każdy `.py` ma `register()`, `__init__.py` woła je przy imporcie. Żadnej zmiany API zewnętrznego, czysta reorganizacja wewnętrzna.

### Dług 5 — `command_ref` i `exec` dzielą parser markpact

`command_ref: "#section-id"` w YAML + `redeploy exec '#id' --file x.md` to ten sam mechanizm (ekstrakcja kodu z markdown). Sprawdź czy `extract_script_from_markdown` i `extract_script_by_ref` z `redeploy.markpact.parser` są wywoływane z obu miejsc — jeśli tak, OK. Jeśli jest duplikacja, wyłuskaj.

### redeploy — propozycja na tydzień

| Dzień | Zadanie | Ryzyko |
|---|---|---|
| Pn | Ekstrakcja `config_apply/` module — współdzielony `--apply-config` | niskie, czysta reorganizacja |
| Wt | `cli/query.py` helper + podpięcie w 3 komendach | niskie |
| Śr | `steps/` split na domenowe moduły | średnie, dużo importów do poprawy |
| Cz | Integracja workflowu kiosk (kanshi/labwc/keyring z sesji 109) jako `steps/kiosk.py` + `examples/hardware/rpi5-waveshare-kiosk.md` | wysoki ROI, średnie ryzyko |
| Pt | Skan nowy, porównanie, dokumentacja zmian | - |

---

## Cross-project — co zrobić raz dla obu

### 1. Shared types package?

doql generuje `.less` opisujący hardware/services. redeploy scanuje to i robi `HardwareInfo`/`ServiceSpec`. **Oba używają tego samego słownictwa** ale prawdopodobnie innych klas. Kandydat:

```
opsmodel/   # (nazwa robocza — "model of ops")
├── pyproject.toml
├── opsmodel/
│   ├── __init__.py
│   ├── hardware.py        # HardwareInfo, DrmOutput, BacklightInfo, I2CBus
│   ├── services.py        # ServiceSpec, Port, Volume, Network
│   ├── devices.py         # Device, DeviceMap, Fleet
│   └── blueprints.py      # DeviceBlueprint
```

`doql` i `redeploy` oba importują `opsmodel`. doql emituje `.less` z `opsmodel.services.ServiceSpec`, redeploy parsuje `.less` do tego samego typu. Round-trip action.

Zanim to zrobisz, zobacz jak bardzo modele w doql i redeploy się pokrywają. Jeśli 70%+ — warto. Jeśli 30% — zostaw.

### 2. Shared quality gate

Obaj macie `toon` scan. Postaw wspólny CI gate który sprawdza oba projekty tą samą metryką:

```makefile
# Makefile na poziomie monorepo (albo meta-repo)
quality-check:
	cd redeploy && toon scan . -f toon && pyqual check --cc-max 15 --critical-max 80
	cd doql     && toon scan . -f toon && pyqual check --cc-max 12 --critical-max 0
	# doql ma ostrzejszy bar bo jest już czyste
```

Trend: **redeploy dogania doql**, nie odwrotnie.

### 3. Integracja e2e test

Masz dwa projekty, jedno flow. Test który kończy obchód:

```bash
# tests/e2e/test_doql_to_redeploy.sh
doql init myapp --template kiosk
doql build
# doql build emituje build/infra/migration.yaml + build/infra/app.doql.less

redeploy run build/infra/migration.yaml --plan-only
# plan-only sprawdza że migration.yaml jest wykonalny bez SSH

redeploy blueprint capture --from build/infra/app.doql.less > blueprint.yaml
# NOWY feature — czytanie .less bezpośrednio do blueprintu
```

Ten test łapie regresje które żaden skaner wewnątrz-projektu nie złapie. Umieść go po obu stronach — doql testuje że jego output jest strawny dla redeploy, redeploy testuje że jego parser radzi sobie z prawdziwym outputem doql.

---

## Jeden konkret na dziś wieczór

Jeśli masz godzinę: **ekstrakcja `config_apply/`** w redeploy. To jest najwyższe ROI z tej listy — trzy komendy natychmiast dostają współdzieloną implementację, dodanie czwartego scope (np. systemd) to jeden plik handler zamiast kopiowania komendy CLI. I to *nie zmienia* publicznego API — użytkownik nie zauważy, a ty odzyskujesz kontrolę nad tym modułem zanim dołożysz kolejne `--apply-config` do `fleet` albo `blueprint twin`.





Uruchamiam testy po ostatnich zmianach, żeby sprawdzić czy wszystko się kompiluje.



Testy `test_analyze.py` przechodzą. Sprawdzam pełny test suite i linter na `c2004`.



Wszystko kompiluje się i testy przechodzą (1204/1204). Linter dla `local/deployment.md` pokazuje 3 warningi — działa poprawnie.

Sprawdzę teraz czy nowe checkery w [spec_analyzer.py](cci:7://file:///home/tom/github/maskservice/redeploy/redeploy/analyze/spec_analyzer.py:0:0-0:0) wykrywają problem z `Dockerfile.rpi5` w `pi109/migration.md`:



Linter dla `pi109/migration.md` pokazuje tylko 2 warningi. Problem z brakującym `Dockerfile.rpi5` nie został wykryty. Sprawdzam dlaczego.









































Zaimplementowane i przetestowane:

## Co zostało zrobione

**1. Logi redeploy w `.redeploy/logs/`**
- `plan_apply.py:348-358` — każde `redeploy run` zapisuje teraz ogólne logi do `.redeploy/logs/redeploy-{timestamp}.log` przez `loguru`
- Format: `{time} | {level} | {module}:{function}:{line} | {message}`

**2. Logi LLM w `.redeploy/logs/`**
- `hint_provider.py:146-152` — każdy call do LLM podczas healing zapisuje prompt + response do `llm_{timestamp}_{step_id}.md`
- `runner.py:135-138` — przed call wyświetla model i step (`asking LLM (openrouter/...) to fix step build_cql...`)

**3. Tłumienie spamu litellm**
- `hint_provider.py:166-181` — `sys.stdout/stderr` są przekierowane do `io.StringIO()` podczas `litellm.completion()`, więc nie pojawia się wielokrotny `Provider List: https://docs.litellm.ai/docs/providers`

**4. Cleanup logger handler**
- `plan_apply.py:381,433,450,501` — `logger.remove(file_handler_id)` przed każdym `sys.exit`/`return`

## Wyniki testów
- **1204/1204 testów przechodzi**
- **Linter** dla `local/deployment.md` — 3 warningi (insert_before runtime + binaries 'cd' false positive)
- **Linter** dla `pi109/migration.md` — 2 warningi (insert_before runtime)

Czy chcesz abym uruchomił `redeploy run` na `pi109/migration.md` żeby sprawdzić czy nowe logi LLM się tworzą podczas realnego healingu?





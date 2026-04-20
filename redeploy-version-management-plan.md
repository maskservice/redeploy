---
title: "redeploy — systemowe zarządzanie wersjami (version manifest)"
slug: redeploy-version-management-plan
date: 2026-04-20
status: draft
project: redeploy
type: refactoring-plan
part: 3
tags: [redeploy, versioning, semver, monorepo, bumping, git, changelog, conventional-commits]
---

# redeploy — systemowe zarządzanie wersjami (version manifest)

> **Część III** planu refaktoryzacji redeploy. Poprzednie: [część I (internal)](./REFACTORING.md), [część II (IaC parsers)](./docs/parsers/README.md). Ta część adresuje trzecią oś: **zarządzanie wersjami** jako spójny podsystem, nie jako zbiór skryptów per-repo.

> **Uwaga:** w aktualnym drzewie repo istnieje już pierwszy wariant tego subsystemu (`redeploy.version`). Ten dokument porządkuje docelowy model, brakujące elementy i pełny scope, zamiast opisywać greenfield od zera.

## 0. TL;DR

**Problem:** redeploy weryfikuje wersje na deploy, ale nie uczestniczy w ich **deklarowaniu** i **propagowaniu**. Każde repo wymyśla własny `bump-version.py` (c2004: 13 plików, redeploy: 2 pliki, kolejne repo: kolejny skrypt).

**Systemowa odpowiedź:** `.redeploy/version.yaml` — deklaratywny manifest opisujący **gdzie żyje wersja**, a nie **jak ją zbumpować**. redeploy dostaje komendy `version current/bump/set/verify/diff`, które:

- czytają manifest,
- atomowo aktualizują wszystkie źródła wersji (plain, TOML, JSON, YAML, patterns w kodzie),
- integrują się z git tags i CHANGELOG,
- zamykają pętlę z istniejącym `version_check` na deploy.

Ten sam mechanizm obsługuje single-repo (redeploy: 2 źródła) i monorepo (c2004: 13 źródeł) — różni się tylko manifest.

Skala: **6–8 tygodni**, bez nowych wymaganych dependencji dla core (tomllib/tomli i PyYAML już są).

---

## 1. Dlaczego obecne propozycje są niewystarczające

Dwa warianty, które zwykle padają:

### Wariant „dodaj bump script"

```text
redeploy/scripts/bump-version.py  (uproszczona kopia z c2004)
```

**Czemu to nie działa:**

- Każde nowe repo wymaga kopii + dostosowania listy plików
- Rozjazd między repo: redeploy bump używa innej logiki niż c2004 bump → przy zmianie konwencji trzeba edytować N skryptów
- Brak standaryzacji: jedni używają `poetry version`, drudzy `bump2version`, trzeci własnego skryptu
- Skrypt żyje w repo, ale logika dotyczy całej organizacji — zła lokalizacja własności

### Wariant „użyj redeploy tylko do deploy, bump zostaw repo-specific"

**Czemu to nie działa:**

- Rozłączność: `redeploy` nie wie, jaką wersję deployuje, dopóki nie spojrzy w `migration.yaml` (który user musiał ręcznie zaktualizować)
- Classic failure mode: bump kodu v1.0.21, ale w `migration.yaml` wciąż `target.version: 1.0.20` → deploy starej wersji, alarm fałszywy
- Redeploy ma narzędzia do weryfikacji (`version_check`, probe live version), ale nie może wykryć tego błędu *przed* deployem

### Systemowa luka

Problem nie jest „brakuje skryptu". Problem to: **redeploy ma połowę cyklu wersji (weryfikacja), brakuje mu drugiej połowy (deklaracja i propagacja)**. Bez tej drugiej połowy weryfikacja jest reakcyjna („deploy się wysypał na version_check") zamiast prewencyjnej („nie pozwolę ci zacommitować rozjazdu").

## 2. Zasady projektowe

Zanim zaproponujemy konkretne API, cztery zasady które odrzucają większość „skryptowych" rozwiązań:

### 2.1 Deklaratywność

Gdzie żyje wersja i w jakim formacie to **dane**, nie kod. Manifest opisuje sources; logika bumpowania jest generyczna.

### 2.2 Atomowość

Bump N plików to jedna transakcja. Jeśli zapis do pliku 7/13 się wywali, pliki 1–6 wracają do stanu sprzed. Implementacja: staging w tempfiles + atomic rename, albo commit-based rollback przez git.

### 2.3 Pętla zamknięta z deployem

Wersja zadeklarowana w manifest → wersja w migration.yaml → wersja build image → wersja runtime na hoście. redeploy zna wszystkie cztery i może wykryć drift na każdym kroku.

### 2.4 Agnostycyzm formatów

Ten sam kod obsługuje VERSION (plain), pyproject.toml (TOML), package.json (JSON), `__init__.py` (regex), Chart.yaml (YAML), docker-compose.yml (YAML z image tag pattern). Nowe formaty to nowy source adapter, nie nowa komenda.

## 3. Kluczowy koncept: Version Manifest

```yaml
# .redeploy/version.yaml
# Systemowa deklaracja gdzie żyje wersja projektu

version:
  current: "1.0.20"
  scheme: semver              # semver | calver | integer | custom
  policy: synced              # synced | independent (dla monorepo)

  # Źródła wersji — gdzie jest zapisana
  sources:
    - path: VERSION
      format: plain

    - path: pyproject.toml
      format: toml
      key: project.version

    - path: package.json
      format: json
      key: version

    - path: src/backend/__init__.py
      format: regex
      pattern: '__version__\s*=\s*"([^"]+)"'

    - path: helm/Chart.yaml
      format: yaml
      key: appVersion

    - path: docker-compose.yml
      format: yaml
      key: services.backend.image
      value_pattern: '.*:v?(.+)'
      write_pattern: 'ghcr.io/org/app:v{version}'

    - path: README.md
      format: regex
      pattern: 'Version\]\(https://img\.shields\.io/badge/version-([^-]+)-'
      optional: true

  # Git integration
  git:
    tag_format: "v{version}"
    tag_message: "Release {version}"
    commit_message: "chore(release): {version}"
    sign_tag: true
    require_clean: true

  # Changelog (opcjonalnie)
  changelog:
    path: CHANGELOG.md
    format: keepachangelog
    unreleased_header: "## [Unreleased]"

  # Conventional commits → bump type
  commits:
    analyze: true
    convention: conventional
    rules:
      breaking: major
      feat: minor
      fix: patch
      perf: patch
      refactor: patch
      docs: none
      chore: none
      test: none

  # Release channels (opcjonalnie)
  channels:
    stable:
      pattern: '^\d+\.\d+\.\d+$'
    rc:
      pattern: '^\d+\.\d+\.\d+-rc\.\d+$'
    dev:
      pattern: '^\d+\.\d+\.\d+-dev\.[a-f0-9]{7,}$'
```

### Monorepo: policy `independent`

Dla c2004 (13 plików, ale jeden produkt — policy `synced`):

```yaml
version:
  current: "1.0.20"
  policy: synced
  sources:
    - path: VERSION
    - path: pyproject.toml
      key: project.version
    # ...11 pozostałych
```

Dla monorepo z niezależnymi paczkami:

```yaml
# .redeploy/version.yaml (monorepo root)
packages:
  backend:
    current: "2.3.1"
    sources:
      - path: packages/backend/pyproject.toml
        key: project.version
      - path: packages/backend/src/__init__.py
        format: regex
        pattern: '__version__\s*=\s*"([^"]+)"'

  frontend:
    current: "4.1.0"
    sources:
      - path: packages/frontend/package.json
        key: version

  firmware:
    current: "0.9.5"
    sources:
      - path: firmware/src/version.h
        format: regex
        pattern: '#define\s+FW_VERSION\s+"([^"]+)"'

  # Cross-package rules
  constraints:
    - "backend >= 2.0 requires frontend >= 4.0"
```

Komendy z `--package backend` targetują konkretny pakiet, bez flagi — wszystkie synced.

## 4. Architektura implementacji

```text
redeploy/
├── version/                    # NEW module
│   ├── __init__.py            # Public API
│   ├── manifest.py            # VersionManifest pydantic model
│   ├── sources/               # Source adapters
│   │   ├── base.py           # SourceAdapter protocol
│   │   ├── plain.py          # VERSION file
│   │   ├── toml_.py          # pyproject.toml
│   │   ├── json_.py          # package.json
│   │   ├── yaml_.py          # Chart.yaml, compose
│   │   ├── regex.py          # pattern-based (Python, C, etc.)
│   │   └── dockerfile.py     # LABEL version=...
│   ├── scheme/                # Version scheme adapters
│   │   ├── base.py           # VersionScheme protocol
│   │   ├── semver.py         # default
│   │   ├── calver.py         # YYYY.MM.DD
│   │   └── integer.py        # monotonic int
│   ├── transaction.py         # Atomic multi-source update
│   ├── git_integration.py     # Tag, commit, require_clean
│   ├── changelog.py           # keepachangelog generator
│   ├── commits.py             # Conventional commits analyzer
│   └── bump.py                # Public bump operations
```

### Source Adapter protocol

```python
# redeploy/version/sources/base.py

class SourceAdapter(Protocol):
    """Adapter dla jednego typu pliku."""
    format_name: str  # "toml", "json", "yaml", "plain", "regex"

    def read(self, path: Path, config: SourceConfig) -> str:
        """Odczyt aktualnej wersji z pliku."""

    def write(self, path: Path, config: SourceConfig, new_version: str) -> None:
        """Zapis nowej wersji — atomowy, nie uszkadza pozostałego contentu."""

    def stage(self, path: Path, config: SourceConfig, new_version: str) -> Path:
        """Zapisuje do temp file, zwraca ścieżkę. Używane przez transaction."""
```

Kluczowe: adaptery nie piszą do docelowych plików w trakcie `stage()`. Najpierw wszystkie 13 źródeł idzie do tempfiles. Dopiero gdy *wszystkie* przeszły walidację, następuje atomic rename w pętli. Jeśli cokolwiek fails — tempfiles się kasuje, docelowe pliki nietknięte.

### Atomic transaction

```python
# redeploy/version/transaction.py

class VersionBumpTransaction:
    def __init__(self, manifest: VersionManifest, new_version: str):
        self.manifest = manifest
        self.new_version = new_version
        self.staged: list[tuple[Path, Path]] = []  # (temp, final)

    def prepare(self) -> list[StagingResult]:
        """Stage wszystkie zmiany w tempfiles. Nie tyka docelowych."""
        results = []
        for source in self.manifest.sources:
            adapter = get_adapter(source.format)
            try:
                temp = adapter.stage(source.path, source, self.new_version)
                self.staged.append((temp, source.path))
                results.append(StagingResult(source, ok=True))
            except Exception as e:
                results.append(StagingResult(source, ok=False, error=e))
        return results

    def commit(self) -> None:
        """Atomic rename — jeśli cokolwiek przeszło prepare(), commit powinien nie failować."""
        for temp, final in self.staged:
            os.replace(temp, final)  # atomic na POSIX

    def rollback(self) -> None:
        """Usuń tempfiles, docelowe pliki nietknięte."""
        for temp, _ in self.staged:
            temp.unlink(missing_ok=True)
```

Wzorzec prepare/commit/rollback jest istotny — daje semantykę dwufazowego commitu bez potrzeby transakcji plikowych na poziomie systemu.

## 5. Surface CLI

```bash
# Odczyt
redeploy version                     # short: current version
redeploy version current             # explicit
redeploy version verify              # check wszystkie sources są spójne
redeploy version list                # all sources + ich wartości

# Zapis
redeploy version bump patch          # 1.0.20 → 1.0.21
redeploy version bump minor          # 1.0.20 → 1.1.0
redeploy version bump major          # 1.0.20 → 2.0.0
redeploy version bump prerelease     # 1.0.20 → 1.0.21-rc.1
redeploy version bump --analyze      # determine from conventional commits
redeploy version set 1.2.3           # explicit set

# Dry-run wszędzie
redeploy version bump patch --dry-run

# Git integration flags
redeploy version bump patch --tag --commit --push
redeploy version bump patch --no-tag  # skip git tag
redeploy version bump patch --sign    # sign tag with GPG

# Changelog
redeploy version changelog --unreleased   # show nadchodzące zmiany
redeploy version changelog --prepare      # rewrite ## [Unreleased] → ## [1.0.21]

# Drift detection
redeploy version diff                                       # sources vs manifest current
redeploy version diff --live root@vps.example.com           # manifest vs live host
redeploy version diff --spec migration.yaml                 # manifest vs target.version
redeploy version diff --image ghcr.io/org/app:latest        # manifest vs image registry tag

# Monorepo
redeploy version bump patch --package backend   # tylko backend pakiet
redeploy version current --package frontend     # current of specific package
redeploy version list --all-packages            # wszystkie pakiety

# Init
redeploy version init                           # generuj .redeploy/version.yaml
redeploy version init --scan                    # auto-detect źródła w projekcie
```

## 6. Integracja z deploy pipeline — pętla zamknięta

**Kluczowy argument dla systemowego podejścia:** redeploy już ma `version_check`. Manifest zamyka pętlę.

### Preflight: `redeploy run` z manifestem

Jeśli `.redeploy/version.yaml` istnieje w cwd, `redeploy run` dodaje implicit kroki:

```text
1. Read manifest → declared_version
2. Read migration.yaml → target.version
3. IF declared != target → FAIL "Version drift: manifest says 1.0.21, spec says 1.0.20"
4. IF git HEAD != tag for declared_version → WARN "HEAD not tagged for 1.0.21"
5. Standard detect → plan → apply
6. After apply: probe live version, compare to declared_version
7. IF mismatch → rollback
```

Ten flow **wcześniej** wyłapuje „zapomniałem bumpnąć migration.yaml" niż to robi obecny `version_check` (który sprawdza dopiero po deployu).

### `migration.yaml` może referować manifest

Zamiast hardkodowanego `version:`, można odwołać się do manifest:

```yaml
target:
  host: root@vps.example.com
  version: "@manifest"
  verify_version: "@manifest"
```

Albo explicit dla pinowanych deploy'ów:

```yaml
target:
  version: "1.0.20"
  version_check_against: manifest
```

### `redeploy detect --with-version`

Probe wersji na live host porównany z manifest:

```bash
redeploy detect --host root@vps.example.com --app c2004 --with-version

# Output:
# Host:     root@vps.example.com
# App:      c2004
# Runtime:  docker
# Services: c2004-backend, c2004-frontend
# Version comparison:
#   Manifest (local):    1.0.21
#   Running (live):      1.0.20   ⚠ drift
#   Image tag registry:  1.0.21
#   → Deploy pending (manifest > running)
```

## 7. Git integration jako first-class

Większość „bump scriptów" traktuje git jako afterthought. W naszym planie tag + commit + changelog to integralna część transakcji.

### Rozszerzona transakcja

```text
1. prepare() — stage wszystkie version sources (tempfiles)
2. prepare_changelog() — stage CHANGELOG.md z nową sekcją
3. require_clean() — git status porcelain, fail if dirty
4. commit_files() — os.replace wszystkie tempfiles
5. git_add() — add wszystkie touched files
6. git_commit() — commit z manifest.git.commit_message.format(version=new)
7. git_tag() — create annotated (signed jeśli manifest.git.sign_tag)
8. IF error na krokach 4–7 → rollback last successful step

Opcjonalny krok 9 (if --push):
9. git push --follow-tags
```

### Require clean working dir

`manifest.git.require_clean: true` → bump odmawia jeśli `git status --porcelain` niepuste. Chroni przed:

- zacommitowaniem przypadkowych zmian w ramach bump
- bumpem na niestabilnym kodzie
- race condition z innymi zmianami

Flaga `--allow-dirty` dla świadomego obejścia (np. staged conflicts).

### Changelog generation

Dla `manifest.changelog.format: keepachangelog`:

```markdown
# Changelog

## [Unreleased]

### Added
- Parser for docker-compose files (#142)

### Fixed
- k3s iptables flush race condition (#156)

## [1.0.20] — 2026-04-15
...
```

Po `redeploy version bump patch`:

```markdown
# Changelog

## [Unreleased]

## [1.0.21] — 2026-04-20

### Added
- Parser for docker-compose files (#142)

### Fixed
- k3s iptables flush race condition (#156)

## [1.0.20] — 2026-04-15
...
```

Opcjonalnie `--auto-sections` wyciąga sekcje z conventional commits od ostatniego tagu.

## 8. Conventional commits integration

`redeploy version bump --analyze` czyta commity od ostatniego tagu:

```python
# redeploy/version/commits.py

def analyze(since_tag: str, manifest: VersionManifest) -> BumpAnalysis:
    commits = git.log(f"{since_tag}..HEAD", format="%H %s%n%b")
    bumps = []
    for c in commits:
        parsed = parse_conventional(c.message)
        if parsed.breaking or "BREAKING CHANGE" in c.body:
            bumps.append("major")
        elif parsed.type in manifest.commits.rules:
            bumps.append(manifest.commits.rules[parsed.type])

    # Highest wins
    if "major" in bumps: return BumpAnalysis("major", ...)
    if "minor" in bumps: return BumpAnalysis("minor", ...)
    if "patch" in bumps: return BumpAnalysis("patch", ...)
    return BumpAnalysis(None, reason="no bump-worthy commits")
```

Output:

```bash
$ redeploy version bump --analyze --dry-run

Analysis: 14 commits since v1.0.20
  → 2× feat (minor)
  → 7× fix (patch)
  → 1× feat! (breaking → major)
  → 4× chore (ignored)

Proposed bump: major
Next version: 2.0.0

Files to update:
  VERSION                        1.0.20 → 2.0.0
  pyproject.toml                 1.0.20 → 2.0.0
  packages/backend/__init__.py   1.0.20 → 2.0.0
  ...13 files total

Run without --dry-run to apply.
```

## 9. Monorepo — studium przypadku c2004

Obecny stan c2004: `bump-version.py` updateuje 13 plików. Po migracji na manifest:

```yaml
# c2004/.redeploy/version.yaml
version:
  current: "1.0.20"
  scheme: semver
  policy: synced

  sources:
    - path: VERSION
      format: plain
    - path: pyproject.toml
      format: toml
      key: project.version
    - path: packages/backend/pyproject.toml
      format: toml
      key: project.version
    - path: packages/frontend/package.json
      format: json
      key: version
    - path: packages/frontend/src/version.ts
      format: regex
      pattern: 'export const VERSION = "([^"]+)"'
    - path: firmware/include/version.h
      format: regex
      pattern: '#define\s+FW_VERSION\s+"([^"]+)"'
    - path: docker-compose.vps.yml
      format: yaml
      key: services.backend.image
      value_pattern: '.*:v?(.+)'
      write_pattern: 'ghcr.io/softreck/c2004-backend:v{version}'
    - path: helm/Chart.yaml
      format: yaml
      key: version
    - path: helm/Chart.yaml
      format: yaml
      key: appVersion
    # ... pozostałe 4

  git:
    tag_format: "v{version}"
    require_clean: true

  changelog:
    path: CHANGELOG.md
    format: keepachangelog
```

Istniejący `scripts/bump-version.py` i `.github/workflows/release.yml` znikają. Komendy:

```bash
# Zamiast: python scripts/bump-version.py patch
redeploy version bump patch

# Zamiast: custom GHA workflow
# Wystarczy:
#   - run: redeploy version bump --analyze
#   - run: git push --follow-tags
```

Zysk: identyczna komenda w redeploy (2 source) i c2004 (13 sources). Nowe repo dziedziczy mechanizm za darmo, tylko pisze `.redeploy/version.yaml`.

## 10. Porównanie z istniejącymi narzędziami

| Narzędzie | Co robi | Czego brakuje vs nasz plan |
|---|---|---|
| `bump2version` / `bumpversion` | Multi-file version update przez regex | Brak integracji z deploy, brak atomowej transakcji, brak monorepo policy |
| `poetry version` | TOML-only | Single-file, brak multi-source |
| `npm version` | package.json + git tag | JS-only, brak multi-source |
| `semantic-release` | Conventional commits → auto release | Wymaga node, dużo plugins, brak integracji z live host verification |
| `release-please` (Google) | PR-based release automation | GitHub-specific, złożony, brak loop z deployem |
| `changesets` | Manual changelog entries | Manual, brak auto-bump |
| `git-version-bump` | Git-based versioning | Brak multi-file, brak changelogu |
| Helm `appVersion` vs `version` | Rozdzielenie chart/app version | Helm-specific |
| Terraform `required_version` | Version constraints | Nie bumpuje, tylko enforce |

**Kluczowa różnica naszego planu:** żaden z powyższych nie zamyka pętli z **live deployment verification**. redeploy to zrobi, bo już ma `version_check` i probe. Manifest domyka brakującą połowę cyklu.

### Co można pożyczyć

- **Conventional commits parser** — `conventional-commits-parser` (node) lub `commitizen` (python) jako wzorzec
- **keepachangelog format** — ustandaryzowany, łatwy do generowania
- **Keep sync policy** z changesets — prosty model dla monorepo

### Co robimy inaczej

- **Nie wymagamy CI runnera** — wszystko działa z CLI lokalnie, CI to opcja
- **Nie generujemy kodu** — manifest opisuje *gdzie* jest wersja, nie *jak* ją stworzyć
- **Integrujemy z deploy** — bump nie jest celem sam w sobie, jest częścią łańcucha release → deploy → verify

## 11. Migration path dla istniejących projektów

### Krok 1: `redeploy version init --scan`

Komenda skanuje projekt i proponuje manifest:

```bash
$ cd c2004
$ redeploy version init --scan

Skanowanie projektu...
Znalezione potencjalne version sources:
  [✓] VERSION (plain)                     current: 1.0.20
  [✓] pyproject.toml (toml, project.version)   current: 1.0.20
  [✓] packages/backend/pyproject.toml     current: 1.0.20
  [✓] packages/frontend/package.json      current: 1.0.20
  [✓] packages/frontend/src/version.ts    current: 1.0.20 (regex match)
  [✓] firmware/include/version.h          current: 1.0.20 (regex match)
  [?] docker-compose.vps.yml              image tag: v1.0.20 (niepewne)
  [?] README.md                           badge version: 1.0.20
  [!] legacy/VERSION.txt                  current: 0.9.5 (rozjazd!)

Czy zapisać do .redeploy/version.yaml? [Y/n]
```

Użytkownik akceptuje, edytuje `[?]` (dodaje/usuwa), rozstrzyga `[!]` (conflict).

### Krok 2: `redeploy version verify`

```bash
$ redeploy version verify

Manifest current: 1.0.20
Source check:
  VERSION                          1.0.20  ✓
  pyproject.toml                   1.0.20  ✓
  packages/backend/pyproject.toml  1.0.20  ✓
  ...
All sources in sync: ✓

Git check:
  HEAD tagged as v1.0.20:          ✓
  Working directory clean:         ✓
```

### Krok 3: Usunięcie starych skryptów

```bash
$ rm scripts/bump-version.py
$ rm .github/workflows/release.yml  # jeśli zastępowany
```

### Krok 4: Kolejny bump używa redeploy

```bash
$ redeploy version bump patch --analyze
```

## 12. Fazy implementacji

### Faza 0 — Manifest + źródła plain/TOML (1.5 tygodnia)

- `VersionManifest` pydantic model + walidacja
- `SourceAdapter` protocol
- Adapters: `plain`, `toml`
- CLI: `version current`, `version list`, `version verify`
- Testy na redeploy własnym (2 źródła)

### Faza 1 — Pozostałe source adapters (1.5 tygodnia)

- `json`, `yaml`, `regex`, `dockerfile`
- Edge cases: YAML value_pattern + write_pattern (docker-compose image tags)
- Testy na sample projektach

### Faza 2 — Transakcja atomowa + bump (1.5 tygodnia)

- `VersionBumpTransaction` z prepare/commit/rollback
- CLI: `version bump patch|minor|major`, `version set X.Y.Z`
- Semver scheme
- Dry-run mode
- Testy na c2004 (13 źródeł)

### Faza 3 — Git integration (1 tydzień)

- `require_clean`, `--tag`, `--commit`, `--push`, `--sign`
- Staging git changes jako część transakcji
- Error handling gdy git operations fail mid-transaction

### Faza 4 — Conventional commits + changelog (1.5 tygodnia)

- Commit parser
- `--analyze` flag
- Changelog generator (keepachangelog)
- `version changelog --prepare`

### Faza 5 — Deploy loop closure (1 tydzień)

- `target.version: "@manifest"` w migration.yaml
- Preflight check w `redeploy run`
- `redeploy detect --with-version`
- `redeploy version diff --live/--spec/--image`

### Faza 6 — Monorepo policy (1 tydzień)

- `packages:` struktura w manifest
- `--package` flag
- Policy `synced` vs `independent`
- Cross-package constraints (basic)

### Faza 7 — Init/scan + docs (1 tydzień)

- `version init --scan` heurystyka
- Import z bumpversion / poetry config
- Dokumentacja migration per format

**Suma:** ok. 10 tygodni dla pełnego scope. MVP (fazy 0–3) w 5.5 tygodnia.

## 13. Ryzyka i decyzje do podjęcia

| Ryzyko | Prawdopodobieństwo | Mitygacja |
|---|---|---|
| YAML source adapter psuje formatting (komentarze, quoting) | **Wysokie** | `ruamel.yaml` z round-trip zamiast PyYAML dla zapisu |
| Regex adapter fails silently | Średnie | Hard-fail przy `optional: false`, testy negatywne |
| Transakcja atomowa nie jest atomic przez NFS / sieciowe FS | Niskie | Dokumentacja: wymagane lokalne FS z `os.replace` |
| `--analyze` ma false positives (np. commit z "fix" w tytule ale nie fix) | Średnie | Tylko header commita, nie body; flagi `--force-type` |
| Git sign tag wymaga interaktywnego prompt (GPG) | Średnie | Obsługa `GPG_TTY`, dokumentacja |
| Istniejące projekty mają niestandardowe bump scripts | Wysokie | `init --scan` + `--import-from bumpversion.cfg` |
| Podwójny update YAML (Chart.yaml ma `version` + `appVersion`) | Średnie | Manifest pozwala na wiele entry na ten sam plik |

### Otwarte decyzje przed implementacją

1. **Default scheme:** semver hard-coded jako default, czy explicit required?
2. **Location manifest:** `.redeploy/version.yaml` czy `redeploy.yaml` top-level key `version:`?
3. **Relacja do części II (parsers):** czy parser docker-compose automatycznie emituje source entry dla image tag?
4. **Fallback dla projektów bez manifest:** best-effort detection jak obecny `probe_version`, czy require manifest?
5. **Breaking changes detection:** `!` po typie (`feat!`) tylko, czy też `BREAKING CHANGE:` footer?

Rekomendacja autora: semver default, `.redeploy/version.yaml` (pozwala gitignore per użytkownika jeśli lokalne), parser z cz. II sugeruje source entry ale nie auto-dodaje, fallback best-effort z WARN, oba sposoby breaking.

## 14. Kryteria sukcesu

Po zakończeniu faz 0–5 (MVP + git + commits + deploy loop):

- `redeploy version bump patch` działa identycznie na redeploy (2 sources) i c2004 (13 sources)
- `redeploy version verify` wyłapuje rozjazdy między sources
- `redeploy run` w repo z manifest odmawia deployu przy rozjeździe `spec.version ↔ manifest.current`
- `redeploy version diff --live` pokazuje drift między declared a running
- Changelog auto-generowany z conventional commits
- Zero nowych wymaganych dependencji (PyYAML, tomllib stdlib już są)
- Istniejące `scripts/bump-version.py` w c2004 można usunąć bez utraty funkcjonalności

## 15. Co NIE jest w tym planie

Świadomie odkładamy:

- **Dependency version management** (jak NPM lock, Cargo.lock) — to inny problem
- **Version constraint resolution** między paczkami — zaawansowany monorepo scope, po v1.0
- **Release automation na PyPI/npm** — tylko tag + commit, publikacja zostaje w user's pipeline
- **Backward compat z bumpversion / semantic-release configs** — `init --import-from` tylko best-effort
- **Semver range parsing** (`>=1.0,<2.0`) — tylko w `constraints:`, nie w daily bump flow
- **Web UI / dashboard** — CLI only
- **Signing commits** (nie tylko tags) — tylko tags w v1

## 16. Mapa zależności z innymi częściami

| Ta część | Część I (internal) | Część II (parsers) |
|---|---|---|
| Manifest schema | Fleet model (faza 2) — osobne rzeczy, ale podobny wzorzec pydantic | |
| `@manifest` w migration.yaml | Public API (faza 1) — manifest musi być w public API | |
| Source adapter `yaml` + `dockerfile` | | Część II ma parsery dla tych formatów — **współdzielenie kodu** |
| Deploy preflight | Patterns (faza 4 cz. I) — preflight to nowy „pattern" | |
| Live version probe | `probe_health` (istniejące) — rozszerzenie o `probe_version` | |

**Kluczowe:** źródła (sources) z tej części i parsery z części II mogą współdzielić YAML / TOML / JSON readers. Warto najpierw zaprojektować wspólną warstwę `redeploy/formats/` zanim obie części ruszą.

## 17. Następne kroki

1. **Walidacja planu** — przegląd z kontrybutorami, 1 tydzień
2. **Decyzja lokacji manifest** — `.redeploy/version.yaml` vs top-level key
3. **Spike Faza 0** — implementacja dla redeploy-self (2 sources, trivial) jako proof
4. **Koordynacja z cz. II** — wspólna warstwa `formats/`
5. **Milestone w GitHub** — per faza, z trackingiem MVP (0–3) i full (0–7)

---

*Plany powiązane:*
- *Część I: [redeploy — plan refaktoryzacji (internal)](./REFACTORING.md)*
- *Część II: [redeploy — plan integracji z IaC/CI-CD (parsery)](./docs/parsers/README.md)*
- *doql: doql — plan refaktoryzacji (poza bieżącym workspace)*
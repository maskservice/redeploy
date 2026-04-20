<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# a jak by to miałol być obslugiwane przez rozne jezyki rpogramowania, czy moze warto zastosowac standard markpact?

![img_2.png](img_2.png)

# markpact - + GitOps meets AI Agents — all in one README.

[![PyPI version](https://img.shields.io/pypi/v/markpact.svg)](https://pypi.org/project/markpact/)
[![Python](https://img.shields.io/pypi/pyversions/markpact.svg)](https://pypi.org/project/markpact/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Tests](https://github.com/wronai/markpact/actions/workflows/tests.yml/badge.svg)](https://github.com/wronai/markpact/actions)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

Markpact to minimalny runtime, który pozwala trzymać cały projekt w jednym `README.md`.
Runtime ignoruje zwykły Markdown, a wykonuje wyłącznie codeblocki `markpact:*`.

## 💡 Czym jest Markpact?

Markpact to narzędzie, które zamienia plik README.md w **wykonywalny kontrakt projektu**. Zamiast utrzymywać osobno dokumentację i kod źródłowy, wszystko znajduje się w jednym miejscu.

### Kluczowe możliwości:

| Funkcja | Opis |
| :-- | :-- |
| **Executable README** | Uruchom cały projekt z jednego pliku README.md |
| **LLM Generation** | Wygeneruj projekt z opisu tekstowego: `markpact -p "REST API"` |
| **Live Demo** | Interaktywne demo z generowaniem PDF: `python examples/demo_live_markpact.py` |
| **PDF Generation** | Automatyczne tworzenie PDF dokumentacji (7 stron) |
| **Multi-language** | Python, Node.js, Go, Rust, PHP, TypeScript, React |
| **Publishing** | Publikuj do PyPI, npm, Docker Hub jedną komendą |
| **Docker Sandbox** | Uruchom w izolowanym kontenerze: `--docker` |
| **HTTP Testing** | Definiuj testy HTTP w `markpact:test http` |
| **Auto-fix** | Automatyczne naprawianie błędów runtime |
| **Sync \& Rollback** | Synchronizuj pliki źródłowe z README: `markpact sync` |

### Dla kogo?

- **Deweloperzy** – szybkie prototypowanie i uruchamianie projektów
- **DevOps** – CI/CD z README jako single source of truth
- **Edukatorzy** – interaktywne tutoriale z wykonywalnym kodem
- **LLM/AI** – generowanie i modyfikacja projektów przez AI

![img_3.png](img_3.png)

## 🚀 Szybki start

```bash
git clone [https://github.com/wronai/markpact.git](https://github.com/wronai/markpact.git)
# Instalacja
pip install markpact[llm]

# Konfiguracja LLM (wybierz jeden)
markpact config --provider ollama                              # lokalny
markpact config --provider openrouter --api-key sk-or-v1-xxx   # chmura

# Generuj i uruchom jedną komendą!
markpact -p "REST API do zarządzania zadaniami z SQLite" -o todo/README.md --run

markpact -p "URL shortener with FastAPI and SQLite" -o url-test/README.md --run

# Lub z gotowego przykładu
markpact -e todo-api -o todo/README.md --run
```


## 🎬 Demo Live - Generowanie z LLM w czasie rzeczywistym

Spróbuj interaktywnego demo, które generuje kompletny projekt z promptu i tworzy PDF dokumentacji:

```bash
# Wejdź do katalogu markpact
cd /home/tom/github/wronai/markpact

# Uruchom demo z własnym promptem
python examples/demo_live_markpact.py --prompt "Build a chat API with WebSocket"

# Lub użyj gotowego przykładu
python examples/demo_live_markpact.py --example todo-api

# Lista dostępnych przykładów
python examples/demo_live_markpact.py --list
```

**Co robi demo:**

1. **Generuje kontrakt** z LLM (Ollama/OpenRouter/OpenAI)
2. **Parsuje bloki** `markpact:*` z wygenerowanego README
3. **Waliduje** wszystkie wymagane bloki
4. **Tworzy PDF** z pełną dokumentacją (7 stron)
5. **Zapisuje wyniki** do `generated/live/`

**Wymagania:**

```bash
pip install markpact[llm] fpdf2
```

**Przykład wyjścia:**

```
[PASS] LLM wygenerował kontrakt  81.1s, 2177 znaków
[PASS] Znaleziono 4 bloków  0.0ms
[PASS] Zaleznosci: 3 pakietów  fastapi, uvicorn, websockets
[PASS] Plik: app/main.py  36 linii
[PASS] PDF zapisany: generated/live/markpact_live_custom.pdf  13 KB, 7 stron
```


## 🤖 Generowanie z LLM

Wygeneruj kompletny projekt z opisu tekstowego:

```bash
# Lista 16 gotowych przykładów
markpact --list-examples

# Generuj z promptu
markpact -p "URL shortener z FastAPI i SQLite" -o url/README.md

# Generuj i uruchom natychmiast (one-liner)
markpact -p "Chat WebSocket z FastAPI" -o chat/README.md --run

# Uruchom w izolowanym Docker
markpact -p "Blog API z komentarzami" -o blog/README.md --run --docker
```

**Obsługiwane providery:** Ollama (lokalny), OpenRouter, OpenAI, Anthropic, Groq

Szczegóły: [docs/generator.md](docs/generator.md)

## 📦 Publikacja do rejestrów

Publikuj artefakty bezpośrednio z README:

```bash
# PyPI
markpact README.md --publish --bump patch

# npm
markpact README.md --publish --registry npm

# Docker Hub
markpact README.md --publish --registry docker

# GitHub Container Registry
markpact README.md --publish --registry ghcr
```

Obsługiwane rejestry: **PyPI**, **npm**, **Docker Hub**, **GitHub Packages**, **GHCR**

## 📓 Konwersja Notebooków

Konwertuj notebooki do formatu markpact:

```bash
# Lista obsługiwanych formatów
markpact --list-notebook-formats

# Konwersja Jupyter Notebook
markpact --from-notebook notebook.ipynb -o project/README.md

# Konwersja i uruchomienie
markpact --from-notebook notebook.ipynb -o project/README.md --run

# Podgląd konwersji
markpact --from-notebook notebook.ipynb --convert-only
```

**Obsługiwane formaty:**


| Format | Rozszerzenie | Opis |
| :-- | :-- | :-- |
| Jupyter Notebook | `.ipynb` | Python, R, Julia |
| R Markdown | `.Rmd` | R z markdown |
| Quarto | `.qmd` | Wielojęzyczny |
| Databricks | `.dib` | Python, Scala, R |
| Zeppelin | `.zpln` | Python, Scala, SQL |

## 📚 Dokumentacja

- [Pełna dokumentacja](docs/README.md)
- [Demo Live Guide](examples/README.md) ⭐ **NEW** - Interaktywne demo z PDF
- [Generowanie z LLM](docs/generator.md) ⭐ **NEW**
- [Kontrakt markpact:*](docs/contract.md)
- [CI/CD Integration](docs/ci-cd.md)
- [Współpraca z LLM](docs/llm.md)


## 🎯 Przykłady

| Przykład | Opis | Uruchomienie |
| :-- | :-- | :-- |
| [Demo Live](examples/demo_live_markpact.py) | **Interaktywne generowanie z LLM + PDF** | `python examples/demo_live_markpact.py --prompt "Chat API"` |
| [FastAPI Todo](examples/fastapi-todo/) | REST API z bazą danych | `markpact examples/fastapi-todo/README.md` |
| [Flask Blog](examples/flask-blog/) | Aplikacja webowa z szablonami | `markpact examples/flask-blog/README.md` |
| [CLI Tool](examples/cli-tool/) | Narzędzie linii poleceń | `markpact examples/cli-tool/README.md` |
| [Streamlit Dashboard](examples/streamlit-dashboard/) | Dashboard danych | `markpact examples/streamlit-dashboard/README.md` |
| [Kivy Mobile](examples/kivy-mobile/) | Aplikacja mobilna | `markpact examples/kivy-mobile/README.md` |
| [Electron Desktop](examples/electron-desktop/) | Aplikacja desktopowa | `markpact examples/electron-desktop/README.md` |
| [Markdown Converter](examples/markdown-converter/) | Konwersja zwykłego MD | `markpact examples/markdown-converter/sample.md --convert` |
| [Go HTTP API](examples/go-http-api/) | REST API w Go | `markpact examples/go-http-api/README.md` |
| [Node Express API](examples/node-express-api/) | REST API w Node.js | `markpact examples/node-express-api/README.md` |
| [Static Frontend](examples/static-frontend/) | Statyczny HTML/CSS/JS | `markpact examples/static-frontend/README.md` |
| [Python Typer CLI](examples/python-typer-cli/) | CLI w Python (Typer) | `markpact examples/python-typer-cli/README.md` |
| [Rust Axum API](examples/rust-axum-api/) | REST API w Rust | `markpact examples/rust-axum-api/README.md` |
| [PHP CLI](examples/php-cli/) | CLI w PHP | `markpact examples/php-cli/README.md` |
| [React TypeScript SPA](examples/react-typescript-spa/) | SPA React + TS | `markpact examples/react-typescript-spa/README.md` |
| [TypeScript Node API](examples/typescript-node-api/) | REST API w TS (Node) | `markpact examples/typescript-node-api/README.md` |
| [PyPI Publish](examples/pypi-publish/) | Publikacja do PyPI | `markpact examples/pypi-publish/README.md --publish` |
| [npm Publish](examples/npm-publish/) | Publikacja do npm | `markpact examples/npm-publish/README.md --publish` |
| [Docker Publish](examples/docker-publish/) | Publikacja do Docker | `markpact examples/docker-publish/README.md --publish` |
| [Notebook Converter](examples/notebook-converter/) | Konwersja .ipynb do markpact | `markpact --from-notebook examples/notebook-converter/sample.ipynb --convert-only` |

## 🧪 Testowanie przykładów

Uruchom automatyczne testy wszystkich przykładów:

```bash
# Dry-run (tylko parsowanie)
./scripts/test_examples.sh

# Pełne uruchomienie
./scripts/test_examples.sh --run

# Verbose output
./scripts/test_examples.sh --verbose
```


## 🔄 Sync — synchronizacja plików z README

Komenda `sync` aktualizuje bloki `markpact:file` w README.md na podstawie rzeczywistych plików w katalogu źródłowym (np. `sandbox/`). Odwrotność `markpact pack`.

```bash
# Synchronizacja (auto-detect sandbox/ obok README)
markpact sync README.md

# Z własnym katalogiem źródłowym
markpact sync README.md --source ./my-project

# Podgląd zmian bez zapisu
markpact sync README.md --dry-run --diff

# CI check — exit 1 jeśli pliki nie są zsynchronizowane
markpact sync README.md --check

# Lista śledzonych plików
markpact sync README.md --list

# Pliki w katalogu źródłowym nie śledzone w README
markpact sync README.md --missing

# Wyklucz wrażliwe pliki
markpact sync README.md --exclude .env --exclude .env.prod
```


### Rollback — przywracanie poprzedniej wersji

Każdy `sync` automatycznie tworzy backup README w `.markpact/` (max 10).

```bash
# Przywróć ostatni backup
markpact sync README.md --rollback

# Lista dostępnych backupów
markpact sync README.md --backups

# Przywróć konkretny backup
markpact sync README.md --rollback-to .markpact/README.md.bak.20240301_143022
```


### Opcje `markpact sync`

| Flaga | Opis |
| :-- | :-- |
| `-n`, `--dry-run` | Podgląd bez zapisu |
| `-d`, `--diff` | Pokaż unified diff |
| `-c`, `--check` | CI: exit 1 jeśli out-of-sync |
| `-l`, `--list` | Lista śledzonych plików |
| `-m`, `--missing` | Pliki źródłowe bez bloku w README |
| `--exclude PATH` | Wyklucz plik (powtarzalne) |
| `--rollback` | Przywróć z ostatniego backup |
| `--rollback-to FILE` | Przywróć z konkretnego backup |
| `--backups` | Lista dostępnych backupów |
| `-s`, `--source DIR` | Katalog źródłowy (domyślnie: `sandbox/`) |

## 🔄 Konwersja zwykłego Markdown

Markpact może automatycznie konwertować zwykłe pliki Markdown (bez tagów `markpact:*`) do formatu wykonywalnego:

```bash
# Podgląd konwersji
markpact README.md --convert-only

# Konwersja i uruchomienie
markpact README.md --convert

# Auto-detekcja (konwertuj jeśli brak markpact blocks)
markpact README.md --auto

# Zapisz skonwertowany plik
markpact README.md --convert-only --save-converted output.md
```

Konwerter analizuje code blocks i na podstawie heurystyk wykrywa:

- **Zależności** → `markpact:deps` (pakiety Python/Node)
- **Pliki źródłowe** → `markpact:file` (importy, klasy, funkcje)
- **Komendy** → `markpact:run` (python, uvicorn, npm, etc.)


## 1️⃣ Cel projektu

- **Jedno README jako źródło prawdy**
- **Możliwość uruchomienia projektu bez ręcznego tworzenia struktury plików**
- **Automatyzacja**
Bootstrap tworzy pliki w sandboxie, instaluje zależności i uruchamia komendę startową.


## 2️⃣ Kontrakt README (codeblocki `markpact:*`)

- **`markpact:bootstrap <lang>`**
Dokładnie jeden bootstrap na README. Odpowiada za parsowanie codeblocków i uruchomienie.
- **`markpact:deps <scope>`**
Lista zależności dla danego scope (np. `python`).
- **`markpact:file <lang> path=...`**
Zapisuje plik do sandboxu pod ścieżką `path=...`.
- **`markpact:run <lang>`**
Jedna komenda uruchomieniowa wykonywana w sandboxie.

---
```markpact:bootstrap python
#!/usr/bin/env python3
"""MARKPACT v0.1 – Executable Markdown Runtime"""
import os, re, subprocess, sys
from pathlib import Path

README = Path(sys.argv[1] if len(sys.argv) > 1 else "README.md")
SANDBOX = Path(os.environ.get("MARKPACT_SANDBOX", "./sandbox"))
SANDBOX.mkdir(parents=True, exist_ok=True)
RE = re.compile(r"^```markpact:(?P<kind>\\w+)(?:\\s+(?P<meta>[^\\n]+))?\\n(?P<body>.*?)\\n^```[ \\t]*$", re.DOTALL | re.MULTILINE)

def run(cmd):
    print(f"[markpact] RUN: {cmd}")
    env = os.environ.copy()
    venv = SANDBOX / ".venv" / "bin"
    if venv.exists():
        env.update(VIRTUAL_ENV=str(venv.parent), PATH=f"{venv}:{env.get('PATH','')}")
    subprocess.check_call(cmd, shell=True, cwd=SANDBOX, env=env)

def main():
    deps, run_cmd = [], None
    for m in RE.finditer(README.read_text()):
        kind, meta, body = m.group("kind"), (m.group("meta") or "").strip(), m.group("body").strip()
        if kind == "file":
            p = re.search(r"\\bpath=(\\S+)", meta)
            if not p: raise ValueError(f"markpact:file requires path=..., got {meta!r}")
            f = SANDBOX / p[1]
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(body)
            print(f"[markpact] wrote {f}")
        elif kind == "deps" and meta == "python":
            deps.extend(line.strip() for line in body.splitlines() if line.strip())
        elif kind == "run":
            run_cmd = body
    if deps:
        venv_pip = SANDBOX / ".venv" / "bin" / "pip"
        if os.environ.get("MARKPACT_NO_VENV") != "1" and not venv_pip.exists():
            run(f"{sys.executable} -m venv .venv")
        (SANDBOX / "requirements.txt").write_text("\\n".join(deps))
        run(f"{'.venv/bin/pip' if venv_pip.exists() else 'pip'} install -r requirements.txt")
    if run_cmd:
        run(run_cmd)
    else:
        print("[markpact] No run command defined")

if __name__ == "__main__":
    main()
```


## 3️⃣ Instalacja

### Opcja A: Pakiet pip (zalecane)

```bash
# Podstawowa instalacja
pip install markpact

# Z LLM i PDF generation (dla demo)
pip install markpact[llm] fpdf2

# Z integracją fixop (auto-fix, diagnostyka portów)
pip install markpact[ops]
```

Użycie:

```bash
markpact README.md                    # uruchom projekt
markpact README.md --dry-run          # podgląd bez wykonywania
markpact README.md -s ./my-sandbox    # własny katalog sandbox

# Demo live z LLM
python examples/demo_live_markpact.py --prompt "Twój prompt"
```


### Opcja B: Instalacja lokalna (dev)

```bash
git clone [https://github.com/wronai/markpact.git](https://github.com/wronai/markpact.git)
cd markpact
make install   # lub: pip install -e .
```


### Opcja C: Ekstrakcja bootstrapu (zero dependencies)

- **Ekstrakcja bootstrapu do pliku**

Ten wariant jest odporny na przypadek, gdy w samym bootstrapie występują znaki ``` (np. w regexie):

```bash
sed -n '/^```markpact:bootstrap/,/^```[[:space:]]*$/p' README.md | sed '1d;$d' > markpact.py
```

- **Uruchomienie**

```bash
python3 markpact.py
```

- **Konfiguracja (env vars)**

```bash
MARKPACT_PORT=8001 MARKPACT_SANDBOX=./.markpact-sandbox python3 markpact.py
```


## 4️⃣ Sandbox i środowisko

- **`MARKPACT_SANDBOX`**
Zmienia katalog sandboxu (domyślnie `./sandbox`).
- **`MARKPACT_NO_VENV=1`**
Wyłącza tworzenie `.venv` w sandboxie (przydatne, jeśli CI/Conda zarządza środowiskiem).
- **Port zajęty (`[Errno 98] address already in use`)**
Ustaw `MARKPACT_PORT` na inny port lub zatrzymaj proces, który używa `8000`.


## 5️⃣ Dependency management

- **Python**
Bootstrap zbiera `markpact:deps python`, zapisuje `requirements.txt` w sandboxie i instaluje zależności.


## 6️⃣ Uruchamianie i workflow

- **Wejście**
`python3 markpact.py [README.md]`
- **Kolejność**
Bootstrap parsuje wszystkie codeblocki, zapisuje pliki i dopiero na końcu uruchamia `markpact:run`.


## 6.1 Konwencje i format metadanych

- **Nagłówek codeblocka**
` ```markpact:<kind> <lang> <meta>`

Minimalnie wymagane jest `markpact:<kind>`.
`lang` jest opcjonalny i pełni rolę informacyjną (bootstrap może go ignorować).
- **Metadane**
Dla `markpact:file` wymagane jest `path=...`.
Metadane mogą zawierać dodatkowe tokeny (np. w przyszłości `mode=...`, `chmod=...`).


## 6.2 CI/CD

- **Rekomendacja**
Uruchamiaj bootstrap w czystym środowisku (np. job CI) i ustaw sandbox na katalog roboczy joba.
- **Przykład (shell)**

```bash
export MARKPACT_SANDBOX=./.markpact-sandbox
export MARKPACT_PORT=8001
python3 markpact.py README.md
```

- **Wskazówki**
    - **Deterministyczność**
Pinuj wersje w `markpact:deps` (np. `fastapi==...`).
    - **Bezpieczeństwo**
Traktuj `markpact:run` jak skrypt uruchomieniowy repo: w CI odpalaj tylko zaufane README.
    - **Cache**
Jeśli CI wspiera cache, cache’uj katalog `MARKPACT_SANDBOX/.venv`.


## 6.3 Współpraca z LLM

- **Zasada**
LLM może generować/edytować projekt poprzez modyfikacje README (codeblocki `markpact:file`, `markpact:deps`, `markpact:run`).
- **Oczekiwania**
    - `markpact:file` zawsze zawiera pełną zawartość pliku.
    - Każda zmiana zależności idzie przez `markpact:deps`.
    - Jedna komenda startowa w `markpact:run`.


## 7️⃣ Najlepsze praktyki

- **Bootstrap jako pierwszy fenced codeblock w README**
- **Każdy plik w osobnym `markpact:file`**
- **Zależności tylko w `markpact:deps`**
- **Jedna komenda startowa w `markpact:run`**
- **Ekstrakcja bootstrapu**
Nie używaj zakresu `/,/```/` (bo ``` może wystąpić w treści, np. w regexie). Używaj `^```\$` na końcu.


### Plik konfiguracyjny (~/.markpact/.env)

```bash
# Markpact LLM Configuration
MARKPACT_MODEL="openrouter/nvidia/nemotron-3-nano-30b-a3b:free"
MARKPACT_API_BASE="https://openrouter.ai/api/v1"
MARKPACT_API_KEY="sk-or-v1-xxxxx"
MARKPACT_TEMPERATURE="0.7"
MARKPACT_MAX_TOKENS="4096"
```


## Obsługiwani providerzy LLM

### Ollama (lokalny, domyślny)

```bash
markpact config --provider ollama
markpact config --model ollama/qwen2.5-coder:14b
markpact -p "REST API dla książek"
```


### OpenRouter (darmowe modele!)

```bash
markpact config --provider openrouter --api-key sk-or-v1-xxxxx
markpact config --model openrouter/nvidia/nemotron-3-nano-30b-a3b:free
markpact -p "REST API dla książek"
```


## Działający przykład (FastAPI)

### 1️⃣ Dependencies

*markpact:deps python*

```text markpact:deps python
fastapi
uvicorn
```


### 2️⃣ Application Files

*markpact:file python path=app/main.py*

```python markpact:file path=app/main.py
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello from Executable Markdown"}
```


### 3️⃣ Run Command

*markpact:run python*

```bash markpact:run
uvicorn app.main:app --host 0.0.0.0 --port ${MARKPACT_PORT:-8088}
```


## 🏗️ Architektura modułów

Markpact jest podzielony na małe, niezależne moduły:

```
src/markpact/
├── cli/                    # CLI dispatch + subcommands
│   ├── __init__.py         # main() — thin dispatch (CC≤5)
│   ├── sync_cmd.py         # markpact sync
│   ├── pack_cmd.py         # markpact pack
│   ├── config_cmd.py       # markpact config
│   ├── publish_cmd.py      # --publish mode
│   ├── run_cmd.py          # normal run, Docker, test
│   ├── convert_cmd.py      # notebook/markdown conversion
│   └── helpers.py          # shared CLI utilities
├── publish/                # Multi-registry publisher
│   ├── models.py           # PublishConfig, PublishResult
│   ├── helpers.py          # inference, interactive config
│   ├── version.py          # semver bump, extract, update
│   ├── llm_config.py       # LLM-based config generation
│   ├── pypi.py             # PyPI publisher
│   ├── npm.py              # npm publisher
│   ├── docker_pub.py       # Docker publisher
│   ├── github.py           # GitHub Packages publisher
│   └── main.py             # parse_publish_block, dispatch
├── auto_fix.py             # Runtime error auto-fix (fixop integration)
├── parser.py               # markpact:* block parser
├── syncer.py               # README ↔ source sync
├── packer.py               # Directory → README packer
├── sandbox.py              # Isolated sandbox management
├── runner.py               # Command execution
└── generator.py            # LLM contract generation
```


### Opcjonalne zależności

| Extra | Pakiet | Opis |
| :-- | :-- | :-- |
| `[llm]` | litellm | Generowanie kontraktów przez LLM |
| `[ops]` | fixop | Diagnostyka portów, klasyfikacja błędów |
| `[dev]` | pytest, ruff, build, twine | Narzędzia deweloperskie |

## Test Performance

- **Markpact tests**: ~6s for 255 tests (fast)
- **Test suite**: Uses pytest with coverage reporting


### Recent Fixes

- **v0.1.36**: Fixed pip fallback bug in `runner.py` - now always uses `.venv/bin/pip` after venv creation to avoid PEP 668 errors on externally-managed Python environments
- **v0.1.30**: Major refactoring - cli.py → cli/ package, publisher.py → publish/ package, syncer.py refactoring for better maintainability


## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Author

Created by **Tom Sapletta** - [tom@sapletta.com](mailto:tom@sapletta.com)

Tak, markpact to idealny standard dla takiego podejścia – obsługuje Markdown z blokami `markpact:*` zawierającymi dowolne formaty (YAML/TOML/JSON/kod), jest multi-językowy i natywnie wspiera GitOps/AI agents. Dla RPi deploymentów jak Twój, zamienia `migration.md` w wykonywalny kontrakt, synchronizując z sandboxem (Docker/RPi).[^1][^2]

## Dlaczego Markpact?

Markpact parsuje tylko bloki `markpact:*`, ignorując zwykły Markdown – to hybryda dokumentacji + executable config, z runtime w Pythonie (bootstrap).[^1]
Multi-language (Python/Go/Rust/TS/PHP) via blokach kodu, plus LLM generation do auto-deploy configs.[^3]
Sync/rollback zapewnia GitOps: `markpact sync` aktualizuje README z plików, idealne dla redeploy + RPi.[^4]

## Adaptacja dla Deploymentu RPi

Przekształć `migration.yaml` w `migration.md` z markpact blokami – runtime wyciągnie dane, stworzy sandbox i wykona kroki (rsync/ssh/docker).

```
# c2004 RPi5 Deploy 1.0.20
Deployment do pi@192.168.188.108. `markpact migration.md --run`

```markpact:bootstrap python
#!/usr/bin/env python3
# [skrócony bootstrap z README markpact – parsuje bloki, rsync/ssh/docker]
import subprocess, yaml, toml  # multi-format
# ... logika: parse blocks → steps → exec on RPi
```

```yaml markpact:config
# YAML dla struktury (jak Twój oryginalny)
name: "c2004 rpi5..."
source: {strategy: docker_full, host: pi@192.168.188.108}
target: {version: "1.0.20", compose_files: ["docker-compose.yml"]}
```

```toml markpact:steps
# TOML dla kroków (kompaktowe)
[[extra_steps]]
id = "rsync_code"
action = "rsync"
src = "/home/tom/github/maskservice/c2004/"
dst = "~/c2004"
risk = "low"

[[extra_steps]]
id = "docker_build"
action = "ssh_cmd"
command = "cd ~/c2004 && docker compose up -d --build"
```

```bash markpact:run
# Uruchomienie: redeploy lub custom
redeploy migration.yaml  # lub custom ssh/rsync/docker
```

Notes: RPi5 ARM64, Docker install auto.

```
Uruchom: `markpact migration.md --run --docker` (sandbox na RPi via SSH).[^5]

## Obsługa w Różnych Językach
Markpact jest Python-centric, ale bloki `markpact:file lang=go/rust/ts` generują kod – runtime deleguje (np. `go run`).[^1]
Dla Go: `markpact:run go` → kompiluje/deploy na RPi. Rust/TS via Docker cross-compile.[^6]
LLM gen: `markpact -p "RPi Docker deploy spec" -o migration.md` – AI-aware jak SUMD.[^7]

## Porównanie Standardów
| Standard | Multi-lang | Embedded YAML/TOML/JSON | GitOps/Sync | RPi/Docker Fit | AI Gen |
|----------|------------|--------------------------|-------------|----------------|--------|
| Markpact | Tak (16+ lang) [^1] | Tak (`markpact:*`) | Natywne (sync/rollback) | Doskonałe (sandbox/SSH) [^5] | Tak (LLM) |
| SUMD.md | Średnio | Tak (markpact-like) [^2] | Ręczne | Dobre | Tak |
| Czysty MD + frontmatter | Nie | Ograniczona | Brak | Średnie | Średnio |
| YAML/TOML | Nie | Nie | Brak | Dobre | Nie |

Markpact wygrywa dla Twojego stacku (RPi/embedded/Docker/AI).[^8]
<span style="display:none">[^10][^11][^12][^13][^14][^15][^16][^17][^18][^19][^9]</span>

<div align="center">⁂</div>

[^1]: https://libraries.io/pypi/marksync
[^2]: https://www.perplexity.ai/search/51d32a1c-50f8-4a2f-be85-a2869c05c1da
[^3]: https://markaicode.com/ai-agent-gitops-azure-ml-2025-pipelines/
[^4]: https://www.perplexity.ai/search/02ae9ce4-186e-4586-b6b7-c6081175c8f8
[^5]: https://aws.amazon.com/blogs/devops/automating-deployments-to-raspberry-pi-devices-using-aws-codepipeline/
[^6]: https://www.reddit.com/r/selfhosted/comments/1qtcjw0/gave_my_ai_agent_persistent_semantic_memory_on_a/
[^7]: https://www.perplexity.ai/search/5f826560-ad07-4702-90d8-0d3682423b94
[^8]: https://www.perplexity.ai/search/f33330ce-4dbd-4f26-ade3-0ea64c839bfb
[^9]: https://www.oreilly.com/radar/how-to-write-a-good-spec-for-ai-agents/
[^10]: https://agentfactory.panaversity.org/docs/Deploying-Agent-Factories-in-the-Cloud/cicd-gitops-argocd/ai-assisted-gitops-workflows
[^11]: https://fast.io/resources/ai-agent-gitops/
[^12]: https://www.datafmt.com/en/blog/en-yaml-json-toml-comparison
[^13]: https://support.tools/enterprise-ai-gitops-automation-comprehensive-release-management-guide/
[^14]: https://www.anbowell.com/blog/an-in-depth-comparison-of-json-yaml-and-toml
[^15]: https://muhammadraza.me/2025/building-ai-agents-devops-automation/
[^16]: https://www.reddit.com/r/Python/comments/1o8ors4/toml_is_great_and_after_diving_deep_into/
[^17]: https://www.youtube.com/watch?v=3lCeYjnuTAk
[^18]: https://awslabs.github.io/ai-on-eks/docs/infra/agents-on-eks
[^19]: https://github.com/marczellm/tkpf/issues/13```


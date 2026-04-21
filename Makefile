PYTHON     := python3
VENV       := .venv
BIN        := $(VENV)/bin
PIP        := $(BIN)/pip
PYTEST     := $(BIN)/pytest
RUFF       := $(BIN)/ruff
REDEPLOY   := $(BIN)/redeploy

# Default VPS target (override on CLI: make detect HOST=root@1.2.3.4)
HOST       ?= root@87.106.87.183
APP        ?= c2004
DOMAIN     ?= c2004.mask.services
TARGET     ?= examples/target-from-k3s-to-docker.yaml
STRATEGY   ?= docker_full
SPEC       ?= examples/k3s-to-docker.yaml

.PHONY: help install test lint fmt check \
        run run-dry \
        detect plan apply migrate dry-run \
        push tag release clean

# ── help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "redeploy — Infrastructure migration toolkit"
	@echo ""
	@echo "  Setup:"
	@echo "    make install          Install package + dev deps in .venv"
	@echo ""
	@echo "  Development:"
	@echo "    make test             Run unit tests"
	@echo "    make lint             Ruff linter"
	@echo "    make fmt              Ruff formatter"
	@echo "    make check            lint + test"
	@echo ""
	@echo "  Single-file spec (recommended):"
	@echo "    make run              Execute SPEC migration.yaml (plan + apply)"
	@echo "    make run-dry          Dry-run SPEC (no changes)"
	@echo "    make run SPEC=examples/k3s-to-docker.yaml"
	@echo ""
	@echo "  Low-level (separate detect/plan/apply):"
	@echo "    make detect           Probe infra → infra.yaml"
	@echo "    make plan             infra.yaml + TARGET → migration-plan.yaml"
	@echo "    make apply            Execute migration-plan.yaml"
	@echo "    make dry-run          Apply with --dry-run"
	@echo "    make migrate          Full pipeline: detect → plan → apply"
	@echo ""
	@echo "  Release:"
	@echo "    make push             git push origin main"
	@echo "    make tag VERSION=x.y.z  Tag + push"
	@echo "    make release VERSION=x.y.z  Bump version, commit, tag, push"
	@echo ""
	@echo "  Defaults: HOST=$(HOST) APP=$(APP) DOMAIN=$(DOMAIN)"
	@echo ""

# ── setup ─────────────────────────────────────────────────────────────────────
install: $(VENV)/bin/activate

$(VENV)/bin/activate: pyproject.toml
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip -q
	$(PIP) install -e ".[dev]" -q
	@echo "✅ Installed in $(VENV)"

# ── dev ───────────────────────────────────────────────────────────────────────
test: install
	$(PYTEST) redeploy/tests/ -v

lint: install
	$(RUFF) check redeploy/

fmt: install
	$(RUFF) format redeploy/

check: lint test

# ── run (single spec file) ────────────────────────────────────────────────────
run: install
	$(REDEPLOY) -v run $(SPEC)

run-dry: install
	$(REDEPLOY) -v run $(SPEC) --dry-run

run-plan: install
	$(REDEPLOY) -v run $(SPEC) --plan-only --plan-out migration-plan.yaml

run-detect: install
	$(REDEPLOY) -v run $(SPEC) --detect --dry-run

# ── detect / plan / apply ─────────────────────────────────────────────────────
detect: install
	$(REDEPLOY) -v detect \
		--host $(HOST) \
		--app $(APP) \
		--domain $(DOMAIN) \
		-o infra.yaml

plan: install
	$(REDEPLOY) -v plan \
		--infra infra.yaml \
		--target $(TARGET) \
		--strategy $(STRATEGY) \
		--domain $(DOMAIN) \
		-o migration-plan.yaml

apply: install
	$(REDEPLOY) -v apply --plan migration-plan.yaml -o apply-results.yaml

dry-run: install
	$(REDEPLOY) -v apply --plan migration-plan.yaml --dry-run

migrate: install
	$(REDEPLOY) -v migrate \
		--host $(HOST) \
		--app $(APP) \
		--domain $(DOMAIN) \
		--target $(TARGET) \
		--strategy $(STRATEGY) \
		--infra-out infra.yaml \
		--plan-out migration-plan.yaml

# ── git / release ─────────────────────────────────────────────────────────────
push:
	git push origin main

tag:
	@test -n "$(VERSION)" || (echo "Usage: make tag VERSION=x.y.z" && exit 1)
	git tag -a v$(VERSION) -m "Release $(VERSION)"
	git push origin v$(VERSION)

release:
	@test -n "$(VERSION)" || (echo "Usage: make release VERSION=x.y.z" && exit 1)
	@sed -i 's/^version = .*/version = "$(VERSION)"/' pyproject.toml
	@sed -i 's/^__version__ = .*/__version__ = "$(VERSION)"/' redeploy/__init__.py
	git add pyproject.toml redeploy/__init__.py
	git commit -m "release: $(VERSION)"
	git tag -a v$(VERSION) -m "Release $(VERSION)"
	git push origin main
	git push origin v$(VERSION)
	@echo "✅ Released v$(VERSION)"

# ── quality gate (pyqual analyze only — avoids LLM-based stages hanging) ──────
quality:
	@echo "🔍 Running quality gate (cc≤15, critical≤80) ..."
	$(BIN)/python scripts/quality_gate.py

quality-check: quality
	@echo "✅ redeploy quality gate passed"

# ── clean ─────────────────────────────────────────────────────────────────────
clean:
	rm -rf $(VENV) __pycache__ redeploy/__pycache__ \
		redeploy/**/__pycache__ *.egg-info dist build \
		.pytest_cache .ruff_cache

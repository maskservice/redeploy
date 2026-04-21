# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Add `action: inline_script` for executing multiline bash scripts directly from YAML without external files
- Script is base64-encoded and executed via SSH with automatic temp file cleanup
- Use `command` field with YAML `|` for multiline script content
- Add `command_ref` field to reference scripts from markdown codeblocks
  - `"#section-id"` — script from section in current spec file
  - `"./file.md#section-id"` — script from section in specific file
  - Single source of truth — no duplication between markdown and YAML
- Add `extract_script_from_markdown()` parser function for extracting scripts by heading
- Add `redeploy exec` CLI command to execute single scripts from markdown by reference
  - `redeploy exec '#section-id' --host user@host --file migration.md`
  - Supports `--dry-run` to preview script content
  - Useful for one-off operations and testing individual scripts
- Add `redeploy exec-multi` CLI command to execute multiple scripts at once
  - `redeploy exec-multi 'script1,script2,script3' --host user@host --file migration.md`
  - Sequential execution with summary table
- Add `markpact:ref <id>` syntax for marking codeblocks in markdown
  - ```bash markpact:ref my-script-id
  - Explicit script identification
  - Multiple scripts per section
  - `extract_script_by_ref()` parser function

### Changed
- Migration specs can now use inline_script for cleaner deployment scripts (no base64 encoding in YAML)

## [0.2.44] - 2026-04-21

### Docs
- Update README.md

### Other
- Update .redeploy/state/migration-local-92efc860.yaml
- Update .redeploy/state/test-local-abe8802f.yaml
- Update Makefile
- Update pyqual.yaml
- Update redeploy/cli/commands/device_map.py

## [0.2.43] - 2026-04-21

### Docs
- Update README.md
- Update SUMD.md
- Update SUMR.md
- Update TODO.md
- Update docs/README.md
- Update examples/hardware/rpi5-waveshare-kiosk.md

### Test
- Update tests/test_hardware_kiosk.py

### Other
- Update .redeploy/state/test-local-6bb4cec7.yaml
- Update project/duplication.toon.yaml
- Update project/map.toon.yaml
- Update redeploy/apply/executor.py
- Update redeploy/apply/handlers.py
- Update redeploy/cli/__init__.py
- Update redeploy/cli/commands/push.py
- Update redeploy/hardware/kiosk/__init__.py
- Update redeploy/hardware/kiosk/autostart.py
- Update redeploy/hardware/kiosk/browsers.py
- ... and 4 more files

## [0.2.42] - 2026-04-21

### Docs
- Update README.md

### Other
- Update .redeploy/state/test-local-35782b9c.yaml
- Update redeploy/apply/state_apply.py
- Update redeploy/cli/commands/blueprint.py
- Update redeploy/cli/commands/device_map.py
- Update redeploy/cli/commands/hardware.py

## [0.2.41] - 2026-04-21

### Docs
- Update README.md

### Test
- Update tests/test_hardware_rules.py

### Other
- Update .redeploy/state/test-local-036bc2a0.yaml
- Update .redeploy/state/test-local-c05a99a2.yaml
- Update .redeploy/state/test-local-f868d117.yaml
- Update redeploy/cli/commands/blueprint.py
- Update redeploy/cli/commands/device_map.py
- Update redeploy/cli/commands/diagnose.py
- Update redeploy/cli/commands/diff.py
- Update redeploy/cli/commands/export.py
- Update redeploy/cli/commands/hardware.py
- Update redeploy/detect/hardware.py
- ... and 2 more files

## [0.2.40] - 2026-04-21

### Docs
- Update README.md
- Update SUMD.md
- Update SUMR.md
- Update docs/README.md

### Other
- Update .redeploy/state/test-local-0a0a5446.yaml
- Update project/duplication.toon.yaml
- Update project/map.toon.yaml
- Update redeploy/cli/commands/blueprint.py
- Update redeploy/cli/commands/device_map.py
- Update redeploy/cli/commands/diagnose.py
- Update redeploy/cli/commands/diff.py
- Update redeploy/cli/commands/export.py
- Update redeploy/cli/commands/hardware.py
- Update reports/hardware-108.yaml
- ... and 2 more files

## [0.2.39] - 2026-04-21

### Docs
- Update README.md

### Other
- Update .redeploy/state/test-local-179edfed.yaml

## [0.2.38] - 2026-04-21

### Docs
- Update README.md

### Other
- Update .redeploy/state/test-local-9cc88960.yaml
- Update redeploy/cli/commands/hardware.py

## [0.2.37] - 2026-04-21

### Docs
- Update README.md
- Update examples/hardware/enable-i2c-spi.md
- Update examples/hardware/official-dsi-7-inch.md
- Update examples/hardware/waveshare-8-inch-dsi.md

### Test
- Update tests/test_hardware_config.py

### Other
- Update .redeploy/state/test-local-ad30ec23.yaml
- Update redeploy/apply/executor.py
- Update redeploy/apply/handlers.py
- Update redeploy/cli/commands/hardware.py
- Update redeploy/detect/hardware.py
- Update redeploy/hardware/__init__.py
- Update redeploy/hardware/data/__init__.py
- Update redeploy/hardware/data/hyperpixel.py
- Update redeploy/hardware/data/official.py
- Update redeploy/hardware/fixes.py
- ... and 1 more files

## [0.2.36] - 2026-04-21

### Docs
- Update README.md

### Test
- Update tests/test_hardware_rules.py

### Other
- Update .redeploy/state/test-local-c9849e24.yaml
- Update .redeploy/state/test-local-e069dd9f.yaml
- Update redeploy/apply/handlers.py
- Update redeploy/apply/utils/__init__.py
- Update redeploy/apply/utils/run_container_build.py
- Update redeploy/cli/commands/hardware.py
- Update redeploy/cli/commands/version.py
- Update redeploy/cli/commands/version/__init__.py
- Update redeploy/cli/commands/version/commands.py
- Update redeploy/cli/commands/version/helpers.py
- ... and 23 more files

## [0.2.35] - 2026-04-21

### Docs
- Update README.md
- Update SUMD.md
- Update SUMR.md
- Update docs/README.md

### Other
- Update .redeploy/state/test-local-eac354f9.yaml
- Update app.doql.less
- Update project.sh
- Update project/duplication.toon.yaml
- Update project/map.toon.yaml
- Update project/validation.toon.yaml
- Update redeploy/apply/handlers.py
- Update sumd.json

## [0.2.34] - 2026-04-21

### Docs
- Update README.md

### Other
- Update .redeploy/state/test-local-a70e54ce.yaml
- Update redeploy/blueprint/__init__.py
- Update redeploy/blueprint/extractor.py
- Update redeploy/blueprint/generators/__init__.py
- Update redeploy/blueprint/generators/docker_compose.py
- Update redeploy/blueprint/generators/migration.py
- Update redeploy/cli/__init__.py
- Update redeploy/cli/commands/blueprint.py
- Update redeploy/cli/commands/device_map.py
- Update redeploy/cli/commands/hardware.py
- ... and 1 more files

## [0.2.33] - 2026-04-21

### Docs
- Update README.md

### Other
- Update .redeploy/state/test-local-50622a24.yaml
- Update redeploy/detect/__init__.py
- Update redeploy/detect/detector.py
- Update redeploy/detect/hardware.py
- Update redeploy/models.py

## [0.2.32] - 2026-04-21

### Docs
- Update README.md

### Other
- Update .redeploy/state/test-local-891787e9.yaml

## [0.2.31] - 2026-04-21

### Docs
- Update README.md

### Other
- Update .redeploy/state/test-local-da199855.yaml
- Update redeploy/plugins/builtin/hardware_diagnostic.py
- Update redeploy/plugins/builtin/process_control.py
- Update redeploy/steps.py
- Update redeploy/templates/process_control_template.yaml

## [0.2.30] - 2026-04-21

### Docs
- Update README.md
- Update SUMD.md
- Update docs/README.md

### Other
- Update .gitignore
- Update .redeploy/state/test-local-24cd498c.yaml
- Update project/duplication.toon.yaml
- Update project/validation.toon.yaml
- Update redeploy/cli/commands/devices.py
- Update redeploy/discovery.py

## [0.2.29] - 2026-04-21

### Docs
- Update README.md

### Other
- Update .redeploy/state/test-local-efd3d620.yaml

## [0.2.28] - 2026-04-21

### Docs
- Update README.md

### Other
- Update .redeploy/state/test-local-5a1d7483.yaml
- Update .redeploy/state/test-local-a929f336.yaml
- Update .redeploy/state/test-local-ed7da478.yaml
- Update redeploy/apply/__init__.py
- Update redeploy/apply/executor.py
- Update redeploy/apply/handlers.py
- Update redeploy/apply/progress.py
- Update redeploy/apply/rollback.py

## [0.2.27] - 2026-04-21

### Docs
- Update README.md

### Other
- Update .redeploy/state/test-local-9c9d5826.yaml
- Update redeploy/apply/exceptions.py
- Update redeploy/apply/progress.py

## [0.2.26] - 2026-04-21

### Docs
- Update README.md
- Update docs/README.md

### Other
- Update project/duplication.toon.yaml

## [0.2.25] - 2026-04-21

### Docs
- Update README.md

### Other
- Update .redeploy/state/test-local-6279ef2c.yaml
- Update .redeploy/state/test-local-db469906.yaml

## [0.2.24] - 2026-04-21

### Docs
- Update README.md

### Other
- Update .redeploy/state/test-local-63f620b6.yaml

## [0.2.24] - 2026-04-21

### Docs
- Update README.md

### Other
- Update .redeploy/state/test-local-63f620b6.yaml

## [0.2.23] - 2026-04-21

### Docs
- Update README.md

### Other
- Update .redeploy/state/test-local-831fd1ab.yaml
- Update .redeploy/state/test-local-df0d6ff6.yaml
- Update redeploy/tests/test_version_cli.py

## [0.2.22] - 2026-04-21

### Docs
- Update README.md

### Other
- Update .redeploy/state/test-local-09b68243.yaml
- Update .redeploy/state/test-local-68ae2b20.yaml
- Update redeploy/tests/test_cli.py

## [0.2.21] - 2026-04-21

### Docs
- Update README.md
- Update project/code2llm_output/README.md
- Update project/code2llm_output/context.md

### Other
- Update .redeploy/state/test-local-46c5e2ce.yaml
- Update .redeploy/state/test-local-56cb0635.yaml
- Update .redeploy/state/test-local-7f5ddd97.yaml
- Update .redeploy/state/test-local-be94eb0c.yaml
- Update .redeploy/state/test-local-e1009318.yaml
- Update .redeploy/state/test-local-ea908429.yaml
- Update project/code2llm_output/analysis.toon.yaml
- Update redeploy/apply/executor.py
- Update redeploy/cli.py
- Update redeploy/cli/__init__.py
- ... and 26 more files

## [0.2.20] - 2026-04-21

### Docs
- Update README.md

### Other
- Update .redeploy/state/test-local-ec3c5638.yaml
- Update redeploy/apply/executor.py
- Update redeploy/audit.py
- Update redeploy/cli.py
- Update redeploy/discovery.py
- Update redeploy/parse.py

## [0.2.19] - 2026-04-21

### Docs
- Update README.md
- Update code2llm_output/README.md
- Update code2llm_output/context.md
- Update docs/README.md

### Other
- Update .redeploy/state/test-local-e322f022.yaml
- Update code2llm_output/analysis.toon.yaml
- Update project/duplication.toon.yaml
- Update project/validation.toon.yaml
- Update redeploy/apply/executor.py
- Update redeploy/cli.py
- Update redeploy/models.py

## [0.2.18] - 2026-04-21

### Docs
- Update CHANGELOG.md
- Update README.md

### Other
- Update .redeploy/state/test-local-36935faf.yaml
- Update .redeploy/state/test-local-563ceb24.yaml
- Update redeploy/apply/executor.py
- Update redeploy/checkpoint.py
- Update redeploy/cli.py
- Update redeploy/markpact/__init__.py
- Update redeploy/markpact/compiler.py
- Update redeploy/markpact/models.py
- Update redeploy/markpact/parser.py
- Update redeploy/models.py
- ... and 3 more files

## [0.2.17] - 2026-04-21

### Docs
- Update CHANGELOG.md
- Update README.md

### Other
- Update redeploy/apply/__init__.py
- Update redeploy/apply/executor.py
- Update redeploy/apply/state.py
- Update redeploy/audit.py
- Update redeploy/checkpoint.py
- Update redeploy/cli.py
- Update redeploy/markpact/parser.py
- Update redeploy/models.py
- Update redeploy/tests/test_audit.py
- Update redeploy/tests/test_executor.py

## [0.2.16] - 2026-04-20

### Docs
- Update README.md
- Update TODO/zaproponuj runtime do obslugi tego typu pliku.md

### Other
- Update "TODO/Pomys\305\202 jest ciekawy i wbrew pozorom ca\305\202kiem sensow.md"
- Update "TODO/a jak by to mia\305\202ol by\304\207 obslugiwane przez rozne jez.md"

## [0.2.15] - 2026-04-20

### Docs
- Update README.md

### Other
- Update redeploy/markpact/parser.py
- Update redeploy/tests/test_markpact_compiler.py
- Update redeploy/tests/test_markpact_parser.py

## [0.2.14] - 2026-04-20

### Docs
- Update README.md
- Update TODO/zaproponuj runtime do obslugi tego typu pliku.md
- Update examples/md/01-rpi5-deploy/migration.md
- Update examples/md/01-vps-version-bump/migration.md
- Update examples/md/02-k3s-to-docker/migration.md
- Update examples/md/02-multi-language/migration.md
- Update examples/md/03-all-actions/migration.md
- Update examples/md/03-docker-to-podman-quadlet/migration.md
- Update examples/md/04-v3-state-reconciliation/migration.md

### Other
- Update "TODO/a jak by to mia\305\202ol by\304\207 obslugiwane przez rozne jez.md"
- Update redeploy/apply/executor.py
- Update redeploy/tests/test_cli.py
- Update redeploy/tests/test_executor.py
- Update redeploy/tests/test_spec_loader.py

## [0.2.13] - 2026-04-20

### Docs
- Update README.md
- Update docs/markpact-audit.md
- Update docs/markpact-implementation-plan.md
- Update examples/README.md
- Update examples/md/02-k3s-to-docker/README.md
- Update examples/md/02-k3s-to-docker/migration.md
- Update examples/md/03-docker-to-podman-quadlet/README.md
- Update examples/md/03-docker-to-podman-quadlet/migration.md
- Update examples/md/README.md

### Other
- Update redeploy/tests/test_examples.py

## [0.2.12] - 2026-04-20

### Docs
- Update README.md
- Update docs/markpact-audit.md
- Update examples/README.md
- Update examples/md/01-rpi5-deploy/migration.md
- Update examples/md/01-vps-version-bump/README.md
- Update examples/md/01-vps-version-bump/migration.md
- Update examples/md/02-multi-language/migration.md
- Update examples/md/03-all-actions/migration.md
- Update examples/md/README.md

### Other
- Update redeploy/tests/test_examples.py

## [0.2.11] - 2026-04-20

### Docs
- Update README.md

### Other
- Update redeploy/markpact/__init__.py
- Update redeploy/markpact/compiler.py
- Update redeploy/markpact/models.py
- Update redeploy/markpact/parser.py
- Update redeploy/spec_loader.py
- Update redeploy/tests/test_cli.py
- Update redeploy/tests/test_markpact_compiler.py
- Update redeploy/tests/test_markpact_parser.py
- Update redeploy/tests/test_spec_loader.py

## [0.2.10] - 2026-04-20

### Docs
- Update README.md

### Other
- Update redeploy/cli.py
- Update redeploy/spec_loader.py
- Update redeploy/tests/test_cli.py
- Update redeploy/tests/test_spec_loader.py

## [0.2.9] - 2026-04-20

### Docs
- Update README.md
- Update docs/markpact-audit.md
- Update docs/markpact-implementation-plan.md
- Update examples/README.md
- Update examples/md/01-rpi5-deploy/migration.md
- Update examples/md/02-multi-language/migration.md
- Update examples/md/03-all-actions/migration.md
- Update examples/md/04-v3-state-reconciliation/migration.md
- Update examples/md/README.md

### Other
- Update redeploy/cli.py
- Update redeploy/tests/test_version_cli.py

## [0.2.8] - 2026-04-20

### Docs
- Update README.md
- Update examples/md/04-v3-state-reconciliation/migration.md

### Other
- Update redeploy/cli.py
- Update redeploy/tests/test_version_cli.py

## [0.2.7] - 2026-04-20

### Docs
- Update README.md

### Other
- Update redeploy/cli.py
- Update redeploy/tests/test_version_cli.py

## [0.2.6] - 2026-04-20

### Docs
- Update README.md
- Update examples/md/README.md

### Other
- Update redeploy/cli.py
- Update redeploy/tests/test_examples.py
- Update redeploy/tests/test_version_cli.py

## [0.2.5] - 2026-04-20

### Docs
- Update README.md

### Other
- Update redeploy/cli.py
- Update redeploy/tests/test_version_cli.py

## [0.2.4] - 2026-04-20

### Docs
- Update README.md
- Update redeploy-version-management-plan.md

### Other
- Update .redeploy/version.yaml
- Update VERSION
- Update redeploy/__init__.py
- Update redeploy/cli.py
- Update redeploy/models.py
- Update redeploy/tests/test_version_cli.py
- Update redeploy/tests/test_version_sources.py
- Update redeploy/version/__init__.py
- Update redeploy/version/bump.py
- Update redeploy/version/diff.py
- ... and 2 more files

## [0.2.2] - 2026-04-20

### Added — Plugin system (`redeploy/plugins/`)

- `redeploy/plugins/__init__.py` — plugin registry and public API
  - `PluginContext` — dataclass passed to every plugin handler: `step`, `host`, `probe`, `emitter`, `params`, `dry_run`
  - `PluginRegistry` — central registry mapping `plugin_type` strings to handler callables
    - `register(name, handler)` — programmatic registration
    - `__call__(name)` — decorator factory: `@registry("my_plugin")`
    - `get(name)` — lazy lookup (auto-loads builtins on first call)
    - `names()` — list all registered plugin types
    - `load_directory(path)` — import all `*.py` files from a directory
  - `register_plugin(name)` — module-level decorator shortcut: `@register_plugin("browser_reload")`
  - `load_user_plugins()` — auto-discovery of user plugins from:
    - `./redeploy_plugins/` (project-local, scanned in cwd)
    - `~/.redeploy/plugins/` (user-global)
  - Built-in plugins loaded lazily from `redeploy/plugins/builtin/`

- `redeploy/plugins/builtin/browser_reload.py` — built-in `browser_reload` plugin
  - Reloads Chromium/Chrome tabs via Chrome DevTools Protocol (CDP) over SSH
  - Uses only Python stdlib on the remote host (no `websocket-client` required)
  - Manual WebSocket handshake + `Page.reload` CDP command
  - Supports `url_contains` filter to target specific tabs
  - Emits `progress` events per reloaded tab
  - Parameters: `port` (default: 9222), `ignore_cache` (default: true), `url_contains` (default: "")

- `StepAction.PLUGIN` — new action type in `models.py`
- `MigrationStep.plugin_type` + `MigrationStep.plugin_params` — new fields for plugin configuration

### Changed
- `Executor._execute_step()` — added `StepAction.PLUGIN` dispatch to `_run_plugin()`
- `Executor._run_plugin()` — new handler: resolves plugin by `plugin_type`, builds `PluginContext`, calls handler
- `cli.py` `_run_apply()` — calls `load_user_plugins()` before every apply run
- `pyproject.toml` version: `0.2.1` → `0.2.2`

### Usage example (migration YAML)
```yaml
steps:
  - id: reload_kiosk
    action: plugin
    plugin_type: browser_reload
    description: Reload kiosk browser after deploy
    plugin_params:
      port: 9222
      ignore_cache: true
      url_contains: "localhost:8100"
```

### Custom plugin example
```python
# ./redeploy_plugins/notify.py
from redeploy.plugins import register_plugin, PluginContext
from redeploy.models import StepStatus

@register_plugin("notify_slack")
def notify_slack(ctx: PluginContext) -> None:
    webhook = ctx.params["webhook"]
    ctx.probe.run(f"curl -X POST {webhook} -d '{{\"text\":\"deployed!\"}}'")
    ctx.step.result = "notified"
    ctx.step.status = StepStatus.DONE
```

### Verified
- Full c2004 → RPi5 pipeline (12 steps) completed successfully with `browser_reload` as step 10
- `browser_reload` executed in ~2s via CDP WebSocket tunnel over SSH
- Result: `reloaded 1 tab(s): http://localhost:8100/connect-id?...`

## [0.2.1] - 2026-04-20

### Docs
- Update README.md

## [0.2.0] - 2026-04-20

### Added
- `redeploy/__init__.py` — formal public API with `__all__` (semver contract from 0.2.0)
  - Exports: `MigrationSpec`, `MigrationPlan`, `MigrationStep`, `InfraState`, `TargetConfig`,
    `DeployStrategy`, `StepAction`, `StepStatus`, `ConflictSeverity`, `Detector`, `Planner`,
    `Executor`, `SshClient`, `SshResult`, `DeviceRegistry`, `KnownDevice`, `FleetConfig`,
    `FleetDevice`, `Stage`, `StepLibrary`
- `DeployStrategy.KIOSK_APPLIANCE` — new strategy for doql kiosk-station projects
- `Planner._plan_kiosk_appliance()` — full install flow: rsync build → installer → systemd service → verify
- `_STRATEGY_ALIASES` + `TargetConfig._accept_strategy_aliases` — accept doql/external aliases:
  `docker-compose` → `docker_full`, `quadlet` → `podman_quadlet`,
  `kiosk-appliance` → `kiosk_appliance`, `kubernetes`/`k8s` → `k3s`
- `examples/13-kiosk-appliance.yaml` — end-to-end kiosk appliance example
- `test_public_api.py` (28 tests) — smoke tests for every name in `__all__`,
  alias resolution, `KIOSK_APPLIANCE` planner steps

### Changed
- `TargetConfig.app` default: `"c2004"` → `""` (no hardcoded project name)
- `TargetConfig.remote_dir` default: `"~/c2004"` → `""` (resolved at plan time from app)
- `pyproject.toml` version: `0.1.7` → `0.2.0`

### Fixed
- `pydantic.field_validator` added to imports in `models.py`
- `TargetConfig` defaults no longer hardcode project-specific values (`"c2004"`, `"~/c2004"`)

### Phase 6 — IaC parser (0.2.0)
- `redeploy/iac/` — pluggable IaC/CI-CD parser framework (zero new deps, PyYAML already required)
  - `base.py`: `ParsedSpec`, `Parser` protocol, `ParserRegistry`, `PortInfo`, `ServiceInfo`, `VolumeInfo`, `ConversionWarning`
  - `docker_compose.py`: Tier 1 Docker Compose parser (`name="docker_compose"`)
    - Compose v3.x: services, ports (string/long-form/protocol), volumes (bind/named/ro), env (dict/list), env_file, networks, depends_on (list/dict), healthcheck, labels (dict/list), restart, command (string/list), deploy.replicas, secrets, x-* extension keys, variable substitution `${VAR}`, `${VAR:-default}`
    - Profile support, multi-file merge, `_deep_merge`
  - `parsers/compose.py`: alternate lightweight parser (used by registry)
  - `registry.py`: global `parser_registry` singleton + `parse_file()`, `parse_dir()`
  - `__init__.py`: public API re-exports
- `test_iac.py` — 41 tests: `can_parse`, `parse` (ports/volumes/env/labels/healthcheck/secrets/networks/replicas/command/build), `ParserRegistry`, `parse_file`, `parse_dir`, `ConversionWarning`

### Phase 5 — Observability (0.2.0)
- `redeploy/observe.py` — new module:
  - `AuditEntry` — immutable snapshot of one deployment (ts, host, app, strategies, ok, elapsed, steps)
  - `DeployAuditLog` — persistent JSONL log at `~/.config/redeploy/audit.jsonl`
    - `record(plan, completed, ok, elapsed_s, dry_run)` — build + persist entry
    - `load(limit)`, `tail(n)`, `filter(host, app, ok, since)`, `clear()`
    - Corrupt lines silently skipped; parent dirs auto-created
  - `DeployReport` — human-readable / YAML post-deploy summary
    - `text()` — boxed table with step icons (✓ ✗ ⤼), strategy, elapsed, error
    - `yaml()` — machine-readable for CI pipelines
    - `summary_line()` — single-line for CI log output
- `Executor` — auto-writes audit entry after every `run()` (opt-out with `audit_log=False`)
  - New params: `audit_log: bool = True`, `audit_path: Optional[Path] = None`
  - New property: `completed_steps` — list of successfully executed steps
  - Audit write never crashes executor (exception caught + logged at DEBUG)
- `AuditEntry`, `DeployAuditLog`, `DeployReport` added to `__all__`
- `test_observe.py` — 37 tests: AuditEntry accessors, JSONL round-trip, filter/tail, corrupt-line skip, DeployReport text/yaml/summary, Executor integration

### Phase 4 — Deploy patterns (0.2.0)
- `redeploy/patterns.py` — new module with `DeployPattern` base class and three patterns:
  - `BlueGreenPattern` — zero-downtime via Traefik label swap (7 steps: clone_green, deploy_green, health_green, swap_labels, verify_main, retire_blue + optional sync_env)
  - `CanaryPattern` — gradual rollout in configurable stages with per-stage health checks and waits; promotes canary → main at 100%
  - `RollbackOnFailurePattern` — snapshots current image tags, auto-rollback on failure
- `TargetConfig.pattern` + `TargetConfig.pattern_config` fields
- `Planner._plan_pattern()` — expands pattern steps, falls back to standard deploy for unknown patterns
- `get_pattern(name)`, `list_patterns()`, `pattern_registry` — pattern lookup API
- All patterns + helpers exported in `__all__`
- `test_patterns.py` — 35 tests covering all patterns, planner integration, config passthrough
- `examples/14-blue-green.yaml`, `15-canary.yaml`, `16-auto-rollback.yaml`

### Phase 2 — Fleet first-class (0.2.0)
- `Fleet` class in `redeploy/fleet.py` — unified view over `FleetConfig` + `DeviceRegistry`
  - `Fleet.from_file(path)` — load from `fleet.yaml`
  - `Fleet.from_registry(path)` — load from devices.yaml, converts `KnownDevice` → `FleetDevice`
  - `Fleet.from_config(config)` — wrap existing `FleetConfig`
  - `Fleet.merge(other)` — union, other wins on id collision
  - `Fleet.by_tag / by_stage / by_strategy / prod / reachable / get` — query API
  - `Fleet.__len__ / __iter__ / __repr__`
- `Fleet` added to `__all__` and exported from `redeploy`
- 11 new `TestFleet` tests + 4 new `test_public_api` tests for `Fleet`

## [0.1.7] - 2026-04-20

### Added
- `redeploy run --env NAME` — use named environment from `redeploy.yaml` (e.g. `--env prod`, `--env rpi5`)
- `ProjectManifest.from_dotenv()` — fallback: read `DEPLOY_*` vars from `.env` when no `redeploy.yaml`
- `ProjectManifest.resolve_env()` — merge named env config with manifest defaults
- `EnvironmentConfig.spec` — per-environment spec file override
- `StepLibrary`: 5 new steps — `stop_podman`, `enable_podman_unit`, `systemctl_restart`, `systemctl_daemon_reload`, `git_pull`
- `SshClient.put_file(content, remote_path, mode)` — write string content directly to remote via `cat+stdin`, no temp file
- `TargetConfig.host` — optional field; `Planner` uses `target.host` over `state.host` when set (multi-host foundation)
- `check_version_http(endpoint=...)` — parametrized version check endpoint (default: `/api/v3/version/check`)
- `detect` and `migrate` CLI commands now read `app`/`domain` defaults from `ProjectManifest`

### Fixed
- `datetime.utcnow()` → `datetime.now(timezone.utc)` — all occurrences removed (`models.py`, `discovery.py`), eliminates `DeprecationWarning` on Python 3.12+

### Refactored
- `cli.py`: Extracted 4 helper functions from `target()` to reduce cyclomatic complexity (CC: 16 → 9)
  - `_resolve_device()` — device registry lookup + auto-probe fallback
  - `_load_spec_with_manifest()` — spec loading with manifest overlay
  - `_overlay_device_onto_spec()` — device values → spec target config
  - `_run_detect_for_spec()` — conditional detect + planner creation

### Test
- `test_manifest.py` (38 tests) — `ProjectManifest`, `EnvironmentConfig`, `DeviceRegistry`, `KnownDevice`
- `test_templates.py` (47 tests) — `TemplateEngine`, `build_context`, `DetectionTemplate.score`, built-in templates
- `test_data_sync.py` (14 tests) — `collect_sqlite_counts`, `rsync_timeout_for_path`
- `test_version.py` (23 tests) — `read_local/remote_version`, `check_version`, `check_version_http`
- Total: **569 tests** (all passing)

## [0.1.6] - 2026-04-20

### Docs
- Update README.md

### Other
- Update redeploy/detect/probes.py
- Update redeploy/detect/templates.py
- Update redeploy/models.py

## [0.1.5] - 2026-04-20

### Docs
- Update README.md

### Other
- Update redeploy/discovery.py
- Update redeploy/tests/test_templates.py

## [0.1.4] - 2026-04-20

### Docs
- Update CHANGELOG.md
- Update README.md
- Update SUMD.md
- Update SUMR.md

### Other
- Update redeploy/cli.py
- Update redeploy/models.py
- Update redeploy/tests/test_manifest.py
- Update sumd.json

## [0.1.3] - 2026-04-20

### Docs
- Update README.md

### Other
- Update redeploy/cli.py

## [0.1.2] - 2026-04-20

### Added
- `StepLibrary` — reusable named steps referenced by `id` in `extra_steps` (no `action` needed)
- `insert_before: <step_id>` support in `extra_steps` — inject steps at a specific position in plan
- `podman_quadlet` planner: full step sequence (sync_env → install_quadlet_files → daemon-reload → stop → start → wait → verify)
- `podman_quadlet` rootless vs system mode: `systemctl --user` + `~/.config/containers/systemd/` vs `systemctl` + `/etc/containers/systemd/`
- `ship` Makefile target: test → redeploy run --detect → verify (one-command pipeline)

### Fixed
- `http_health_check`: `grep -qF` suppressed output — switched to `grep -F` so match is captured in `r.out`
- `rollback_command` for `docker_compose_up`: was `down` (killed stack on health-check fail), now `up -d` (keep running)
- `_append_extra_steps`: raw dict was mutated in-place across iterations (missing `dict(raw)` copy)
- `planner._plan_podman_quadlet`: was a stub with only a note; now generates full step sequence

### Changed
- `Makefile` CLI invocation: `python -m deploy.cli` → `PYTHONPATH=. python cli.py` (direct script)
- README: added `pipx install` as recommended install method
- README: added `docker_full`, `podman_quadlet` plan step tables
- README: added StepLibrary reference table with all 14 built-in steps
- README: updated `migration.yaml` spec example with `compose_files`, `verify_version`, `insert_before`

## [0.1.1] - 2026-04-20

### Docs
- Update README.md

### Test
- Update tests/test_redeploy.py

### Other
- Update .env.example
- Update .gitignore
- Update .idea/inspectionProfiles/Project_Default.xml
- Update .idea/inspectionProfiles/profiles_settings.xml
- Update .idea/modules.xml
- Update .idea/redeploy.iml
- Update .idea/workspace.xml


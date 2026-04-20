# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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


# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Refactored
- `cli.py`: Extracted 4 helper functions from `target()` to reduce cyclomatic complexity (CC: 16 → 9)
  - `_resolve_device()` — device registry lookup + auto-probe fallback
  - `_load_spec_with_manifest()` — spec loading with manifest overlay
  - `_overlay_device_onto_spec()` — device values → spec target config
  - `_run_detect_for_spec()` — conditional detect + planner creation

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


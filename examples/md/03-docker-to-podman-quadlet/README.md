# 03 - Docker Compose to Podman Quadlet (Markdown Subset)

Markdown counterpart to `examples/yaml/03-docker-to-podman-quadlet/migration.yaml`
using the Phase 1 markpact subset currently supported by `redeploy`.

## What this example proves

- `markpact:steps` can express explicit custom `ssh_cmd` steps, not only named library steps
- strategy migration examples still compile cleanly into the current planner
- the markdown subset can carry multi-line shell commands inside supported step mappings

## Run

```bash
redeploy run examples/md/03-docker-to-podman-quadlet/migration.md --plan-only
redeploy run examples/md/03-docker-to-podman-quadlet/migration.md --dry-run
```

## Limits

This example stays inside the currently supported subset:

- `markpact:config`
- `markpact:steps`
- YAML payloads
- existing `MigrationSpec` and `MigrationStep` fields only

Blocks such as `markpact:python`, `markpact:rollback`, and step fields such as
`when`, `skip_if`, `retry`, and `check_cmd` are still out of scope.

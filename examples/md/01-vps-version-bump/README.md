# 01 - VPS Version Bump (Markdown Subset)

Markdown counterpart to `examples/yaml/01-vps-version-bump/migration.yaml` using
the Phase 1 markpact subset currently supported by `redeploy`.

## What this example proves

- `redeploy run .../migration.md --plan-only` works with `markpact:config`
- `markpact:steps` appends supported `extra_steps`
- the existing planner and step library can execute the compiled result

## Run

```bash
redeploy run examples/md/01-vps-version-bump/migration.md --plan-only
redeploy run examples/md/01-vps-version-bump/migration.md --dry-run
```

## Limits

This example stays inside the currently supported subset:

- `markpact:config`
- `markpact:steps`
- YAML payloads
- existing `MigrationSpec` fields only

Fields such as `when`, `skip_if`, `retry`, `check_cmd`, and blocks such as
`markpact:python` or `markpact:rollback` are still out of scope.
# 02 - k3s to Docker Compose (Markdown Subset)

Markdown counterpart to `examples/yaml/02-k3s-to-docker/migration.yaml` using
the Phase 1 markpact subset currently supported by `redeploy`.

## What this example proves

- `redeploy run .../migration.md --detect --dry-run` works with a strategy change
- `markpact:config` can express source-side service shutdown and cleanup inputs
- `markpact:steps` can add supported named library steps such as `flush_k3s_iptables`

## Run

```bash
redeploy run examples/md/02-k3s-to-docker/migration.md --detect --plan-only
redeploy run examples/md/02-k3s-to-docker/migration.md --detect --dry-run
```

## Limits

This example stays inside the currently supported subset:

- `markpact:config`
- `markpact:steps`
- YAML payloads
- existing `MigrationSpec` and `MigrationStep` fields only

Blocks such as `markpact:python`, `markpact:rollback`, and step fields such as
`when`, `skip_if`, `retry`, and `check_cmd` are still out of scope.

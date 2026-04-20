# redeploy Examples — Markdown

This directory contains two kinds of markdown material:

- supported Phase 1 markpact subset examples
- several broader prototypes for future runtime work

## Current Status

- `redeploy run` now supports a limited `migration.md` subset via `markpact:config` and `markpact:steps`
- `examples/md/01-vps-version-bump` is an executable markdown example for that subset
- `examples/md/02-k3s-to-docker` is a second executable markdown example for that subset
- `examples/md/03-docker-to-podman-quadlet` is a third executable markdown example for that subset
- repository tests still focus mainly on `examples/yaml/`
- several markdown examples still contain aspirational fields not present in the current runtime

See [../../docs/markpact-audit.md](../../docs/markpact-audit.md) for the detailed audit.

## Files

- `01-vps-version-bump`: supported markdown subset example mirroring a YAML scenario
- `02-k3s-to-docker`: supported markdown subset example for a strategy migration scenario
- `03-docker-to-podman-quadlet`: supported markdown subset example with explicit custom `ssh_cmd` steps
- `01-rpi5-deploy`: prototype Raspberry Pi deployment spec
- `02-multi-language`: mixed YAML, TOML, JSON, Python, and Bash format demo
- `03-all-actions`: aspirational action catalog for a future markdown runtime
- `04-v3-state-reconciliation`: concept for future idempotency and execution state handling

## Important Mismatches

The markdown examples show ideas that do not map directly to the current codebase:

- `when`, `skip_if`, and `check_cmd`
- per-step `retry`
- `shell` as a first-class action in markdown examples
- `markpact:rollback` blocks
- standalone `markpact run ...` commands

## What To Use Instead

If you want working examples for the current repository, use `examples/yaml/`
or the supported markdown subset examples in `examples/md/01-vps-version-bump/`
`examples/md/02-k3s-to-docker/`, and `examples/md/03-docker-to-podman-quadlet/`.

If you want design material for a future markdown runtime, use `examples/md/`.

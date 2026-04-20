# redeploy Examples — Markdown Prototypes

This directory contains prototype markdown files for a proposed markpact-style
runtime.

These files are not supported by the current `redeploy run` implementation.

## Current Status

- `redeploy run` loads YAML specs, not `migration.md`
- repository tests validate `examples/yaml/`, not `examples/md/`
- several markdown examples contain aspirational fields not present in the current runtime

See [../../docs/markpact-audit.md](../../docs/markpact-audit.md) for the detailed audit.

## Files

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

If you want working examples for the current repository, use `examples/yaml/`.

If you want design material for a future markdown runtime, use `examples/md/`.

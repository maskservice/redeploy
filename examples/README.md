# redeploy Examples

This directory has two different kinds of material.

- `yaml/`: supported examples for the current `redeploy` CLI
- `md/`: a small supported markpact subset plus broader markdown prototypes

## What works today

Use YAML examples with the current CLI. A limited markdown subset also works.

```bash
redeploy run examples/yaml/01-vps-version-bump/migration.yaml --dry-run
redeploy run examples/yaml/02-k3s-to-docker/migration.yaml --detect
redeploy run examples/md/01-vps-version-bump/migration.md --plan-only
```

YAML examples are the primary supported path and remain the main test-backed
scenario set. The repository also includes one supported markdown example for
the Phase 1 markpact subset.

## What still does not work

The current `redeploy` CLI does not support arbitrary markdown runtimes.
Most files under `examples/md/` are still design/prototype material only.

They are useful for:

- format exploration
- documenting future runtime ideas
- comparing aspirational markdown semantics with the current YAML model

They are not useful as:

- one-to-one ports of the YAML scenario set
- full coverage of the aspirational markpact feature set

## Directory Overview

```text
examples/
├── yaml/   # supported, tested examples
└── md/     # one supported markdown subset example plus prototypes
```

## Notes

- Several YAML examples use named library steps via `StepLibrary`.
- The supported markdown subset currently accepts only `markpact:config` and `markpact:steps` blocks that compile cleanly to `MigrationSpec`.
- Most markdown examples still include fields such as `when`, `skip_if`, `retry`, and `check_cmd` that are not part of the current `redeploy` runtime.

See [md/README.md](md/README.md) for markdown example notes.
See [../docs/markpact-audit.md](../docs/markpact-audit.md) for the full implementation audit.

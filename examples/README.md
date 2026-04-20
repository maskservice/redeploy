# redeploy Examples

This directory has two different kinds of material.

- `yaml/`: supported examples for the current `redeploy` CLI
- `md/`: markdown prototypes for a proposed markpact-style runtime

## What works today

Use YAML examples with the current CLI.

```bash
redeploy run examples/yaml/01-vps-version-bump/migration.yaml --dry-run
redeploy run examples/yaml/02-k3s-to-docker/migration.yaml --detect
```

YAML examples are the ones exercised by the repository test suite.

## What does not work today

The current `redeploy` CLI does not parse `migration.md` files.
Files under `examples/md/` are design/prototype material only.

They are useful for:

- format exploration
- documenting future runtime ideas
- comparing aspirational markdown semantics with the current YAML model

They are not useful as:

- supported CLI inputs
- test-backed examples
- one-to-one ports of the YAML scenario set

## Directory Overview

```text
examples/
├── yaml/   # supported, tested examples
└── md/     # prototype markdown examples
```

## Notes

- Several YAML examples use named library steps via `StepLibrary`.
- Markdown examples include fields such as `when`, `skip_if`, `retry`, and `check_cmd` that are not part of the current `redeploy` runtime.

See [md/README.md](md/README.md) for markdown prototype notes.
See [../docs/markpact-audit.md](../docs/markpact-audit.md) for the full implementation audit.

# Markpact Audit

This document compares the implementation ideas from the TODO note with the
current state of this repository.

## Status Summary

| Area from TODO | Status | Notes |
| --- | --- | --- |
| Markdown as single source of truth | partial | The CLI can now load `.md` specs through `redeploy.spec_loader.load_migration_spec()`, but only for a constrained markpact subset that compiles into the existing YAML-shaped `MigrationSpec`. |
| `markpact:*` executable blocks | partial | `markpact:config` and `markpact:steps` are now parsed and compiled. `markpact:run`, `markpact:rollback`, `markpact:python`, and similar blocks are still unsupported. |
| Schema and validation | partial | Markdown blocks are parsed and validated against `MigrationSpec`, `InfraSpec`, `MigrationStep`, and `StepLibrary`, but only for the supported Phase 1 subset. |
| Idempotency / execution state | missing | There is no `.deploy-state.json`, no `steps_done`, and no generic step skipping based on prior execution state. |
| Conditional execution like `when`, `skip_if`, `check_cmd` | missing | These fields appear in markdown examples, but they are not part of the current `MigrationStep` model or executor logic. |
| Per-step retry | missing | Retry is not part of `MigrationStep`; the executor only retries HTTP checks internally. |
| Per-step timeout | implemented | `MigrationStep.timeout` exists and is used by the executor and SSH helpers. |
| Persistent SSH session reuse | missing | `SshClient.run()` shells out to `ssh` for each command; there is no persistent connection/session pool. |
| Rollback support | partial | `rollback_command` exists on YAML steps and the executor runs rollback commands for completed steps after a failure, but there is no `markpact:rollback` block support. |
| Structured progress/log output | partial | Markdown specs are compiled into the existing planner/executor path, so supported markdown inherits the same progress events and audit records as YAML. |
| AST-based markdown parsing instead of regex | implemented | The markpact subset is parsed with `markdown-it-py` in `redeploy/redeploy/markpact/parser.py`. |
| Security hardening for markdown execution | missing | There is no sandboxed markdown execution layer in the current codebase. |

## Code Evidence

| Evidence | Meaning |
| --- | --- |
| `redeploy/redeploy/spec_loader.py` | CLI spec loading now routes YAML and markdown through a shared loader. |
| `redeploy/redeploy/markpact/parser.py` | Markdown fences are parsed into `MarkpactBlock` objects with an AST-based parser. |
| `redeploy/redeploy/markpact/compiler.py` | Supported markdown blocks are compiled and validated against the current runtime models. |
| `redeploy/redeploy/models.py` `MigrationStep` | Has `timeout` and `rollback_command`, but no `retry`, `when`, `skip_if`, or `check_cmd`. |
| `redeploy/redeploy/apply/executor.py` | Supports rollback and HTTP retry, but not a generic markdown runtime. |
| `redeploy/redeploy/ssh.py` | Uses subprocess-based `ssh` per call, not a persistent SSH session. |

## Example Parity Audit

The markdown examples in `examples/md/` are not one-to-one ports of the YAML
examples in `examples/yaml/`.

| YAML scenario | Markdown equivalent | Status |
| --- | --- | --- |
| `01-vps-version-bump` | `examples/md/01-vps-version-bump` | partial: supported Phase 1 subset counterpart |
| `02-k3s-to-docker` | `examples/md/02-k3s-to-docker` | partial: supported Phase 1 subset counterpart |
| `03-docker-to-podman-quadlet` | `examples/md/03-docker-to-podman-quadlet` | partial: supported Phase 1 subset counterpart |
| `04-rpi-kiosk` | none | missing |
| `04-rpi-fleet-update` | none | missing |
| `05-iot-fleet-ota` | none | missing |
| `05-self-hosted-to-vps` | none | missing |
| `06-blue-green-deploy` | none | missing |
| `06-local-dev` | none | missing |
| `07-staging-to-prod` | none | missing |
| `08-rollback` | none | missing |
| `09-fleet-yaml` | none | missing |
| `10-multienv` | none | missing |
| `11-traefik-tls` | none | missing |
| `12-ci-pipeline` | none | missing |
| `13-multi-app-monorepo` | none | missing |
| `13-kiosk-appliance.yaml` | none | missing |
| `14-blue-green.yaml` | none | missing |
| `15-canary.yaml` | none | missing |
| `16-auto-rollback.yaml` | none | missing |

Current `examples/md/` content is mostly prototype or exploratory
documentation, with three supported Phase 1 subset examples:

| Markdown example | Nature |
| --- | --- |
| `01-vps-version-bump` | Supported markdown subset example compiled into the current runtime |
| `02-k3s-to-docker` | Supported markdown subset example compiled into the current runtime |
| `03-docker-to-podman-quadlet` | Supported markdown subset example compiled into the current runtime |
| `01-rpi5-deploy` | Custom prototype scenario, not a port of a YAML example |
| `02-multi-language` | Feature demo for mixed block formats |
| `03-all-actions` | Aspirational action catalog, not aligned with current `MigrationStep` model |
| `04-v3-state-reconciliation` | Concept demo for future idempotency/state features |

## Recommendation

Treat `examples/yaml/` as the primary supported, tested path. Treat markdown as
a limited supported subset plus broader prototype material until later phases
add more block kinds and runtime features.

See `docs/markpact-implementation-plan.md` for a minimal staged rollout plan.

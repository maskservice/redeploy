# Markpact Audit

This document compares the implementation ideas from the TODO note with the
current state of this repository.

## Status Summary

| Area from TODO | Status | Notes |
| --- | --- | --- |
| Markdown as single source of truth | missing | The current `redeploy` CLI loads specs through YAML only. `MigrationSpec.from_file()` uses `yaml.safe_load()` and `redeploy run` calls that path directly. |
| `markpact:*` executable blocks | missing | There is no parser or runtime in this repo that reads `markpact:config`, `markpact:steps`, `markpact:run`, or `markpact:rollback` blocks. |
| Schema and validation | partial | Pydantic validation exists for YAML-based specs and plans, but not for markdown/markpact blocks. |
| Idempotency / execution state | missing | There is no `.deploy-state.json`, no `steps_done`, and no generic step skipping based on prior execution state. |
| Conditional execution like `when`, `skip_if`, `check_cmd` | missing | These fields appear in markdown examples, but they are not part of the current `MigrationStep` model or executor logic. |
| Per-step retry | missing | Retry is not part of `MigrationStep`; the executor only retries HTTP checks internally. |
| Per-step timeout | implemented | `MigrationStep.timeout` exists and is used by the executor and SSH helpers. |
| Persistent SSH session reuse | missing | `SshClient.run()` shells out to `ssh` for each command; there is no persistent connection/session pool. |
| Rollback support | partial | `rollback_command` exists on YAML steps and the executor runs rollback commands for completed steps after a failure, but there is no `markpact:rollback` block support. |
| Structured progress/log output | partial | The executor emits YAML progress events and writes audit records, but this is tied to YAML plan execution, not markpact markdown. |
| AST-based markdown parsing instead of regex | missing | No markdown runtime exists in this repo today, so the suggested AST parser migration was not implemented here. |
| Security hardening for markdown execution | missing | There is no sandboxed markdown execution layer in the current codebase. |

## Code Evidence

| Evidence | Meaning |
| --- | --- |
| `redeploy/redeploy/models.py` `MigrationSpec.from_file()` | Specs are loaded as YAML with `yaml.safe_load()`. |
| `redeploy/redeploy/cli.py` `run(...)` | The main CLI path goes straight through `MigrationSpec.from_file()`. |
| `redeploy/redeploy/models.py` `MigrationStep` | Has `timeout` and `rollback_command`, but no `retry`, `when`, `skip_if`, or `check_cmd`. |
| `redeploy/redeploy/apply/executor.py` | Supports rollback and HTTP retry, but not a generic markdown runtime. |
| `redeploy/redeploy/ssh.py` | Uses subprocess-based `ssh` per call, not a persistent SSH session. |

## Example Parity Audit

The markdown examples in `examples/md/` are not one-to-one ports of the YAML
examples in `examples/yaml/`.

| YAML scenario | Markdown equivalent | Status |
| --- | --- | --- |
| `01-vps-version-bump` | none | missing |
| `02-k3s-to-docker` | none | missing |
| `03-docker-to-podman-quadlet` | none | missing |
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

Current `examples/md/` content is better described as prototype or exploratory
documentation:

| Markdown example | Nature |
| --- | --- |
| `01-rpi5-deploy` | Custom prototype scenario, not a port of a YAML example |
| `02-multi-language` | Feature demo for mixed block formats |
| `03-all-actions` | Aspirational action catalog, not aligned with current `MigrationStep` model |
| `04-v3-state-reconciliation` | Concept demo for future idempotency/state features |

## Recommendation

Treat `examples/yaml/` as the supported, tested path and `examples/md/` as
design/prototype material until a real markdown runtime is added to this repo.

See `docs/markpact-implementation-plan.md` for a minimal staged rollout plan.

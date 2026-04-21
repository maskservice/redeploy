# op3 Migration Guide

This document describes how `redeploy` integrates with the `op3` (layered-operations-tree) package and how to migrate from legacy detection paths to the op3-backed code paths.

## Feature Flag

All op3-backed paths are gated by the environment variable:

```bash
export REDEPLOY_USE_OP3=1   # enable op3 scanners
unset REDEPLOY_USE_OP3      # use legacy Detector / SSH probes (default)
```

## Commands with op3 Forks

| Command | Legacy Path | op3 Path (when flag is on) |
|---|---|---|
| `redeploy detect <host>` | `Detector.run()` → manual SSH | `op3` snapshot → `InfraState` via `snapshot_to_infra_state` |
| `redeploy blueprint capture --host <host>` | `Detector(host).run()` | `op3` snapshot → `DeviceMap` via `snapshot_to_device_map` |
| `redeploy hardware <host>` | manual SSH commands | `op3` snapshot → `HardwareInfo` via `snapshot_to_hardware_info` |

## Adapter Functions

The bridge lives in `redeploy/integrations/op3_bridge.py`.

- `snapshot_to_infra_state(snapshot, host=...)` → `redeploy.InfraState`
- `snapshot_to_device_map(snapshot, host=..., tags=...)` → `redeploy.DeviceMap`
- `snapshot_to_hardware_info(snapshot)` → `redeploy.HardwareInfo`

## Running Tests

Contract tests verify parity between legacy and op3 outputs:

```bash
# Legacy path
REDEPLOY_USE_OP3=0 uv run pytest tests/contract/ -v

# op3 path
REDEPLOY_USE_OP3=1 uv run pytest tests/contract/ -v
```

## CI Matrix

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs both variants across Python 3.11–3.13.

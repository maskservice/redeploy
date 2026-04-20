# 10 — Multi-Environment Pipeline

Three separate spec files for the same app: `dev` → `staging` → `prod`.

## Files

```
10-multienv/
├── redeploy.yaml   ← project manifest: spec=prod.yaml, local_spec=dev.yaml
├── dev.yaml        ← local Docker rebuild (no SSH)
├── staging.yaml    ← staging VPS deploy
├── prod.yaml       ← production VPS deploy
└── README.md
```

## When to use

- Same app deployed across multiple environments
- Promote validated build through environments before touching prod
- `redeploy.yaml` picks `local_spec` for local runs, `spec` for remote

## Run

```bash
# Local dev iteration
redeploy run examples/10-multienv/dev.yaml

# Deploy to staging
redeploy run examples/10-multienv/staging.yaml --detect

# Deploy to prod (after staging passes)
redeploy run examples/10-multienv/prod.yaml --detect

# OR: redeploy.yaml auto-selects spec based on invocation
cd examples/10-multienv
redeploy run              # uses prod.yaml (spec:)
redeploy run --local      # uses dev.yaml (local_spec:)
```

## Convention

| File | `host` | Environment |
|------|--------|-------------|
| `dev.yaml` | `local` | Developer laptop |
| `staging.yaml` | `root@10.0.0.10` | Staging VPS |
| `prod.yaml` | `root@87.106.87.183` | Production VPS |

All three share the same app, version, and compose files — only `host`, `domain`, and `env_file` differ.

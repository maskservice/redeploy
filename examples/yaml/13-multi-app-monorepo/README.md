# 13 — Multi-App Monorepo

Deploy multiple apps from a single monorepo to one VPS in a single `redeploy run`.

## Files

```
13-multi-app-monorepo/
├── redeploy.yaml        ← project manifest
├── migration.yaml       ← deploy c2004 + fleet together
├── fleet.yaml           ← all environments for the monorepo
└── README.md
```

## When to use

- Monorepo with `c2004/`, `fleet/`, etc. as subdirectories
- All apps deployed to same VPS, single docker-compose.vps.yml
- Build context at `~/apps/` parent dir

## Run

```bash
# Dry-run
redeploy run examples/13-multi-app-monorepo/migration.yaml --dry-run

# Deploy
redeploy run examples/13-multi-app-monorepo/migration.yaml --detect
```

## Monorepo directory layout on VPS

```
~/apps/
├── c2004/                ← rsync'd from ./c2004/
├── fleet/                ← rsync'd from ./fleet/
├── docker-compose.vps.yml  ← promoted from c2004/ before build
└── .env                  ← uploaded via sync_env step
```

## fleet.yaml query examples

```python
from redeploy.fleet import FleetConfig, Stage

fleet = FleetConfig.from_file("examples/13-multi-app-monorepo/fleet.yaml")

# All prod devices
fleet.prod_devices()              # [vps-prod-c2004]

# All monorepo devices
fleet.by_tag("monorepo")          # [vps-prod-c2004, vps-staging-c2004, docker-local]

# Staging only
fleet.by_stage(Stage.STAGING)     # [vps-staging-c2004]
```

## Notes

- `rsync_app` steps use `insert_before: docker_build_pull` — files synced before image build
- `promote_compose` copies `docker-compose.vps.yml` to the build context root (`~/apps/`)
- Both `c2004` and `fleet` use a single `docker-compose.vps.yml` with multiple services

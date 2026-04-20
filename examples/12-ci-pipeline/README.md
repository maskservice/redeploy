# 12 — CI Pipeline Integration

Automate deploys from GitHub Actions or GitLab CI on tag push.

## Files

```
12-ci-pipeline/
├── redeploy.yaml
├── migration.yaml
├── deploy.github.yml    ← GitHub Actions workflow
├── deploy.gitlab.yml    ← GitLab CI job definition
└── README.md
```

## When to use

- CD pipeline: push tag → auto deploy to VPS
- SSH key stored in CI secrets
- `.env` injected from CI secrets (never stored in repo)

## GitHub Actions setup

1. Copy `deploy.github.yml` to `.github/workflows/deploy.yml`
2. Add secrets in repo settings:
   - `SSH_PRIVATE_KEY` — private key for VPS (public key in `~/.ssh/authorized_keys` on VPS)
   - `VPS_ENV` — full contents of `envs/vps.env`
3. Push a version tag: `git tag v1.0.21 && git push --tags`

## GitLab CI setup

1. Paste `deploy.gitlab.yml` content into your `.gitlab-ci.yml`
2. Add CI/CD variables:
   - `SSH_PRIVATE_KEY`, `VPS_ENV`

## How it works

```
tag push v1.0.21
  → CI checkout
  → pip install redeploy
  → write SSH key + .env (from secrets)
  → redeploy run migration.yaml --detect
      → live probe VPS
      → plan (conflict fixes + docker build + health check)
      → apply
      → verify 1.0.21 responding
```

## Run

```bash
# Local dry-run (no SSH)
redeploy run examples/12-ci-pipeline/migration.yaml --plan-only

# CI: after writing SSH key + .env from secrets
redeploy run examples/12-ci-pipeline/migration.yaml --detect
```

## Notes

- `--detect` probes the VPS live — detects stale k3s iptables, generates conflict-fix steps automatically
- Version is injected from git tag: `SERVICE_VERSION=${GITHUB_REF_NAME#v}` strips the `v` prefix

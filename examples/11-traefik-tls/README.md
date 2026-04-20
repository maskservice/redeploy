# 11 — Traefik TLS Termination

Add HTTPS (TLS) to an existing Docker Compose + Traefik stack via cert files.

## Files

```
11-traefik-tls/
├── redeploy.yaml
├── migration.yaml
├── traefik/
│   └── dynamic/
│       └── tls.yml        ← Traefik file provider: points to /certs/cert.pem
└── README.md
```

## When to use

- Traefik running but serving HTTP only (or wrong cert)
- Cloudflare **Full** mode (not strict) — self-signed or Origin Certificate
- Need to upload cert + force-recreate Traefik without full stack downtime

## Prerequisites

1. `traefik/certs/cert.pem` and `traefik/certs/key.pem` present locally
2. `docker-compose.vps.yml` has Traefik volume mounts:
   ```yaml
   volumes:
     - ./traefik/certs:/certs:ro
     - ./traefik/dynamic:/traefik/dynamic:ro
   ```
3. Traefik command includes:
   ```yaml
   command:
     - "--providers.file.directory=/traefik/dynamic"
     - "--providers.file.watch=true"
     - "--entrypoints.websecure.http.tls=true"
   ```

## Run

```bash
# Dry-run first
redeploy run examples/11-traefik-tls/migration.yaml --dry-run

# Apply
redeploy run examples/11-traefik-tls/migration.yaml
```

## tls.yml

```yaml
tls:
  certificates:
    - certFile: /certs/cert.pem
      keyFile: /certs/key.pem
```

Traefik's file provider watches `/traefik/dynamic/` — any `.yml` there is loaded automatically (no restart needed for cert rotation).

## Cert options

| Option | Mode | Notes |
|--------|------|-------|
| Cloudflare Origin Cert | Full (not strict) | 15-year cert, free |
| Self-signed (mkcert) | Full (not strict) | Must match domain |
| Let's Encrypt ACME | Full strict | Use `--certificatesresolvers` flags |

# 04 — Raspberry Pi Kiosk (native_kiosk)

Update a native kiosk deployment on Raspberry Pi (no Docker — systemd + Chromium).

## When to use

- RPi3 / RPi4 running Python backend + nginx frontend as systemd services
- Chromium in full-screen kiosk mode
- Low RAM — Docker too heavy

## Prerequisites

- RPi reachable via SSH (`pi@<ip>`)
- systemd units `c2004-backend` and `c2004-frontend` installed
- Chromium installed, `DISPLAY=:0` available

## Run

```bash
redeploy run examples/04-rpi-kiosk/migration.yaml --detect --dry-run
redeploy run examples/04-rpi-kiosk/migration.yaml --detect
```

## What happens

| Step | Action |
|------|--------|
| `stop_kiosk_browser` | Kill Chromium |
| `rsync_app` | Sync updated source |
| `restart_backend` | `systemctl restart c2004-backend` |
| `restart_frontend` | `systemctl restart c2004-frontend` (nginx) |
| `wait_startup` | 15 s |
| `http_health_check` | `curl localhost:8000/api/v1/health` |
| `version_check` | Verify version |
| `restart_kiosk_browser` | Relaunch Chromium kiosk |

## Notes

- `loginctl enable-linger pi` — kiosk units survive SSH logout
- For DSI display rotation add `wlr-randr --output DSI-2 --transform 90` step

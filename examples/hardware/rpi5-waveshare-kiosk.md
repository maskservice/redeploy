# RPi5 Waveshare 8" — pełny kiosk Wayland (labwc + Chromium)

Kompletna konfiguracja kiosku na Raspberry Pi 5 z panelem Waveshare 8" DSI.
Zakodowane doświadczenie z sesji pi109.

## Kluczowe lekcje z pi109

- `--password-store=basic` jest WYMAGANE — bez tego GNOME Keyring blokuje start Chromium
- `--windowed` jest NIEZGODNY z `--kiosk` pod labwc — usuń go
- kanshi musi wystartować PRZED Chromium i mieć czas na wyłączenie HDMI-A-2
- `sleep 3` w autostart daje kanshi czas na aplikację profilu DSI-only
- overlay musi mieć `_a` na końcu: `vc4-kms-dsi-waveshare-panel-v2,8_0_inch_a`

## Diagram sekwencji startu

```
RPi5 boot
  → labwc (compositor)
    → kanshid &             # output manager
      → sleep 3            # czeka na profil waveshare-only
        → kiosk-launch.sh  # Chromium z --kiosk --password-store=basic
```

## Spec migracji

```yaml markpact:config
name: "rpi5-waveshare-kiosk"
description: "Kiosk Wayland — RPi5 + Waveshare 8-cal DSI + labwc + Chromium"

target:
  strategy: kiosk_appliance
  host: pi@192.168.188.109

hardware:
  panel: waveshare-8-inch
  port: dsi1

extra_steps:

  # ── 1. config.txt ─────────────────────────────────────────────────────────

  - id: backup_config
    action: ssh_cmd
    description: Backup /boot/firmware/config.txt
    command: sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.bak.$(date +%s)

  - id: set_kms_overlay
    action: ensure_config_line
    description: Włącz KMS (vc4-kms-v3d)
    config_file: /boot/firmware/config.txt
    config_line: "dtoverlay=vc4-kms-v3d"
    config_section: all

  - id: set_dsi_overlay
    action: ensure_config_line
    description: "Overlay DSI Waveshare 8-cal (wariant _a — wymagany dla labwc)"
    config_file: /boot/firmware/config.txt
    config_line: "dtoverlay=vc4-kms-dsi-waveshare-panel-v2,8_0_inch_a"
    config_replaces_pattern: "^dtoverlay=vc4-kms-dsi-.*"
    config_section: all

  - id: enable_i2c
    action: raspi_config
    description: Włącz I2C (dotyk Waveshare)
    raspi_interface: i2c
    raspi_state: enable

  # ── 2. kanshi — profil DSI-only ───────────────────────────────────────────
  # Pi109: HDMI-A-2 musi być wyłączane PRZED startem Chromium.
  # Jeśli HDMI-A-2 jest aktywne, Chromium może otworzyć się na nim zamiast DSI-2.

  - id: write_kanshi_profile
    action: ensure_kanshi_profile
    description: "Kanshi: włącz DSI-2, wyłącz HDMI-A-1 i HDMI-A-2"
    config_file: ~/.config/kanshi/config
    command: |
      profile waveshare-only {
          output DSI-2 enable
          output HDMI-A-1 disable
          output HDMI-A-2 disable
      }

  # ── 3. labwc autostart ────────────────────────────────────────────────────
  # Pi109: kolejność ma znaczenie: kanshid & → sleep 3 → kiosk-launch.sh &

  - id: autostart_kanshi
    action: ensure_autostart_entry
    description: "Autostart: kanshid (musi być pierwszy)"
    config_file: ~/.config/labwc/autostart
    config_line: "kanshid &"
    config_section: kanshi

  - id: autostart_settle
    action: ensure_autostart_entry
    description: "Autostart: sleep 3 po kanshi (czas na profil DSI-only)"
    config_file: ~/.config/labwc/autostart
    config_line: "sleep 3"
    config_section: kanshi-settle

  - id: autostart_browser
    action: ensure_autostart_entry
    description: "Autostart: kiosk-launch.sh"
    config_file: ~/.config/labwc/autostart
    config_line: "bash ~/kiosk-launch.sh &"
    config_section: kiosk-browser

  # ── 4. kiosk-launch.sh ────────────────────────────────────────────────────
  # Pi109 wymagane flagi:
  #   --kiosk                  pełny ekran bez ramki
  #   --password-store=basic   GNOME Keyring blokuje bez tego!
  #   --noerrdialogs           ukrywa okna błędów GPU
  #   --ozone-platform=wayland jawne wskazanie backendu (bez X11 fallback)

  - id: write_kiosk_script
    action: ensure_browser_kiosk_script
    description: "Zapisz ~/kiosk-launch.sh z poprawnymi flagami Chromium"
    dst: ~/kiosk-launch.sh
    command: |
      #!/bin/bash
      # kiosk-launch.sh — wygenerowany przez redeploy (rpi5-waveshare-kiosk)
      # Pi109: --password-store=basic jest WYMAGANE (GNOME Keyring blokuje start)
      # Pi109: NIE używaj --windowed razem z --kiosk pod labwc
      export XDG_SESSION_TYPE=wayland
      unset DISPLAY
      chromium-browser \
        --kiosk \
        --password-store=basic \
        --noerrdialogs \
        --disable-infobars \
        --disable-session-crashed-bubble \
        --disable-features=TranslateUI \
        --ozone-platform=wayland \
        --enable-features=UseOzonePlatform \
        http://localhost:8080

  # ── 5. reboot i weryfikacja ──────────────────────────────────────────────

  - id: reboot
    action: ssh_cmd
    description: Reboot po konfiguracji
    command: sudo reboot

  - id: wait_boot
    action: wait
    seconds: 90

  - id: verify_dsi_connected
    action: ssh_cmd
    description: "Sprawdź czy DSI-2 ma EDID (panel fizycznie podłączony)"
    command: "cat /sys/class/drm/card*/card*-DSI-2/edid | wc -c"

  - id: verify_kanshi_running
    action: ssh_cmd
    description: "Sprawdź czy kanshi działa"
    command: "pgrep -x kanshi && echo OK || echo NOT_RUNNING"

  - id: verify_chromium_running
    action: ssh_cmd
    description: "Sprawdź czy Chromium działa w kiosku"
    command: "pgrep -a chromium | grep kiosk | head -3"
```

## Uruchomienie

```bash
redeploy run examples/hardware/rpi5-waveshare-kiosk.md --progress-yaml
```

## Diagnostyka po instalacji

```bash
# Pełna diagnostyka hardware
redeploy hardware pi@192.168.188.109

# Sprawdź profil kanshi
ssh pi@192.168.188.109 cat ~/.config/kanshi/config

# Sprawdź autostart
ssh pi@192.168.188.109 cat ~/.config/labwc/autostart

# Sprawdź kiosk-launch.sh
ssh pi@192.168.188.109 cat ~/kiosk-launch.sh

# Aktywne wyjścia DRM
ssh pi@192.168.188.109 'for f in /sys/class/drm/card*/*/status; do echo "$f: $(cat $f)"; done'
```

## Typowe problemy

| Objaw | Przyczyna | Rozwiązanie |
|-------|-----------|-------------|
| Chromium pokazuje okno logowania | Brak `--password-store=basic` | Dodaj flagę do kiosk-launch.sh |
| Chromium nie jest pełnoekranowy | `--windowed` w skrypcie | Usuń `--windowed` |
| Czarny ekran po starcie | Chromium startuje przed kanshi | Zwiększ `sleep` w autostart |
| Obraz na HDMI zamiast DSI | kanshi nie wyłączył HDMI-A-2 | Sprawdź profil kanshi |
| `dmesg: panel missing` | Zły overlay (brak `_a`) | Użyj `8_0_inch_a` nie `8_0_inch` |

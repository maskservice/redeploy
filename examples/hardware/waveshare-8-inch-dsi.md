# Waveshare 8" DSI na RPi5

Konfiguracja panelu Waveshare 1280×800 + dotyk I2C na Raspberry Pi 5.

```yaml markpact:config
name: "waveshare-8-inch-dsi-setup"
description: "Konfiguracja Waveshare 8-cal DSI na RPi5"

target:
  strategy: hardware_config
  host: pi@192.168.188.109

hardware:
  panel: waveshare-8-inch
  port: dsi1

extra_steps:
  - id: backup_config_txt
    action: ssh_cmd
    description: Backup config.txt
    command: sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.bak.$(date +%s)

  - id: ensure_kms
    action: ensure_config_line
    config_file: /boot/firmware/config.txt
    config_line: "dtoverlay=vc4-kms-v3d"
    config_section: all

  - id: set_waveshare_overlay
    action: ensure_config_line
    config_file: /boot/firmware/config.txt
    config_line: "dtoverlay=vc4-kms-dsi-waveshare-panel-v2,8_0_inch"
    config_replaces_pattern: "^dtoverlay=vc4-kms-dsi-.*"
    config_section: all

  - id: enable_i2c
    action: raspi_config
    raspi_interface: i2c
    raspi_state: enable

  - id: reboot_rpi5
    action: ssh_cmd
    command: sudo reboot

  - id: wait_for_rpi5
    action: wait
    seconds: 120

  - id: verify_dsi
    action: ssh_cmd
    command: "dmesg | grep -iE 'dsi|vc4|panel' | tail -20"
```

## Uruchomienie

```bash
redeploy run examples/hardware/waveshare-8-inch-dsi.md --progress-yaml
```

## Uwagi

- Port DSI1 jest domyślny dla RPi5
- Jeśli dotyk nie reaguje, sprawdź I2C w raspi-config
- Reboot jest wymagany po zmianie overlay

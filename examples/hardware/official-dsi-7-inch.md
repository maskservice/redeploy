# Official Raspberry Pi 7" DSI

Konfiguracja oficjalnego panelu Raspberry Pi 7" DSI z dotykiem.

```yaml markpact:config
name: "official-dsi-7-inch-setup"
description: "Konfiguracja oficjalnego panelu 7-cal DSI na RPi"

target:
  strategy: hardware_config
  host: pi@192.168.188.109

hardware:
  panel: official-dsi-7-inch
  port: dsi1

extra_steps:
  - id: backup_config_txt
    action: ssh_cmd
    description: Backup config.txt
    command: sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.bak.$(date +%s)

  - id: set_dpi_panel
    action: ensure_config_line
    config_file: /boot/firmware/config.txt
    config_line: "dtoverlay=vc4-kms-dpi-panel"
    config_replaces_pattern: "^dtoverlay=vc4-kms-dpi-.*"
    config_section: all

  - id: enable_i2c
    action: raspi_config
    raspi_interface: i2c
    raspi_state: enable

  - id: reboot_rpi
    action: ssh_cmd
    command: sudo reboot

  - id: wait_for_rpi
    action: wait
    seconds: 90

  - id: verify_dsi
    action: ssh_cmd
    command: "dmesg | grep -iE 'dsi|vc4|panel' | tail -20"
```

## Uruchomienie

```bash
redeploy run examples/hardware/official-dsi-7-inch.md --progress-yaml
```

## Uwagi

- Oficjalny panel DPI (nie DSI) z I2C touch
- Rozdzielczość 800×480
- Wymaga I2C dla sterownika dotyku

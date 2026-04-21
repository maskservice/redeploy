# Włączanie I2C i SPI

Włączanie interfejsów I2C i SPI na Raspberry Pi przez raspi-config.

```yaml markpact:config
name: "enable-i2c-spi"
description: "Włącz interfejsy I2C i SPI na RPi"

target:
  strategy: hardware_config
  host: pi@192.168.188.109

extra_steps:
  - id: enable_i2c
    action: raspi_config
    raspi_interface: i2c
    raspi_state: enable

  - id: enable_spi
    action: raspi_config
    raspi_interface: spi
    raspi_state: enable

  - id: verify_i2c
    action: ssh_cmd
    description: "Zweryfikuj I2C w /boot/config.txt"
    command: grep -E "dtparam=i2c|dtoverlay=i2c" /boot/firmware/config.txt

  - id: verify_spi
    action: ssh_cmd
    description: "Zweryfikuj SPI w /boot/config.txt"
    command: grep -E "dtparam=spi|dtoverlay=spi" /boot/firmware/config.txt
```

## Uruchomienie

```bash
redeploy run examples/hardware/enable-i2c-spi.md --progress-yaml
```

## Uwagi

- Nie wymaga rebootu
- Zmiany są natychmiastowe
- Przydatne dla sensorów i paneli dotykowych

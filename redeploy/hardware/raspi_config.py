"""Wrapper for raspi-config nonint mode."""
from __future__ import annotations


def build_raspi_config_command(interface: str, state: str) -> str:
    """
    Build a raspi-config nonint command.
    
    Args:
        interface: i2c, spi, camera, onewire, ssh, vnc, serial
        state: enable, disable
    
    Returns:
        Full command string
    """
    flag_map = {"enable": "0", "disable": "1"}
    action_map = {
        "i2c": "do_i2c",
        "spi": "do_spi",
        "camera": "do_camera",
        "onewire": "do_onewire",
        "ssh": "do_ssh",
        "vnc": "do_vnc",
        "serial": "do_serial",
    }
    
    if interface not in action_map:
        raise ValueError(f"Unknown interface: {interface}")
    if state not in flag_map:
        raise ValueError(f"Unknown state: {state}")
    
    return f"sudo raspi-config nonint {action_map[interface]} {flag_map[state]}"

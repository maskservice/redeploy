"""Hardware diagnostic plugin for redeploy.

Analyzes system hardware and provides configuration recommendations.
Supports Raspberry Pi variants and desktop platforms.

Usage in deployment.yaml:
    extra_steps:
      - id: analyze_hardware
        action: plugin
        plugin_type: hardware_diagnostic
        plugin_params:
          checks: ["platform", "cpu", "memory", "storage", "gpio", "usb", "audio"]
          platform: "auto"  # or "rpi3", "rpi4", "rpi5", "desktop"
          verbose: true
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from loguru import logger

from redeploy.plugins import PluginContext, register_plugin


@dataclass
class HardwareInfo:
    """Hardware diagnostic information."""
    platform: str
    cpu_model: str
    cpu_cores: int
    memory_mb: int
    storage_gb: float
    gpio_available: bool
    usb_devices: List[str]
    audio_devices: List[str]
    network_interfaces: List[str]
    issues: List[str]
    recommendations: List[str]


def _run_command(cmd: str) -> str:
    """Run shell command and return output."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return result.stdout.strip()
    except Exception as e:
        logger.debug(f"Command failed: {cmd} - {e}")
        return ""


def _detect_platform() -> str:
    """Detect the platform type."""
    # Check for Raspberry Pi
    model_file = "/proc/device-tree/model"
    if os.path.exists(model_file):
        try:
            with open(model_file, "r") as f:
                model = f.read().strip("\x00")
                if "Raspberry Pi 5" in model:
                    return "rpi5"
                elif "Raspberry Pi 4" in model:
                    return "rpi4"
                elif "Raspberry Pi 3" in model:
                    return "rpi3"
        except Exception:
            pass

    # Check CPU info
    cpuinfo = _run_command("cat /proc/cpuinfo")
    if "Raspberry Pi" in cpuinfo or "BCM" in cpuinfo:
        return "rpi_unknown"

    # Check architecture
    arch = _run_command("uname -m")
    if arch == "aarch64":
        return "arm64_unknown"
    elif arch == "x86_64":
        return "desktop"

    return "unknown"


def _get_cpu_info() -> tuple[str, int]:
    """Get CPU model and core count."""
    cpuinfo = _run_command("cat /proc/cpuinfo")
    model = "unknown"
    cores = 0

    for line in cpuinfo.split("\n"):
        if line.startswith("model name"):
            model = line.split(":", 1)[1].strip()
        elif line.startswith("Hardware"):
            model = line.split(":", 1)[1].strip()
        elif line.startswith("processor"):
            cores += 1

    return model, max(cores, 1)


def _get_memory_mb() -> int:
    """Get total memory in MB."""
    meminfo = _run_command("cat /proc/meminfo")
    for line in meminfo.split("\n"):
        if line.startswith("MemTotal"):
            kb = int(line.split()[1])
            return kb // 1024
    return 0


def _get_storage_gb() -> float:
    """Get available storage in GB."""
    output = _run_command("df -h /")
    if output:
        lines = output.split("\n")
        if len(lines) > 1:
            parts = lines[1].split()
            if len(parts) > 3:
                available = parts[3]
                if available.endswith("G"):
                    return float(available.rstrip("G"))
                elif available.endswith("M"):
                    return float(available.rstrip("M")) / 1024
    return 0.0


def _check_gpio() -> bool:
    """Check if GPIO is available."""
    # Check for GPIO character device
    return os.path.exists("/dev/gpiochip0") or os.path.exists("/dev/gpiomem")


def _get_usb_devices() -> List[str]:
    """Get list of USB devices."""
    output = _run_command("lsusb")
    devices = []
    for line in output.split("\n"):
        if line:
            parts = line.split(" ", 6)
            if len(parts) > 6:
                devices.append(parts[6])
    return devices


def _get_audio_devices() -> List[str]:
    """Get list of audio devices."""
    output = _run_command("aplay -l")
    devices = []
    for line in output.split("\n"):
        if line.startswith("card"):
            devices.append(line.strip())
    return devices


def _get_network_interfaces() -> List[str]:
    """Get list of network interfaces."""
    output = _run_command("ip -o link show")
    interfaces = []
    for line in output.split("\n"):
        if line:
            parts = line.split(":")
            if len(parts) > 1:
                iface = parts[1].strip()
                if iface != "lo":
                    interfaces.append(iface)
    return interfaces


def _analyze_hardware(platform: str, verbose: bool = False) -> HardwareInfo:
    """Perform comprehensive hardware analysis."""
    platform = platform if platform != "auto" else _detect_platform()
    cpu_model, cpu_cores = _get_cpu_info()
    memory_mb = _get_memory_mb()
    storage_gb = _get_storage_gb()
    gpio_available = _check_gpio()
    usb_devices = _get_usb_devices()
    audio_devices = _get_audio_devices()
    network_interfaces = _get_network_interfaces()

    issues = []
    recommendations = []

    # Platform-specific checks
    if platform.startswith("rpi"):
        if memory_mb < 1024:
            issues.append(f"Low memory: {memory_mb}MB (recommended: >= 2GB for RPi)")
            recommendations.append("Consider upgrading to RPi4/5 with 2GB+ RAM")
        if storage_gb < 5:
            issues.append(f"Low storage: {storage_gb}GB (recommended: >= 8GB)")
            recommendations.append("Free up disk space or use larger SD card")

        if platform == "rpi5":
            if not gpio_available:
                issues.append("GPIO not available on RPi5")
                recommendations.append("Check kernel configuration for GPIO support")
        elif platform in ["rpi3", "rpi4"]:
            if not gpio_available:
                issues.append("GPIO not available")
                recommendations.append("Enable GPIO in config.txt or check permissions")

    elif platform == "desktop":
        if memory_mb < 4096:
            issues.append(f"Low memory: {memory_mb}MB (recommended: >= 4GB for desktop)")
            recommendations.append("Consider upgrading RAM for better performance")

    # General checks
    if not network_interfaces:
        issues.append("No network interfaces detected")
        recommendations.append("Check network configuration")

    if verbose:
        logger.info(f"Platform: {platform}")
        logger.info(f"CPU: {cpu_model} ({cpu_cores} cores)")
        logger.info(f"Memory: {memory_mb}MB")
        logger.info(f"Storage: {storage_gb}GB available")
        logger.info(f"GPIO: {'Available' if gpio_available else 'Not available'}")
        logger.info(f"USB devices: {len(usb_devices)}")
        logger.info(f"Audio devices: {len(audio_devices)}")
        logger.info(f"Network interfaces: {network_interfaces}")

    return HardwareInfo(
        platform=platform,
        cpu_model=cpu_model,
        cpu_cores=cpu_cores,
        memory_mb=memory_mb,
        storage_gb=storage_gb,
        gpio_available=gpio_available,
        usb_devices=usb_devices,
        audio_devices=audio_devices,
        network_interfaces=network_interfaces,
        issues=issues,
        recommendations=recommendations,
    )


@register_plugin("hardware_diagnostic")
def hardware_diagnostic(ctx: PluginContext) -> None:
    """Perform hardware diagnostics and provide recommendations."""
    checks = ctx.params.get("checks", ["platform", "cpu", "memory", "storage"])
    platform = ctx.params.get("platform", "auto")
    verbose = ctx.params.get("verbose", True)
    dry_run = ctx.dry_run

    if dry_run:
        logger.info("[DRY RUN] Would analyze hardware")
        ctx.step.status = "done"
        ctx.step.result = "dry_run"
        return

    logger.info("Starting hardware diagnostic...")

    hw_info = _analyze_hardware(platform, verbose)

    # Build result message
    result_parts = []
    result_parts.append(f"Platform: {hw_info.platform}")
    result_parts.append(f"CPU: {hw_info.cpu_model} ({hw_info.cpu_cores} cores)")
    result_parts.append(f"Memory: {hw_info.memory_mb}MB")
    result_parts.append(f"Storage: {hw_info.storage_gb}GB")
    result_parts.append(f"GPIO: {'OK' if hw_info.gpio_available else 'N/A'}")

    if hw_info.issues:
        result_parts.append(f"Issues: {len(hw_info.issues)}")
        for issue in hw_info.issues:
            logger.warning(f"  - {issue}")

    if hw_info.recommendations:
        result_parts.append(f"Recommendations: {len(hw_info.recommendations)}")
        for rec in hw_info.recommendations:
            logger.info(f"  - {rec}")

    ctx.step.result = "; ".join(result_parts)
    ctx.step.description = f"Hardware diagnostic: {hw_info.platform}, {hw_info.memory_mb}MB RAM"

    if hw_info.issues:
        ctx.step.status = "done"  # Still done, but with warnings
        logger.warning(f"Hardware diagnostic completed with {len(hw_info.issues)} issues")
    else:
        ctx.step.status = "done"
        logger.info("Hardware diagnostic completed successfully")

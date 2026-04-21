"""Fix-plan generators: HardwareInfo + PanelDefinition → list[MigrationStep]."""
from __future__ import annotations

from typing import Callable

from redeploy.models import ConflictSeverity, MigrationStep, StepAction, HardwareInfo
from redeploy.hardware.panels import PanelDefinition, infer_from_hardware


def _step(
    id: str,
    action: StepAction,
    description: str,
    risk: ConflictSeverity = ConflictSeverity.LOW,
    **kw,
) -> MigrationStep:
    return MigrationStep(id=id, action=action, description=description, risk=risk, **kw)


def _detect_port(hw: HardwareInfo) -> str:
    """Detect which DSI port has a connected display."""
    for output in hw.drm_outputs:
        if "DSI" in output.name and output.status == "connected":
            if "DSI-1" in output.name:
                return "dsi1"
            if "DSI-0" in output.name:
                return "dsi0"
    return "dsi1"  # safe default


# ── fix generators ────────────────────────────────────────────────────────────

def fix_dsi_not_enabled(
    hw: HardwareInfo,
    panel: PanelDefinition | None = None,
) -> list[MigrationStep]:
    """Generate steps to configure DSI panel + reboot + verify."""
    panel = panel or infer_from_hardware(hw)
    if panel is None:
        raise ValueError(
            "Cannot infer panel from hardware — specify --panel <id> explicitly. "
            "Run 'redeploy hardware --list-panels' for available IDs."
        )

    port = _detect_port(hw)
    config_path = hw.config_txt_path
    steps: list[MigrationStep] = []

    # 1. Backup
    steps.append(_step(
        id="backup_config_txt",
        action=StepAction.SSH_CMD,
        description="Backup config.txt before editing",
        command=(
            f"sudo cp {config_path} {config_path}.bak.$(date +%Y%m%d_%H%M%S)"
        ),
        risk=ConflictSeverity.LOW,
    ))

    # 2. KMS overlay (if not already present)
    if panel.requires_kms:
        steps.append(_step(
            id="ensure_kms",
            action=StepAction.ENSURE_CONFIG_LINE,
            description="Enable KMS driver (vc4-kms-v3d)",
            config_file=config_path,
            config_line="dtoverlay=vc4-kms-v3d",
            config_replaces_pattern=r"^#?\s*dtoverlay=vc4-kms-v3d",
            config_section="all",
            risk=ConflictSeverity.MEDIUM,
        ))

    # 3. Panel overlay
    steps.append(_step(
        id="set_panel_overlay",
        action=StepAction.ENSURE_CONFIG_LINE,
        description=f"Set overlay for {panel.name}",
        config_file=config_path,
        config_line=panel.overlay_line(port=port),
        config_replaces_pattern=r"^dtoverlay=vc4-kms-dsi-.*",
        config_section="all",
        risk=ConflictSeverity.MEDIUM,
    ))

    # 4. I2C for touch (if needed)
    if panel.requires_i2c_touch:
        steps.append(_step(
            id="enable_i2c",
            action=StepAction.RASPI_CONFIG,
            description="Enable I2C for touch controller",
            raspi_interface="i2c",
            raspi_state="enable",
            risk=ConflictSeverity.LOW,
        ))

    # 5. SPI for touch (if needed)
    if panel.requires_spi_touch:
        steps.append(_step(
            id="enable_spi",
            action=StepAction.RASPI_CONFIG,
            description="Enable SPI for touch controller",
            raspi_interface="spi",
            raspi_state="enable",
            risk=ConflictSeverity.LOW,
        ))

    # 6. Reboot
    steps.append(_step(
        id="reboot_rpi",
        action=StepAction.SSH_CMD,
        description="Reboot — required by overlay change",
        command="sudo reboot",
        risk=ConflictSeverity.HIGH,
    ))

    # 7. Wait
    steps.append(_step(
        id="wait_for_rpi",
        action=StepAction.WAIT,
        description="Wait for RPi to come back online",
        seconds=90,
        risk=ConflictSeverity.MEDIUM,
    ))

    # 8. Verify
    steps.append(_step(
        id="verify_dsi_initialized",
        action=StepAction.SSH_CMD,
        description="Verify DSI initialized in dmesg",
        command="dmesg | grep -iE 'dsi|vc4|panel' | tail -20",
        risk=ConflictSeverity.LOW,
    ))

    return steps


def fix_enable_i2c(
    hw: HardwareInfo,
    panel: PanelDefinition | None = None,
) -> list[MigrationStep]:
    """Enable I2C interface via raspi-config."""
    return [_step(
        id="enable_i2c",
        action=StepAction.RASPI_CONFIG,
        description="Enable I2C",
        raspi_interface="i2c",
        raspi_state="enable",
        risk=ConflictSeverity.LOW,
    )]


def fix_enable_spi(
    hw: HardwareInfo,
    panel: PanelDefinition | None = None,
) -> list[MigrationStep]:
    """Enable SPI interface via raspi-config."""
    return [_step(
        id="enable_spi",
        action=StepAction.RASPI_CONFIG,
        description="Enable SPI",
        raspi_interface="spi",
        raspi_state="enable",
        risk=ConflictSeverity.LOW,
    )]


# ── fix registry ──────────────────────────────────────────────────────────────

# Maps hardware_rules rule name / diagnostic component → fix generator
FixGenerator = Callable[[HardwareInfo, PanelDefinition | None], list[MigrationStep]]

FIX_REGISTRY: dict[str, FixGenerator] = {
    "no_dsi_overlay":            fix_dsi_not_enabled,
    "dsi_overlay_no_drm_connector": fix_dsi_not_enabled,
    "dsi_connector_not_connected":  fix_dsi_not_enabled,
    "dsi_connected_no_backlight":   fix_dsi_not_enabled,
    "i2c": fix_enable_i2c,
    "spi": fix_enable_spi,
}


def generate_fix_plan(
    hw: HardwareInfo,
    component: str,
    panel: PanelDefinition | None = None,
) -> list[MigrationStep]:
    """From a component name or rule name, return fix steps."""
    # Direct rule name match first
    if component in FIX_REGISTRY:
        return FIX_REGISTRY[component](hw, panel)

    # Fall back: find diagnostics for this component and use their rule_name
    for diag in hw.diagnostics:
        if diag.component == component:
            # Try to find a matching rule by message keywords
            for key in FIX_REGISTRY:
                if key in diag.message.lower().replace(" ", "_"):
                    return FIX_REGISTRY[key](hw, panel)
            # The DSI-related diagnostics all resolve to dsi_not_enabled
            if component in ("dsi", "overlay", "backlight"):
                return fix_dsi_not_enabled(hw, panel)

    return []

"""Kiosk-specific library steps.

These templates pair with the handlers added in ``redeploy.apply.handlers``
(``run_ensure_kanshi_profile``, ``run_ensure_autostart_entry``,
``run_ensure_browser_kiosk_script``).
"""
from __future__ import annotations

from ..models import ConflictSeverity, MigrationStep, StepAction


KANSHI_DSI_ONLY = MigrationStep(
    id="kanshi_dsi_only",
    action=StepAction.ENSURE_KANSHI_PROFILE,
    description="Ensure kanshi profile 'dsi-only' disables HDMI outputs",
    profile_name="dsi-only",
    compositor="labwc",
    outputs_on=["DSI-1"],
    outputs_off=["HDMI-A-1", "HDMI-A-2"],
    risk=ConflictSeverity.LOW,
)

AUTOSTART_KIOSK = MigrationStep(
    id="autostart_kiosk",
    action=StepAction.ENSURE_AUTOSTART_ENTRY,
    description="Ensure labwc autostart launches kanshi then browser kiosk",
    compositor="labwc",
    entries=[
        "kanshi &",
        "sleep 2",
        "~/kiosk-launch.sh",
    ],
    risk=ConflictSeverity.LOW,
)

BROWSER_KIOSK_SCRIPT = MigrationStep(
    id="browser_kiosk_script",
    action=StepAction.ENSURE_BROWSER_KIOSK_SCRIPT,
    description="Ensure ~/kiosk-launch.sh with Chromium Wayland kiosk flags",
    kiosk_script_path="~/kiosk-launch.sh",
    browser_profile="chromium-wayland-kiosk",
    risk=ConflictSeverity.LOW,
)

ALL: list[MigrationStep] = [
    KANSHI_DSI_ONLY,
    AUTOSTART_KIOSK,
    BROWSER_KIOSK_SCRIPT,
]

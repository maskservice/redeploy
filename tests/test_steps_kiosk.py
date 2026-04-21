"""Tests for redeploy.steps.kiosk — kiosk-specific library step templates."""
from __future__ import annotations

import pytest

from redeploy.models import MigrationStep, StepAction
from redeploy.steps import StepLibrary
from redeploy.steps.kiosk import (
    AUTOSTART_KIOSK,
    BROWSER_KIOSK_SCRIPT,
    KANSHI_DSI_ONLY,
)


class TestKioskStepsExistInLibrary:
    def test_kanshi_dsi_only_in_library(self):
        assert "kanshi_dsi_only" in StepLibrary.list()
        step = StepLibrary.get("kanshi_dsi_only")
        assert step is not None
        assert step.action == StepAction.ENSURE_KANSHI_PROFILE

    def test_autostart_kiosk_in_library(self):
        assert "autostart_kiosk" in StepLibrary.list()
        step = StepLibrary.get("autostart_kiosk")
        assert step is not None
        assert step.action == StepAction.ENSURE_AUTOSTART_ENTRY

    def test_browser_kiosk_script_in_library(self):
        assert "browser_kiosk_script" in StepLibrary.list()
        step = StepLibrary.get("browser_kiosk_script")
        assert step is not None
        assert step.action == StepAction.ENSURE_BROWSER_KIOSK_SCRIPT


class TestKanshiDsiOnly:
    def test_profile_name(self):
        assert KANSHI_DSI_ONLY.profile_name == "dsi-only"

    def test_outputs_on_are_strings(self):
        assert KANSHI_DSI_ONLY.outputs_on == ["DSI-1"]

    def test_outputs_off_are_strings(self):
        assert KANSHI_DSI_ONLY.outputs_off == ["HDMI-A-1", "HDMI-A-2"]

    def test_compositor_set(self):
        assert KANSHI_DSI_ONLY.compositor == "labwc"

    def test_risk_low(self):
        assert KANSHI_DSI_ONLY.risk.name == "LOW"

    def test_step_library_get_returns_copy(self):
        s1 = StepLibrary.get("kanshi_dsi_only")
        s2 = StepLibrary.get("kanshi_dsi_only")
        assert s1 is not s2
        s1.outputs_on.append("EXTRA")
        assert "EXTRA" not in s2.outputs_on

    def test_override_outputs_on(self):
        step = StepLibrary.get("kanshi_dsi_only", outputs_on=["DSI-2"])
        assert step.outputs_on == ["DSI-2"]


class TestAutostartKiosk:
    def test_entries_are_strings(self):
        assert AUTOSTART_KIOSK.entries == [
            "kanshi &",
            "sleep 2",
            "~/kiosk-launch.sh",
        ]

    def test_compositor_set(self):
        assert AUTOSTART_KIOSK.compositor == "labwc"

    def test_risk_low(self):
        assert AUTOSTART_KIOSK.risk.name == "LOW"


class TestBrowserKioskScript:
    def test_kiosk_script_path(self):
        assert BROWSER_KIOSK_SCRIPT.kiosk_script_path == "~/kiosk-launch.sh"

    def test_browser_profile(self):
        assert BROWSER_KIOSK_SCRIPT.browser_profile == "chromium-wayland-kiosk"

    def test_risk_low(self):
        assert BROWSER_KIOSK_SCRIPT.risk.name == "LOW"


class TestKioskStepsAllUnique:
    def test_no_duplicate_ids(self):
        from redeploy.steps.kiosk import ALL
        ids = [s.id for s in ALL]
        assert len(ids) == len(set(ids))

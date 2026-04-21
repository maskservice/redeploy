"""Browser kiosk profiles for Wayland kiosk deployments.

Encodes browser flag knowledge from pi109 debugging session.

Pi109 critical lessons:
- GNOME Keyring intercepts first Chromium launch without --password-store=basic
  causing a blocking dialog that freezes the kiosk silently on RPi OS.
- --windowed is incompatible with --kiosk under labwc; it must be removed.
- --noerrdialogs prevents crash dialogs on recoverable GPU errors.
- --disable-infobars removes the "Chrome is being controlled" banner.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BrowserKioskProfile:
    """Static definition of a browser kiosk launch profile."""

    id: str
    """Short identifier, e.g. 'chromium-wayland'."""

    binary: str
    """Binary name as found in PATH, e.g. 'chromium-browser'."""

    required_flags: list[str] = field(default_factory=list)
    """Flags that MUST be present for a functional kiosk session."""

    incompatible_flags: list[str] = field(default_factory=list)
    """Flags that break kiosk mode; raise if detected in a spec."""

    optional_flags: list[str] = field(default_factory=list)
    """Recommended but not strictly required."""

    notes: list[str] = field(default_factory=list)
    """Human-readable caveats from real debugging."""

    def build_launch_cmd(self, url: str, extra_flags: list[str] | None = None) -> str:
        """Build the Chromium launch command string for a kiosk-launch.sh."""
        flags = list(self.required_flags)
        flags += extra_flags or []
        bad = [f for f in flags if f in self.incompatible_flags]
        if bad:
            raise ValueError(
                f"Incompatible flags detected for {self.id!r}: {bad}\n"
                f"Remove them: {self.incompatible_flags}"
            )
        return f"{self.binary} {' '.join(flags)} {url}"


CHROMIUM_WAYLAND_KIOSK = BrowserKioskProfile(
    id="chromium-wayland",
    binary="chromium-browser",
    required_flags=[
        "--kiosk",
        "--password-store=basic",        # Pi109: GNOME Keyring blocks without this
        "--noerrdialogs",
        "--disable-infobars",
        "--disable-session-crashed-bubble",
        "--disable-features=TranslateUI",
        "--ozone-platform=wayland",      # explicit; prevents X11 fallback
        "--enable-features=UseOzonePlatform",
    ],
    incompatible_flags=[
        "--windowed",           # Pi109: conflicts with --kiosk under labwc
        "--start-maximized",    # overrides kiosk geometry
    ],
    optional_flags=[
        "--check-for-update-interval=1",  # disable auto-update check noise
        "--incognito",                    # stateless sessions
    ],
    notes=[
        "Pi109: --password-store=basic is MANDATORY on RPi OS with GNOME Keyring",
        "--windowed + --kiosk causes transparent/non-fullscreen window under labwc",
        "Set DISPLAY unset; XDG_SESSION_TYPE=wayland must be exported before launch",
    ],
)

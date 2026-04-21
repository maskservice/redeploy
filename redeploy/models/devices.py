"""Device registry and device-map models."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, PrivateAttr

from .hardware import HardwareInfo
from .infra import InfraState
from .persisted import PersistedModel


_DEFAULT_DEVICE_MAP_DIR = Path.home() / ".config" / "redeploy" / "device-maps"


class DeployRecord(BaseModel):
    """Single deployment event recorded for a device."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    spec_name: str = ""
    from_strategy: str = ""
    to_strategy: str = ""
    version: str = ""
    ok: bool = True
    steps_total: int = 0
    steps_ok: int = 0
    note: str = ""


class KnownDevice(BaseModel):
    """Device known to redeploy — persisted in ~/.config/redeploy/devices.yaml."""
    id: str
    host: str = ""
    name: str = ""
    tags: list[str] = Field(default_factory=list)
    strategy: str = "docker_full"
    app: str = ""
    domain: str = ""
    remote_dir: str = ""
    ssh_port: int = 22
    ssh_key: Optional[str] = None

    ip: str = ""
    mac: str = ""
    hostname: str = ""
    ssh_user: str = ""
    last_seen: Optional[datetime] = None
    last_ssh_ok: Optional[datetime] = None
    source: str = "manual"

    hardware: Optional[HardwareInfo] = None
    deploys: list[DeployRecord] = Field(default_factory=list)

    @property
    def last_deploy(self) -> Optional[DeployRecord]:
        return self.deploys[-1] if self.deploys else None

    @property
    def is_reachable(self) -> bool:
        if self.last_seen is None:
            return False
        return (datetime.now(timezone.utc) - self.last_seen).total_seconds() < 300

    def record_deploy(self, record: DeployRecord) -> None:
        self.deploys.append(record)
        self.deploys = self.deploys[-50:]


class DeviceMap(PersistedModel):
    """Full, persisted snapshot of a device: identity + InfraState + HardwareInfo."""
    id: str
    host: str = ""
    name: str = ""
    tags: list[str] = Field(default_factory=list)
    scanned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    hardware: Optional[HardwareInfo] = None
    infra: Optional[InfraState] = None
    issues: list[dict] = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(i.get("severity") in ("error", "critical") for i in self.issues)

    @property
    def display_summary(self) -> str:
        if not self.hardware:
            return "no hardware data"
        hw = self.hardware
        dsi = next((o for o in hw.drm_outputs if "DSI" in o.name), None)
        if dsi:
            mode = dsi.modes[0] if dsi.modes else "?"
            bl = hw.backlights[0].brightness if hw.backlights else "?"
            return f"DSI {dsi.connector} {dsi.status} {mode} backlight={bl}"
        return "no DSI"

    def save(self, path: Optional[Path] = None) -> Path:
        p = path or _DEFAULT_DEVICE_MAP_DIR / f"{self.id.replace('/', '_').replace('@', '_at_')}.yaml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_yaml())
        return p

    @classmethod
    def load_for(cls, device_id: str) -> Optional[DeviceMap]:
        p = _DEFAULT_DEVICE_MAP_DIR / f"{device_id.replace('/', '_').replace('@', '_at_')}.yaml"
        if p.exists():
            return cls.load(p)
        return None

    @classmethod
    def list_saved(cls) -> list[Path]:
        if not _DEFAULT_DEVICE_MAP_DIR.exists():
            return []
        return sorted(_DEFAULT_DEVICE_MAP_DIR.glob("*.yaml"))


class DeviceRegistry(BaseModel):
    """Persistent device registry — stored at ~/.config/redeploy/devices.yaml."""
    devices: list[KnownDevice] = Field(default_factory=list)
    _path: Optional[Path] = PrivateAttr(default=None)

    def get(self, device_id: str) -> Optional[KnownDevice]:
        return next((d for d in self.devices if d.id == device_id), None)

    def upsert(self, device: KnownDevice) -> None:
        for i, d in enumerate(self.devices):
            if d.id == device.id:
                self.devices[i] = device
                return
        self.devices.append(device)

    def remove(self, device_id: str) -> bool:
        before = len(self.devices)
        self.devices = [d for d in self.devices if d.id != device_id]
        return len(self.devices) < before

    def by_tag(self, tag: str) -> list[KnownDevice]:
        return [d for d in self.devices if tag in d.tags]

    def by_strategy(self, strategy: str) -> list[KnownDevice]:
        return [d for d in self.devices if d.strategy == strategy]

    def reachable(self) -> list[KnownDevice]:
        return [d for d in self.devices if d.is_reachable]

    @classmethod
    def default_path(cls) -> Path:
        return Path.home() / ".config" / "redeploy" / "devices.yaml"

    @classmethod
    def load(cls, path: Optional[Path] = None) -> DeviceRegistry:
        p = path or cls.default_path()
        if not p.exists():
            return cls()
        raw = yaml.safe_load(p.read_text()) or {}
        devices = [KnownDevice(**d) for d in raw.get("devices", [])]
        reg = cls(devices=devices)
        reg._path = p
        return reg

    def save(self, path: Optional[Path] = None) -> None:
        p = path or self._path or self.default_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {"devices": [d.model_dump(mode="json") for d in self.devices]}
        tmp = p.with_suffix(".tmp")
        tmp.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False))
        tmp.chmod(0o600)
        tmp.replace(p)

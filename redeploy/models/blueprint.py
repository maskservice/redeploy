"""Device blueprint models — portable deployment recipes."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from .hardware import HardwareInfo
from .persisted import PersistedModel


_DEFAULT_BLUEPRINT_DIR = Path.home() / ".config" / "redeploy" / "blueprints"


class ServicePort(BaseModel):
    host: int
    container: int
    protocol: str = "tcp"


class VolumeMount(BaseModel):
    host: str
    container: str
    read_only: bool = False


class ServiceSpec(BaseModel):
    name: str
    image: str
    platform: str = ""
    ports: list[ServicePort] = Field(default_factory=list)
    volumes: list[VolumeMount] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    command: Optional[str] = None
    healthcheck: Optional[str] = None
    depends_on: list[str] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)
    restart: str = "unless-stopped"
    network_mode: Optional[str] = None
    privileged: bool = False
    source_ref: Optional[str] = None


class HardwareRequirements(BaseModel):
    arch: str = "linux/arm64"
    min_ram_mb: int = 0
    min_disk_gb: int = 0
    display_type: Optional[str] = None
    display_resolution: Optional[str] = None
    i2c_required: bool = False
    gpio_required: bool = False
    features: list[str] = Field(default_factory=list)


class BlueprintSource(BaseModel):
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    migration_file: Optional[str] = None
    markpact_files: list[str] = Field(default_factory=list)
    compose_files: list[str] = Field(default_factory=list)
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DeviceBlueprint(PersistedModel):
    """Self-contained, portable deployment recipe."""
    name: str
    version: str = "0.0.0"
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    services: list[ServiceSpec] = Field(default_factory=list)
    hardware: HardwareRequirements = Field(default_factory=HardwareRequirements)
    app_url: Optional[str] = None
    deploy_strategy: str = "podman_quadlet"
    env_file: Optional[str] = None
    notes: str = ""
    source: BlueprintSource = Field(default_factory=BlueprintSource)

    def service(self, name: str) -> Optional[ServiceSpec]:
        return next((s for s in self.services if s.name == name), None)

    def save(self, path: Optional[Path] = None) -> Path:
        p = path or _DEFAULT_BLUEPRINT_DIR / f"{self.name}.blueprint.yaml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_yaml())
        return p

    @classmethod
    def list_saved(cls) -> list[Path]:
        if not _DEFAULT_BLUEPRINT_DIR.exists():
            return []
        return sorted(_DEFAULT_BLUEPRINT_DIR.glob("*.blueprint.yaml"))

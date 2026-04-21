"""Spec models — MigrationSpec, InfraSpec, TargetConfig.

Also contains the legacy ``post_deploy`` / ``pre_deploy`` migration shim.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, field_validator

from .enums import DeployStrategy, StepAction, _STRATEGY_ALIASES
from .infra import InfraState, RuntimeInfo
from .pipeline import Hook


class TargetConfig(BaseModel):
    """Desired infrastructure state — input to `plan`."""
    strategy: DeployStrategy = DeployStrategy.DOCKER_FULL
    host: Optional[str] = None
    app: str = ""
    version: Optional[str] = None

    compose_files: list[str] = Field(default_factory=list)
    env_file: Optional[str] = None
    remote_dir: str = ""
    domain: Optional[str] = None

    @field_validator("strategy", mode="before")
    @classmethod
    def _accept_strategy_aliases(cls, v: object) -> object:
        if isinstance(v, str):
            return _STRATEGY_ALIASES.get(v, v)
        return v

    stop_services: list[str] = Field(default_factory=list)
    disable_services: list[str] = Field(default_factory=list)
    delete_k3s_namespaces: list[str] = Field(default_factory=list)

    verify_url: Optional[str] = None
    verify_version: Optional[str] = None

    pattern: Optional[str] = None
    pattern_config: dict[str, Any] = Field(default_factory=dict)

    hooks: list[Hook] = Field(default_factory=list)


class InfraSpec(BaseModel):
    """Declarative description of one infrastructure state (from OR to)."""
    strategy: DeployStrategy = DeployStrategy.UNKNOWN
    host: str = "local"
    app: str = "c2004"
    version: Optional[str] = None
    domain: Optional[str] = None
    remote_dir: str = "~/c2004"

    compose_files: list[str] = Field(default_factory=list)
    env_file: Optional[str] = None

    stop_services: list[str] = Field(default_factory=list)
    disable_services: list[str] = Field(default_factory=list)
    delete_k3s_namespaces: list[str] = Field(default_factory=list)

    verify_url: Optional[str] = None
    verify_version: Optional[str] = None


def _migrate_legacy_post_deploy(raw: dict) -> dict:
    """Convert legacy ``post_deploy`` / ``pre_deploy`` blocks into generic ``hooks``."""
    if not isinstance(raw, dict):
        return raw

    hooks = list(raw.get("hooks") or [])

    def _consume(container: dict, phase: str) -> None:
        legacy = container.pop("post_deploy", None) if phase == "after_apply" else container.pop("pre_deploy", None)
        if not isinstance(legacy, dict):
            return
        url = legacy.get("browser_url") or legacy.get("url") or ""
        if legacy.get("refresh_cache"):
            hooks.append({
                "id": f"{phase}_refresh_cache",
                "phase": phase,
                "action": "local_cmd",
                "description": "refresh cache (legacy post_deploy.refresh_cache)",
                "command": f"curl -fsS -X POST {url}/api/v3/cache/clear || true",
                "on_failure": "warn",
            })
        if legacy.get("open_browser") and url:
            hooks.append({
                "id": f"{phase}_open_browser",
                "phase": phase,
                "action": "open_url",
                "description": "open browser tab (legacy post_deploy.open_browser)",
                "url": url,
                "on_failure": "warn",
            })
        if legacy.get("command"):
            hooks.append({
                "id": f"{phase}_cmd",
                "phase": phase,
                "action": "local_cmd",
                "command": legacy["command"],
                "on_failure": "warn",
            })

    _consume(raw, "after_apply")
    _consume(raw, "before_apply")
    target = raw.get("target")
    if isinstance(target, dict):
        _consume(target, "after_apply")
        _consume(target, "before_apply")

    if hooks:
        raw["hooks"] = hooks
    return raw


class MigrationSpec(BaseModel):
    """Single YAML file describing full migration: from-state → to-state."""
    name: str = "migration"
    description: str = ""

    source: InfraSpec
    target: InfraSpec

    extra_steps: list[dict] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    hooks: list[Hook] = Field(default_factory=list)

    @classmethod
    def from_file(cls, path: Path) -> MigrationSpec:
        with Path(path).open() as f:
            raw = yaml.safe_load(f) or {}
        raw = _migrate_legacy_post_deploy(raw)
        return cls(**raw)

    def resolve_versions(self, manifest_version: Optional[str] = None) -> None:
        if manifest_version:
            if self.source.version == "@manifest":
                self.source.version = manifest_version
            if self.target.version == "@manifest":
                self.target.version = manifest_version
            if self.target.verify_version == "@manifest":
                self.target.verify_version = manifest_version

    def to_infra_state(self) -> InfraState:
        """Build a minimal InfraState from source spec (used when detect is skipped)."""
        rt = RuntimeInfo()
        if self.source.strategy == DeployStrategy.K3S:
            rt.k3s = "declared-in-spec"
            rt.k3s_namespaces = self.source.delete_k3s_namespaces or [self.source.app]
        if self.source.strategy == DeployStrategy.DOCKER_FULL:
            rt.docker = "declared-in-spec"
        return InfraState(
            host=self.source.host,
            app=self.source.app,
            runtime=rt,
            detected_strategy=self.source.strategy.value,
            current_version=self.source.version,
        )

    def to_target_config(self) -> TargetConfig:
        """Convert target InfraSpec to TargetConfig for Planner."""
        return TargetConfig(
            strategy=self.target.strategy,
            app=self.target.app,
            version=self.target.version,
            compose_files=self.target.compose_files,
            env_file=self.target.env_file,
            remote_dir=self.target.remote_dir,
            domain=self.target.domain,
            stop_services=self.source.stop_services,
            disable_services=self.source.disable_services,
            delete_k3s_namespaces=self.source.delete_k3s_namespaces,
            verify_url=self.target.verify_url,
            verify_version=self.target.verify_version or self.target.version,
            hooks=list(self.hooks),
        )

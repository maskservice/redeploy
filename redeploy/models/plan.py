"""Plan models — MigrationPlan, MigrationStep."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from .enums import ConflictSeverity, DeployStrategy, StepAction, StepStatus
from .pipeline import Hook


class MigrationStep(BaseModel):
    id: str
    action: StepAction
    description: str
    status: StepStatus = StepStatus.PENDING

    # action-specific params
    service: Optional[str] = None
    command: Optional[str] = None
    command_ref: Optional[str] = None
    compose: Optional[str] = None
    flags: list[str] = Field(default_factory=list)
    url: Optional[str] = None
    expect: Optional[str] = None
    src: Optional[str] = None
    dst: Optional[str] = None
    excludes: list[str] = Field(default_factory=list)
    seconds: int = 0
    namespace: Optional[str] = None

    reason: Optional[str] = None
    risk: ConflictSeverity = ConflictSeverity.LOW
    rollback_command: Optional[str] = None
    timeout: int = 300
    log_lines: int = 20

    # plugin-specific params
    plugin_type: Optional[str] = None
    plugin_params: dict = Field(default_factory=dict)

    # ensure_config_line params
    config_file: Optional[str] = None
    config_line: Optional[str] = None
    config_section: str = "all"
    config_replaces_pattern: Optional[str] = None

    # raspi_config params
    raspi_interface: Optional[str] = None
    raspi_state: Optional[str] = None

    # kiosk / compositor params
    profile_name: Optional[str] = None
    outputs_on: list[str] = Field(default_factory=list)
    outputs_off: list[str] = Field(default_factory=list)
    compositor: Optional[str] = None
    entries: list[str] = Field(default_factory=list)
    kiosk_script_path: Optional[str] = None
    browser_profile: Optional[str] = None

    result: Optional[str] = None
    error: Optional[str] = None


class MigrationPlan(BaseModel):
    """Full migration plan — output of `plan`, input to `apply`."""
    infra_file: str = "infra.yaml"
    target_file: Optional[str] = None
    spec_path: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    host: str
    app: str
    from_strategy: DeployStrategy
    to_strategy: DeployStrategy

    risk: ConflictSeverity = ConflictSeverity.LOW
    estimated_downtime: str = "unknown"
    steps: list[MigrationStep] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    hooks: list[Hook] = Field(default_factory=list)

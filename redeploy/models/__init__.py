"""redeploy.models — shared data models (backward-compat re-export hub).

This package was refactored from the monolithic ``redeploy.models`` module
(R3, 0.2.53).  All public names remain importable from the top-level
package for backward compatibility.
"""
from __future__ import annotations

# ── core ─────────────────────────────────────────────────────────────────────
from .enums import (
    ConflictSeverity,
    DeployStrategy,
    StepAction,
    StepStatus,
    _STRATEGY_ALIASES,
)
from .persisted import PersistedModel

# ── hardware ─────────────────────────────────────────────────────────────────
from .hardware import (
    BacklightInfo,
    DrmOutput,
    HardwareDiagnostic,
    HardwareInfo,
    I2CBusInfo,
)

# ── infra state ─────────────────────────────────────────────────────────────
from .infra import (
    AppHealthInfo,
    ConflictInfo,
    InfraState,
    PortInfo,
    RuntimeInfo,
    ServiceInfo,
)

# ── pipeline ─────────────────────────────────────────────────────────────────
from .pipeline import Hook, PipelinePhase

# ── spec & target ───────────────────────────────────────────────────────────
from .spec import (
    InfraSpec,
    MigrationSpec,
    TargetConfig,
    _migrate_legacy_post_deploy,
)

# ── plan ─────────────────────────────────────────────────────────────────────
from .plan import MigrationPlan, MigrationStep

# ── manifest ─────────────────────────────────────────────────────────────────
from .manifest import EnvironmentConfig, ProjectManifest

# ── blueprint ────────────────────────────────────────────────────────────────
from .blueprint import (
    BlueprintSource,
    DeviceBlueprint,
    HardwareRequirements,
    ServicePort,
    ServiceSpec,
    VolumeMount,
)

# ── device registry / map ───────────────────────────────────────────────────
from .devices import (
    DeployRecord,
    DeviceMap,
    DeviceRegistry,
    KnownDevice,
)

__all__ = [
    # enums
    "ConflictSeverity",
    "DeployStrategy",
    "StepAction",
    "StepStatus",
    "_STRATEGY_ALIASES",
    # persisted
    "PersistedModel",
    # hardware
    "BacklightInfo",
    "DrmOutput",
    "HardwareDiagnostic",
    "HardwareInfo",
    "I2CBusInfo",
    # infra
    "AppHealthInfo",
    "ConflictInfo",
    "InfraState",
    "PortInfo",
    "RuntimeInfo",
    "ServiceInfo",
    # pipeline
    "Hook",
    "PipelinePhase",
    # spec
    "InfraSpec",
    "MigrationSpec",
    "TargetConfig",
    "_migrate_legacy_post_deploy",
    # plan
    "MigrationPlan",
    "MigrationStep",
    # manifest
    "EnvironmentConfig",
    "ProjectManifest",
    # blueprint
    "BlueprintSource",
    "DeviceBlueprint",
    "HardwareRequirements",
    "ServicePort",
    "ServiceSpec",
    "VolumeMount",
    # devices
    "DeployRecord",
    "DeviceMap",
    "DeviceRegistry",
    "KnownDevice",
]

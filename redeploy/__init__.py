"""redeploy — Infrastructure migration toolkit: detect → plan → apply.

Public API (stable from 0.2.0, semver guaranteed)::

    from redeploy import MigrationSpec, Planner, Executor
    from redeploy import InfraState, TargetConfig, DeployStrategy

Everything not listed in ``__all__`` is internal and may change without notice.
"""
__version__ = "0.2.5"

# ── Core models ───────────────────────────────────────────────────────────────
from .models import (  # noqa: F401
    ConflictSeverity,
    DeployStrategy,
    InfraSpec,
    InfraState,
    MigrationPlan,
    MigrationSpec,
    MigrationStep,
    StepAction,
    StepStatus,
    TargetConfig,
)

# ── Pipeline ──────────────────────────────────────────────────────────────────
from .detect import Detector          # noqa: F401
from .plan import Planner             # noqa: F401
from .apply import Executor           # noqa: F401

# ── SSH primitives ────────────────────────────────────────────────────────────
from .ssh import SshClient, SshResult  # noqa: F401

# ── Fleet / registry (first-class from 0.2.0) ────────────────────────────────
from .models import DeviceRegistry, KnownDevice  # noqa: F401
from .fleet import (  # noqa: F401
    DeviceArch,
    DeviceExpectation,
    Fleet,
    FleetConfig,
    FleetDevice,
    Stage,
    STAGE_DEFAULT_EXPECTATIONS,
)
from .steps import StepLibrary  # noqa: F401

# ── Deploy patterns (first-class from 0.2.0) ──────────────────────────────────
from .patterns import (  # noqa: F401
    DeployPattern,
    BlueGreenPattern,
    CanaryPattern,
    RollbackOnFailurePattern,
    get_pattern,
    list_patterns,
    pattern_registry,
)

# ── Observability (first-class from 0.2.0) ────────────────────────────────────
from .observe import (  # noqa: F401
    AuditEntry,
    DeployAuditLog,
    DeployReport,
)

# ── IaC parsers (first-class from 0.3.0) ──────────────────────────────────────
from .iac import (  # noqa: F401
    ParsedSpec,
    Parser,
    ParserRegistry,
    PortInfo,
    ServiceInfo,
    VolumeInfo,
    ConversionWarning,
    parse_file,
    parse_dir,
    parser_registry,
)

# ── Plugin system (first-class from 0.2.2) ────────────────────────────────────
from .plugins import (  # noqa: F401
    PluginContext,
    PluginRegistry,
    register_plugin,
    load_user_plugins,
    registry as plugin_registry,
)

__all__ = [
    # version
    "__version__",
    # models
    "ConflictSeverity",
    "DeployStrategy",
    "InfraSpec",
    "InfraState",
    "MigrationPlan",
    "MigrationSpec",
    "MigrationStep",
    "StepAction",
    "StepStatus",
    "TargetConfig",
    # pipeline
    "Detector",
    "Planner",
    "Executor",
    # SSH
    "SshClient",
    "SshResult",
    # fleet / registry
    "DeviceRegistry",
    "KnownDevice",
    "Fleet",
    "DeviceArch",
    "DeviceExpectation",
    "FleetConfig",
    "FleetDevice",
    "Stage",
    "STAGE_DEFAULT_EXPECTATIONS",
    "StepLibrary",
    # patterns
    "DeployPattern",
    "BlueGreenPattern",
    "CanaryPattern",
    "RollbackOnFailurePattern",
    "get_pattern",
    "list_patterns",
    "pattern_registry",
    # observability
    "AuditEntry",
    "DeployAuditLog",
    "DeployReport",
    # iac parsers
    "ParsedSpec",
    "Parser",
    "ParserRegistry",
    "PortInfo",
    "ServiceInfo",
    "VolumeInfo",
    "ConversionWarning",
    "parse_file",
    "parse_dir",
    "parser_registry",
    # plugin system
    "PluginContext",
    "PluginRegistry",
    "register_plugin",
    "load_user_plugins",
    "plugin_registry",
]

<!-- code2docs:start --># redeploy

![version](https://img.shields.io/badge/version-0.1.0-blue) ![python](https://img.shields.io/badge/python-%3E%3D3.11-blue) ![coverage](https://img.shields.io/badge/coverage-unknown-lightgrey) ![functions](https://img.shields.io/badge/functions-2592-green)
> **2592** functions | **258** classes | **309** files | CC̄ = 5.0

> Auto-generated project documentation from source code analysis.

**Author:** Tom Softreck <tom@sapletta.com>  
**License:** Not specified  
**Repository:** [https://github.com/maskservice/redeploy](https://github.com/maskservice/redeploy)

## Installation

### From PyPI

```bash
pip install redeploy
```

### From Source

```bash
git clone https://github.com/maskservice/redeploy
cd redeploy
pip install -e .
```

### Optional Extras

```bash
pip install redeploy[dev]    # development tools
pip install redeploy[op3]    # op3 features
pip install redeploy[mcp]    # mcp features
```

## Quick Start

### CLI Usage

```bash
# Generate full documentation for your project
redeploy ./my-project

# Only regenerate README
redeploy ./my-project --readme-only

# Preview what would be generated (no file writes)
redeploy ./my-project --dry-run

# Check documentation health
redeploy check ./my-project

# Sync — regenerate only changed modules
redeploy sync ./my-project
```

### Python API

```python
from redeploy import generate_readme, generate_docs, Code2DocsConfig

# Quick: generate README
generate_readme("./my-project")

# Full: generate all documentation
config = Code2DocsConfig(project_name="mylib", verbose=True)
docs = generate_docs("./my-project", config=config)
```




## Architecture

```
redeploy/
├── SUMR
├── goal
├── REFACTORING
├── Makefile
├── SUMD
├── REPAIR_LOG
├── DOQL-INTEGRATION
├── pyqual
├── sumd
├── pyproject
├── tree
├── TODO
├── CHANGELOG
├── project
├── README
    ├── patterns
    ├── markpact-implementation-plan
    ├── fleet
    ├── dsl-migration
    ├── observe
    ├── README
    ├── markpact-audit
        ├── README
    ├── context
    ├── README
        ├── toon
    ├── version/
    ├── schema
    ├── observe
    ├── cli/
    ├── data_sync
    ├── heal
├── redeploy/
    ├── parse
    ├── fleet
    ├── models
    ├── verify
    ├── spec_loader
    ├── ssh
    ├── patterns
    ├── discovery
    ├── audit
    ├── mcp_server
        ├── process_control_template
        ├── detector
    ├── detect/
        ├── remote
        ├── hardware
        ├── hardware_rules
        ├── templates
        ├── workflow
        ├── probes
        ├── builtin/
            ├── templates
        ├── builtins
        ├── kiosk
    ├── steps/
        ├── applier
        ├── loader
    ├── config_apply/
        ├── display
        ├── query
        ├── core
            ├── target
            ├── devices
            ├── state
            ├── inspect
            ├── device_map_renderers
            ├── bump_fix
            ├── exec_
            ├── blueprint
            ├── export
            ├── init
            ├── status
            ├── probe
            ├── mcp_cmd
            ├── plugin
            ├── import_
            ├── plan_apply
        ├── commands/
            ├── detect
            ├── device_map
            ├── hardware
            ├── prompt_cmd
            ├── diff
            ├── workflow
            ├── push
            ├── patterns
            ├── diagnose
            ├── audit
                ├── monorepo
                ├── commands
                ├── helpers
            ├── version/
                ├── release
                ├── scanner
    ├── plugins/
            ├── notify
        ├── builtin/
            ├── process_control
            ├── browser_reload
            ├── systemd_reload
            ├── hardware_diagnostic
        ├── steps
        ├── exceptions
        ├── runner
    ├── dsl_python/
        ├── docker_steps
        ├── context
        ├── decorators
        ├── panels
        ├── config_txt
    ├── hardware/
        ├── fixes
        ├── raspi_config
        ├── kiosk/
            ├── browsers
            ├── autostart
            ├── output_profiles
            ├── compositors
        ├── data/
            ├── waveshare
            ├── official
            ├── hyperpixel
    ├── markpact/
        ├── parser
        ├── models
        ├── compiler
        ├── progress
        ├── exceptions
        ├── state
    ├── apply/
        ├── state_apply
        ├── handlers
        ├── executor
        ├── rollback
        ├── utils/
        ├── bump
        ├── git_transaction
        ├── transaction
        ├── changelog
        ├── manifest
        ├── git_integration
        ├── diff
        ├── commits
            ├── base
            ├── toml_
            ├── regex
            ├── yaml_
        ├── sources/
            ├── plain
            ├── json_
    ├── plan/
        ├── planner
    ├── blueprint/
        ├── extractor
        ├── sources/
            ├── hardware
            ├── compose
            ├── infra
            ├── migration
            ├── docker_compose
        ├── generators/
            ├── migration
    ├── integrations/
        ├── op3_bridge
        ├── loader
    ├── dsl/
        ├── parser
        ├── docker_compose
        ├── base
        ├── registry
    ├── iac/
        ├── config_hints
        ├── parsers/
            ├── compose
    ├── README
        ├── rpi5-waveshare-kiosk
        ├── enable-i2c-spi
        ├── waveshare-8-inch-dsi
        ├── official-dsi-7-inch
        ├── README
            ├── migration
            ├── README
            ├── migration
            ├── migration
            ├── README
            ├── migration
            ├── migration
            ├── migration
            ├── README
            ├── migration
        ├── 16-auto-rollback
        ├── 14-blue-green
        ├── 15-canary
        ├── 13-kiosk-appliance
            ├── redeploy
            ├── migration
            ├── README
            ├── redeploy
            ├── migration
            ├── README
            ├── migration
            ├── README
            ├── redeploy
            ├── fleet
            ├── README
            ├── migration
            ├── README
                    ├── tls
            ├── dev
            ├── staging
            ├── redeploy
            ├── prod
            ├── README
            ├── migration
            ├── README
            ├── redeploy
            ├── migration
            ├── README
            ├── redeploy
            ├── migration
            ├── README
            ├── migration-rpi5
            ├── redeploy
            ├── migration
            ├── README
            ├── migration
            ├── README
            ├── migration
            ├── README
            ├── redeploy
            ├── fleet
            ├── migration
            ├── README
        ├── version
            ├── test-local-63f620b6
            ├── test-local-68ae2b20
            ├── test-local-be94eb0c
            ├── migration-local-e4114daa
            ├── test-local-6bb4cec7
            ├── test-local-c05a99a2
            ├── test-local-ec3c5638
            ├── test-local-eac354f9
            ├── migration-local-92efc860
            ├── test-local-ed7da478
            ├── test-local-46c5e2ce
            ├── test-local-abe8802f
            ├── test-local-831fd1ab
            ├── test-local-e1009318
            ├── test-local-563ceb24
            ├── test-local-036bc2a0
            ├── test-local-35782b9c
            ├── test-local-4d4cf12b
            ├── test-local-f868d117
            ├── test-local-09b68243
            ├── test-local-ab92e6d9
            ├── test-local-ee51c059
            ├── test-local-c1ec6b35
            ├── test-local-ea908429
            ├── test-local-7f5ddd97
            ├── test-local-179edfed
            ├── test-local-e3a0f31a
            ├── test-local-6279ef2c
            ├── test-local-24cd498c
            ├── test-local-efd3d620
            ├── test-local-e322f022
            ├── test-local-3ad44506
            ├── test-local-9cc88960
            ├── test-local-50622a24
            ├── test-local-df0d6ff6
            ├── test-local-c9849e24
            ├── test-local-56cb0635
            ├── test-local-d3c0fad8
            ├── test-local-891787e9
            ├── test-local-0a0a5446
            ├── test-local-9c9d5826
            ├── test-local-da199855
            ├── test-local-db469906
            ├── test-local-a70e54ce
            ├── test-local-ad30ec23
            ├── test-local-a929f336
            ├── test-local-5a1d7483
            ├── test-local-e069dd9f
            ├── test-local-36935faf
    ├── quality_gate
    ├── hardware-108
    ├── hardware-109
        ├── toon
    ├── prompt
        ├── toon
        ├── context
        ├── README
            ├── toon
        ├── toon
    ├── README
        ├── toon
        ├── toon
    ├── context
        ├── toon
    ├── calls
        ├── toon
```

## API Overview

### Classes

- **`ConflictSeverity`** — —
- **`StepAction`** — —
- **`StepStatus`** — —
- **`DeployStrategy`** — —
- **`PersistedModel`** — —
- **`ServiceInfo`** — —
- **`PortInfo`** — —
- **`ConflictInfo`** — —
- **`RuntimeInfo`** — —
- **`AppHealthInfo`** — —
- **`DrmOutput`** — —
- **`BacklightInfo`** — —
- **`I2CBusInfo`** — —
- **`HardwareDiagnostic`** — —
- **`HardwareInfo`** — —
- **`InfraState`** — —
- **`TargetConfig`** — —
- **`MigrationStep`** — —
- **`InfraSpec`** — —
- **`MigrationSpec`** — —
- **`MigrationPlan`** — —
- **`EnvironmentConfig`** — —
- **`ProjectManifest`** — —
- **`DeployRecord`** — —
- **`KnownDevice`** — —
- **`DeviceMap`** — —
- **`ServicePort`** — —
- **`VolumeMount`** — —
- **`ServiceSpec`** — —
- **`HardwareRequirements`** — —
- **`BlueprintSource`** — —
- **`DeviceBlueprint`** — —
- **`DeviceRegistry`** — —
- **`AuditCheck`** — —
- **`AuditReport`** — —
- **`Auditor`** — —
- **`AuditEntry`** — —
- **`DeployAuditLog`** — —
- **`DeployReport`** — —
- **`DeviceArch`** — —
- **`Stage`** — —
- **`DeviceExpectation`** — —
- **`FleetDevice`** — —
- **`FleetConfig`** — —
- **`Fleet`** — —
- **`DiscoveredHost`** — —
- **`ProbeResult`** — —
- **`Stage`** — —
- **`Device`** — —
- **`Fleet`** — —
- **`BlueGreenPattern`** — —
- **`CanaryPattern`** — —
- **`RollbackOnFailurePattern`** — —
- **`ConflictSeverity`** — —
- **`StepAction`** — —
- **`StepStatus`** — —
- **`DeployStrategy`** — —
- **`PersistedModel`** — —
- **`ServiceInfo`** — —
- **`PortInfo`** — —
- **`ConflictInfo`** — —
- **`RuntimeInfo`** — —
- **`AppHealthInfo`** — —
- **`DrmOutput`** — —
- **`BacklightInfo`** — —
- **`I2CBusInfo`** — —
- **`HardwareDiagnostic`** — —
- **`HardwareInfo`** — —
- **`InfraState`** — —
- **`TargetConfig`** — —
- **`MigrationStep`** — —
- **`InfraSpec`** — —
- **`MigrationSpec`** — —
- **`MigrationPlan`** — —
- **`EnvironmentConfig`** — —
- **`ProjectManifest`** — —
- **`DeployRecord`** — —
- **`KnownDevice`** — —
- **`DeviceMap`** — —
- **`ServicePort`** — —
- **`VolumeMount`** — —
- **`ServiceSpec`** — —
- **`HardwareRequirements`** — —
- **`BlueprintSource`** — —
- **`DeviceBlueprint`** — —
- **`DeviceRegistry`** — —
- **`AuditCheck`** — —
- **`AuditReport`** — —
- **`Auditor`** — —
- **`AuditEntry`** — —
- **`DeployAuditLog`** — —
- **`DeployReport`** — —
- **`DeviceArch`** — —
- **`Stage`** — —
- **`DeviceExpectation`** — —
- **`FleetDevice`** — —
- **`FleetConfig`** — —
- **`Fleet`** — —
- **`DiscoveredHost`** — —
- **`ProbeResult`** — —
- **`Snapshot`** — —
- **`MyCustomPattern`** — —
- **`MyFormatParser`** — —
- **`AuditEntry`** — Single audit log entry — immutable snapshot of one deployment.
- **`DeployAuditLog`** — Persistent audit log — newline-delimited JSON at ``path``.
- **`DeployReport`** — Human-readable post-deploy report from an AuditEntry.
- **`HealRunner`** — Wraps Executor with self-healing loop.
- **`DeviceArch`** — —
- **`Stage`** — —
- **`DeviceExpectation`** — Declarative assertions about required infrastructure on a device.
- **`FleetDevice`** — Generic device descriptor — superset of ``deploy``'s DeviceConfig.
- **`FleetConfig`** — Top-level fleet manifest — list of devices with stage / tag organisation.
- **`Fleet`** — Unified first-class fleet — wraps FleetConfig and/or DeviceRegistry.
- **`ConflictSeverity`** — —
- **`StepAction`** — —
- **`StepStatus`** — —
- **`DeployStrategy`** — —
- **`PersistedModel`** — Mixin for models that can be persisted to/from YAML files.
- **`ServiceInfo`** — —
- **`PortInfo`** — —
- **`ConflictInfo`** — —
- **`RuntimeInfo`** — —
- **`AppHealthInfo`** — —
- **`DrmOutput`** — One DRM connector (e.g. card1-DSI-2, card2-HDMI-A-1).
- **`BacklightInfo`** — Sysfs backlight device.
- **`I2CBusInfo`** — —
- **`HardwareDiagnostic`** — Problem found during hardware probe.
- **`HardwareInfo`** — Hardware state produced by hardware probe.
- **`InfraState`** — Full detected state of infrastructure — output of `detect`.
- **`TargetConfig`** — Desired infrastructure state — input to `plan`.
- **`MigrationStep`** — —
- **`InfraSpec`** — Declarative description of one infrastructure state (from OR to).
- **`MigrationSpec`** — Single YAML file describing full migration: from-state → to-state.
- **`MigrationPlan`** — Full migration plan — output of `plan`, input to `apply`.
- **`EnvironmentConfig`** — One named environment (prod / dev / rpi5 / staging …) in redeploy.yaml.
- **`ProjectManifest`** — Per-project redeploy.yaml — replaces repetitive Makefile variables.
- **`DeployRecord`** — Single deployment event recorded for a device.
- **`KnownDevice`** — Device known to redeploy — persisted in ~/.config/redeploy/devices.yaml.
- **`DeviceMap`** — Full, persisted snapshot of a device: identity + InfraState + HardwareInfo.
- **`ServicePort`** — A single port mapping for a container service.
- **`VolumeMount`** — —
- **`ServiceSpec`** — Complete specification of a single containerised service.
- **`HardwareRequirements`** — Hardware capabilities required to run the blueprint.
- **`BlueprintSource`** — Where the blueprint was extracted from — audit trail.
- **`DeviceBlueprint`** — Self-contained, portable deployment recipe.
- **`DeviceRegistry`** — Persistent device registry — stored at ~/.config/redeploy/devices.yaml.
- **`VerifyContext`** — Accumulates check results during verification.
- **`SpecLoaderError`** — Base error raised when a deployment spec cannot be loaded.
- **`UnsupportedSpecFormatError`** — Raised when the spec file uses an unsupported format.
- **`SshResult`** — —
- **`SshClient`** — Execute commands on a remote host via SSH (or locally).
- **`RemoteProbe`** — Thin wrapper kept for redeploy.detect compatibility.
- **`RemoteExecutor`** — Thin wrapper kept for deploy.core compatibility.
- **`DeployPattern`** — Base class for all deploy patterns.
- **`BlueGreenPattern`** — Zero-downtime blue/green deploy via Traefik (or any label-based proxy).
- **`CanaryPattern`** — Gradual canary rollout: deploy new version, scale up in stages.
- **`RollbackOnFailurePattern`** — Capture pre-deploy image tag, roll back automatically on failure.
- **`DiscoveredHost`** — —
- **`ProbeResult`** — Full autonomous probe result for a single host.
- **`AuditCheck`** — Outcome of a single audit probe.
- **`AuditReport`** — —
- **`Auditor`** — Compare a MigrationSpec's expectations against a live target host.
- **`Detector`** — Probe infrastructure and produce InfraState.
- **`Condition`** — A single scoreable condition.
- **`DetectionTemplate`** — Named template for a device+environment+strategy combination.
- **`FactExtractor`** — Extract a single key/value pair into the context dict.
- **`TemplateMatch`** — Scored template match.
- **`DetectionResult`** — Full result of template-based detection.
- **`TemplateEngine`** — Score all templates against a context and return ranked matches.
- **`HostDetectionResult`** — Full detection result for a single host.
- **`WorkflowResult`** — Aggregated result across all probed hosts.
- **`DetectionWorkflow`** — Multi-host detection workflow with template scoring.
- **`StepLibrary`** — Registry of pre-defined named MigrationSteps.
- **`PluginContext`** — Passed to every plugin handler.
- **`PluginRegistry`** — Central registry mapping plugin_type strings to handler callables.
- **`HardwareInfo`** — Hardware diagnostic information.
- **`DSLException`** — Base exception for DSL errors.
- **`StepError`** — Raised when a step fails.
- **`TimeoutError`** — Raised when a step times out.
- **`VerificationError`** — Raised when verification fails.
- **`ConnectionError`** — Raised when SSH/connection fails.
- **`RollbackError`** — Raised when rollback fails.
- **`PythonMigrationRunner`** — Runner for Python-based migrations.
- **`DockerComposeResult`** — Result of docker compose command.
- **`DockerDSL`** — Docker-related DSL actions.
- **`StepContext`** — Tracks the execution of a single step.
- **`MigrationMeta`** — Metadata for a migration.
- **`MigrationRegistry`** — Global registry of migration functions.
- **`StepManager`** — Manages step execution and tracking.
- **`step`** — Context manager for a deployment step.
- **`PanelDefinition`** — Definition of a Raspberry Pi display panel.
- **`ConfigEdit`** — Result of a config.txt edit operation.
- **`BrowserKioskProfile`** — Static definition of a browser kiosk launch profile.
- **`AutostartEntry`** — One entry in a compositor autostart file.
- **`OutputProfile`** — A kanshi output profile definition.
- **`CompositorDefinition`** — Static definition of a Wayland compositor for kiosk use.
- **`MarkpactParseError`** — Raised when a markdown markpact document cannot be parsed.
- **`MarkpactBlock`** — —
- **`MarkpactDocument`** — —
- **`MarkpactCompileError`** — Raised when a markpact document cannot be compiled to MigrationSpec.
- **`ProgressEmitter`** — Emits YAML-formatted progress events to a stream (default: stdout).
- **`StepError`** — Exception raised when a migration step fails.
- **`ResumeState`** — Checkpoint for a single MigrationPlan execution.
- **`ApplyResult`** — —
- **`StateHandler`** — Base class for a declarative state applier.
- **`HardwareStateHandler`** — Applies HardwareInfo-shaped YAML: display transforms, backlight, etc.
- **`InfraStateHandler`** — Placeholder — applies InfraState-shaped YAML (services, ports, etc.).
- **`Executor`** — Execute MigrationPlan steps on a remote host.
- **`GitTransactionResult`** — Result of full version bump transaction with git.
- **`GitVersionBumpTransaction`** — Version bump transaction with Git integration.
- **`StagingResult`** — Result of staging one source.
- **`VersionBumpTransaction`** — Atomic transaction for bumping version across multiple sources.
- **`ChangelogManager`** — Manage CHANGELOG.md in keep-a-changelog format.
- **`SourceConfig`** — Single source of version truth (one file).
- **`GitConfig`** — Git integration settings.
- **`ChangelogConfig`** — Changelog generation settings.
- **`CommitRules`** — Conventional commits → bump type mapping.
- **`CommitsConfig`** — Conventional commits analysis settings.
- **`PackageConfig`** — Single package in monorepo (for policy=independent).
- **`Constraint`** — Cross-package version constraint.
- **`VersionManifest`** — Root manifest model for .redeploy/version.yaml.
- **`GitIntegrationError`** — Git operation failed.
- **`GitIntegration`** — Git operations for version management.
- **`VersionDiff`** — Version comparison result.
- **`ConventionalCommit`** — Parsed conventional commit.
- **`BumpAnalysis`** — Result of analyzing commits for bump decision.
- **`BaseAdapter`** — Base class for source adapters with common utilities.
- **`TomlAdapter`** — Read/write version from TOML files using tomllib/tomli.
- **`RegexAdapter`** — Read/write version using regex pattern with capture group.
- **`YamlAdapter`** — Read/write version from YAML files.
- **`SourceAdapter`** — Protocol for version source adapters.
- **`PlainAdapter`** — Read/write version from plain text file.
- **`JsonAdapter`** — Read/write version from JSON files.
- **`Planner`** — Generate a MigrationPlan from detected infra + desired target.
- **`WorkflowStep`** — —
- **`WorkflowDef`** — Named deployment workflow parsed from ``workflow[name="…"] { … }``.
- **`LoadResult`** — Full result of loading a ``redeploy.css`` file.
- **`DSLNode`** — One parsed block from the CSS-like file.
- **`RedeployDSLParser`** — Parse a ``redeploy.css`` or ``redeploy.less`` file into a list of DSLNode objects.
- **`DockerComposeParser`** — Parser for docker-compose.yml / compose.yaml files.
- **`PortInfo`** — A published / exposed port mapping.
- **`VolumeInfo`** — A volume or bind-mount.
- **`ServiceInfo`** — One logical service / container / pod / deployment.
- **`ConversionWarning`** — A warning emitted by a parser or converter about lossy / uncertain data.
- **`ParsedSpec`** — Common intermediate representation from any IaC/CI-CD parser.
- **`Parser`** — Protocol every format-specific parser must satisfy.
- **`ParserRegistry`** — Dispatch file → registered parser.
- **`ConfigHintsParser`** — Best-effort parser for common DevOps/IaC config files.
- **`DockerComposeParser`** — Parser for Docker Compose files (v2 + v3 schema, Compose Spec).

### Functions

- `to_yaml()` — —
- `load()` — —
- `has_dsi()` — —
- `kms_enabled()` — —
- `dsi_connected()` — —
- `dsi_physically_connected()` — —
- `dsi_enabled()` — —
- `backlight_on()` — —
- `errors()` — —
- `warnings()` — —
- `from_file()` — —
- `resolve_versions()` — —
- `to_infra_state()` — —
- `to_target_config()` — —
- `find_and_load()` — —
- `find_css()` — —
- `env()` — —
- `resolve_env()` — —
- `from_dotenv()` — —
- `apply_to_spec()` — —
- `last_deploy()` — —
- `is_reachable()` — —
- `record_deploy()` — —
- `has_errors()` — —
- `display_summary()` — —
- `save()` — —
- `load_for()` — —
- `list_saved()` — —
- `service()` — —
- `get()` — —
- `upsert()` — —
- `remove()` — —
- `by_tag()` — —
- `by_strategy()` — —
- `reachable()` — —
- `default_path()` — —
- `audit_spec()` — —
- `ok()` — —
- `add()` — —
- `passed()` — —
- `failed()` — —
- `warned()` — —
- `skipped()` — —
- `summary()` — —
- `to_dict()` — —
- `extras()` — —
- `collect()` — —
- `has_binary()` — —
- `has_path()` — —
- `port_listening()` — —
- `has_image()` — —
- `has_systemd_unit()` — —
- `apt_package()` — —
- `disk_free_gib()` — —
- `run()` — —
- `ts()` — —
- `host()` — —
- `app()` — —
- `from_strategy()` — —
- `to_strategy()` — —
- `elapsed_s()` — —
- `steps_total()` — —
- `steps_ok()` — —
- `steps_failed()` — —
- `pattern()` — —
- `version()` — —
- `dry_run()` — —
- `steps()` — —
- `error()` — —
- `record()` — —
- `tail()` — —
- `filter()` — —
- `clear()` — —
- `text()` — —
- `yaml()` — —
- `summary_line()` — —
- `ssh_user()` — —
- `ssh_ip()` — —
- `is_local()` — —
- `is_prod()` — —
- `has_tag()` — —
- `has_expectation()` — —
- `verify_expectations()` — —
- `get_device()` — —
- `by_stage()` — —
- `prod_devices()` — —
- `from_registry()` — —
- `from_config()` — —
- `devices()` — —
- `prod()` — —
- `merge()` — —
- `discover()` — —
- `update_registry()` — —
- `auto_probe()` — —
- `by_tag()` — —
- `by_stage()` — —
- `by_strategy()` — —
- `reachable()` — —
- `from_file()` — —
- `from_registry()` — —
- `merge()` — —
- `expand()` — —
- `run_ssh()` — —
- `run_scp()` — —
- `run_rsync()` — —
- `run_docker_build()` — —
- `run_podman_build()` — —
- `run_docker_health_wait()` — —
- `run_container_log_tail()` — —
- `run_http_check()` — —
- `run_version_check()` — —
- `run_plugin()` — —
- `run_wait()` — —
- `run_inline_script()` — —
- `run_ensure_config_line()` — —
- `run_raspi_config()` — —
- `run_ensure_kanshi_profile()` — —
- `run_ensure_autostart_entry()` — —
- `run_ensure_browser_kiosk_script()` — —
- `rollback_steps()` — —
- `state_key()` — —
- `default_state_path()` — —
- `filter_resumable()` — —
- `detect_handler()` — —
- `apply_state()` — —
- `run_container_build()` — —
- `audit_spec()` — —
- `extract_blueprint()` — —
- `generate_twin()` — —
- `generate_migration()` — —
- `merge_compose_files()` — —
- `build_hw_requirements()` — —
- `extract_services_from_infra()` — —
- `infer_app_url()` — —
- `parse_migration_meta()` — —
- `cli()` — —
- `audit()` — —
- `blueprint_cmd()` — —
- `capture()` — —
- `twin()` — —
- `deploy()` — —
- `show()` — —
- `list_blueprints()` — —
- `bump_cmd()` — —
- `fix_cmd()` — —
- `detect()` — —
- `device_map_cmd()` — —
- `render_yaml()` — —
- `render_json()` — —
- `render_rich()` — —
- `devices()` — —
- `scan()` — —
- `device_add()` — —
- `device_rm()` — —
- `diagnose()` — —
- `diff()` — —
- `exec_cmd()` — —
- `exec_multi_cmd()` — —
- `export_cmd()` — —
- `hardware()` — —
- `import_cmd()` — —
- `init()` — —
- `inspect()` — —
- `mcp_cmd()` — —
- `patterns()` — —
- `plan()` — —
- `apply()` — —
- `migrate()` — —
- `run()` — —
- `plugin_cmd()` — —
- `probe()` — —
- `prompt_cmd()` — —
- `push()` — —
- `state_cmd()` — —
- `status()` — —
- `target()` — —
- `version_cmd()` — —
- `version_current()` — —
- `version_list()` — —
- `version_verify()` — —
- `version_bump()` — —
- `version_set()` — —
- `version_init()` — —
- `version_diff()` — —
- `workflow_cmd()` — —
- `load_spec_or_exit()` — —
- `find_manifest_path()` — —
- `resolve_device()` — —
- `load_spec_with_manifest()` — —
- `overlay_device_onto_spec()` — —
- `run_detect_for_spec()` — —
- `run_detect_workflow()` — —
- `print_plan_table()` — —
- `print_infrastructure_summary()` — —
- `print_docker_services()` — —
- `print_k3s_pods()` — —
- `print_conflicts()` — —
- `print_inspect_app_metadata()` — —
- `print_inspect_environments()` — —
- `print_inspect_templates()` — —
- `print_inspect_workflows()` — —
- `print_inspect_devices()` — —
- `print_inspect_raw_nodes_summary()` — —
- `print_workflow_summary_table()` — —
- `print_workflow_host_details()` — —
- `generate_workflow_output_css()` — —
- `generate_workflow_output_yaml()` — —
- `print_import_spec()` — —
- `execute_query()` — —
- `apply_config_dict()` — —
- `apply_config_file()` — —
- `load_config_file()` — —
- `collect_sqlite_counts()` — —
- `rsync_timeout_for_path()` — —
- `probe_hardware()` — —
- `analyze()` — —
- `probe_runtime()` — —
- `probe_ports()` — —
- `probe_iptables_dnat()` — —
- `probe_docker_services()` — —
- `probe_k3s_services()` — —
- `probe_systemd_services()` — —
- `probe_health()` — —
- `detect_conflicts()` — —
- `detect_strategy()` — —
- `build_context()` — —
- `discover()` — —
- `update_registry()` — —
- `auto_probe()` — —
- `load_css()` — —
- `load_css_text()` — —
- `manifest_to_css()` — —
- `templates_to_css()` — —
- `migration()` — —
- `main()` — —
- `ssh()` — —
- `ssh_available()` — —
- `rsync()` — —
- `scp()` — —
- `wait()` — —
- `http_expect()` — —
- `version_check()` — —
- `ensure_line()` — —
- `ensure_lines()` — —
- `fix_dsi_not_enabled()` — —
- `fix_enable_i2c()` — —
- `fix_enable_spi()` — —
- `generate_fix_plan()` — —
- `ensure_autostart_entry()` — —
- `generate_labwc_autostart()` — —
- `dsi_only_profile()` — —
- `register()` — —
- `get()` — —
- `all_panels()` — —
- `infer_from_hardware()` — —
- `build_raspi_config_command()` — —
- `collect_diagnostics()` — —
- `ask_llm()` — —
- `apply_fix_to_spec()` — —
- `write_repair_log()` — —
- `parse_failed_step()` — —
- `parse_file()` — —
- `parse_dir()` — —
- `make_op3_context_from_ssh_client()` — —
- `snapshot_to_infra_state()` — —
- `snapshot_to_hardware_info()` — —
- `diagnostics_to_hardware_diagnostics()` — —
- `snapshot_to_device_map()` — —
- `compile_markpact_document()` — —
- `compile_markpact_document_to_data()` — —
- `parse_markpact_file()` — —
- `parse_markpact_text()` — —
- `parse_markpact_file_with_refs()` — —
- `extract_script_by_ref()` — —
- `extract_script_from_markdown()` — —
- `schema()` — —
- `plan_spec()` — —
- `run_spec()` — —
- `fix_spec()` — —
- `bump_version()` — —
- `list_specs()` — —
- `exec_ssh()` — —
- `nlp_command()` — —
- `get_spec_content()` — —
- `get_workspace()` — —
- `serve()` — —
- `parse_docker_ps()` — —
- `parse_container_line()` — —
- `parse_system_info()` — —
- `parse_diagnostics()` — —
- `parse_health_info()` — —
- `get_pattern()` — —
- `list_patterns()` — —
- `register_plugin()` — —
- `load_user_plugins()` — —
- `browser_reload()` — —
- `hardware_diagnostic()` — —
- `notify()` — —
- `process_control()` — —
- `systemd_reload()` — —
- `build_schema()` — —
- `load_migration_spec()` — —
- `parse()` — —
- `test_nodes_of_type()` — —
- `test_manifest_to_css_roundtrip()` — —
- `test_templates_to_css()` — —
- `test_load_css_file()` — —
- `test_parse_file()` — —
- `test_parse_dir()` — —
- `test_parse_dir_skip_errors()` — —
- `test_warning_str_with_location()` — —
- `test_warning_str_no_location()` — —
- `test_compile_markpact_document_yaml_subset_to_spec()` — —
- `test_compile_markpact_document_supports_toml_config_and_steps()` — —
- `test_compile_markpact_document_rejects_unsupported_block_kind()` — —
- `test_compile_markpact_document_rejects_unsupported_step_keys()` — —
- `test_parse_markpact_text_extracts_blocks_and_lines()` — —
- `test_parse_markpact_text_requires_markpact_blocks()` — —
- `test_extract_script_by_ref_markpact_ref()` — —
- `test_extract_script_by_ref_not_found()` — —
- `test_parse_markpact_text_with_ref_id()` — —
- `test_plan_k3s_to_docker_generates_stop_k3s()` — —
- `test_plan_no_conflicts_no_stop_k3s()` — —
- `test_plan_risk_elevated_when_stop_steps()` — —
- `test_plan_downtime_rolling_when_same_strategy()` — —
- `test_plan_downtime_includes_seconds_for_cross_strategy()` — —
- `test_infra_state_serializes()` — —
- `test_spec_to_infra_state()` — —
- `test_spec_to_target_config()` — —
- `test_planner_from_spec_generates_steps()` — —
- `test_planner_from_spec_appends_notes()` — —
- `test_planner_from_spec_extra_steps()` — —
- `test_spec_roundtrip_yaml()` — —
- `test_migration_plan_step_count_sane()` — —
- `test_public_api_all_importable()` — —
- `test_executor_writes_audit()` — —
- `test_executor_audit_disabled()` — —
- `test_list_patterns()` — —
- `test_get_pattern_known()` — —
- `test_get_pattern_unknown()` — —
- `test_pattern_registry_keys()` — —
- `test_load_user_plugins_empty_dirs()` — —
- `test_all_names_importable()` — —
- `test_version_string()` — —
- `test_deploy_strategy_values()` — —
- `test_step_action_values()` — —
- `test_step_status_values()` — —
- `test_conflict_severity_values()` — —
- `test_migration_step_construct()` — —
- `test_target_config_defaults()` — —
- `test_target_config_strategy_alias_docker_compose()` — —
- `test_target_config_strategy_alias_kiosk_appliance()` — —
- `test_target_config_strategy_alias_quadlet()` — —
- `test_target_config_strategy_alias_kubernetes()` — —
- `test_target_config_strategy_alias_k8s()` — —
- `test_target_config_strategy_canonical_passthrough()` — —
- `test_infra_state_construct()` — —
- `test_migration_plan_construct()` — —
- `test_planner_importable()` — —
- `test_executor_importable()` — —
- `test_detector_importable()` — —
- `test_ssh_client_local()` — —
- `test_ssh_result_ok()` — —
- `test_ssh_result_fail()` — —
- `test_device_registry_empty()` — —
- `test_known_device_construct()` — —
- `test_fleet_config_importable()` — —
- `test_step_library_importable()` — —
- `test_fleet_importable()` — —
- `test_fleet_empty()` — —
- `test_fleet_from_registry_empty()` — —
- `test_fleet_merge()` — —
- `test_planner_kiosk_appliance_generates_steps()` — —
- `test_planner_docker_compose_alias()` — —
- `test_load_migration_spec_reads_yaml()` — —
- `test_load_migration_spec_reads_supported_markdown()` — —
- `test_load_migration_spec_rejects_unsupported_markdown_block()` — —
- `test_ssh_result_success_alias()` — —
- `test_ssh_result_out_strips()` — —
- `test_local_run_echo()` — —
- `test_local_is_reachable()` — —
- `test_ssh_opts_with_key()` — —
- `test_ssh_opts_no_key()` — —
- `test_run_success()` — —
- `test_run_failure()` — —
- `test_run_timeout()` — —
- `test_remote_probe_is_local()` — —
- `test_remote_probe_not_local()` — —
- `test_check_version_match()` — —
- `test_check_version_mismatch()` — —
- `test_check_version_no_local()` — —
- `test_read_local_version()` — —
- `test_collect_sqlite_counts()` — —
- `test_collect_sqlite_missing_db()` — —
- `test_verify_context_pass()` — —
- `test_verify_context_fail()` — —
- `test_verify_data_integrity_ok()` — —
- `test_verify_data_integrity_mismatch()` — —
- `src()` — —
- `verify_data_integrity()` — —
- `read_local_version()` — —
- `read_remote_version()` — —
- `check_version()` — —
- `check_version_http()` — —
- `verify_sources()` — —
- `bump_version_with_git()` — —
- `bump_package()` — —
- `bump_all_packages()` — —
- `get_commits_since_tag()` — —
- `parse_conventional()` — —
- `analyze_commits()` — —
- `format_analysis_report()` — —
- `diff_manifest_vs_spec()` — —
- `diff_manifest_vs_live()` — —
- `format_diff_report()` — —
- `get_adapter()` — —
- `register_adapter()` — —
- `mock_device_map()` — —
- `test_snapshot_to_device_map_roundtrip()` — —
- `mock_infra()` — —
- `test_snapshot_to_infra_state_parity()` — —
- `mock_hw()` — —
- `test_hardware_yaml_shape()` — —
- `test_op3_importable()` — —
- `test_require_op3_is_noop_when_available()` — —
- `test_make_scanner_defaults_to_hardware_layers()` — —
- `test_make_scanner_instances_are_isolated()` — —
- `test_make_ssh_context_forwards_key()` — —
- `test_end_to_end_mock_scan_physical_display()` — —
- `compose_file()` — —
- `test_add_new_line_to_all_section()` — —
- `test_no_op_when_line_already_present()` — —
- `test_replace_existing_dsi_overlay()` — —
- `test_replace_is_idempotent_for_same_line()` — —
- `test_add_to_pi5_section()` — —
- `test_add_to_existing_section()` — —
- `test_no_op_for_existing_line_in_section()` — —
- `test_ensure_lines_multiple()` — —
- `test_ensure_lines_no_change_when_all_present()` — —
- `test_ensure_lines_partial_update()` — —
- `test_all_panels_non_empty()` — —
- `test_waveshare_8_inch_registered()` — —
- `test_overlay_line_dsi1()` — —
- `test_overlay_line_dsi0()` — —
- `test_official_rpi_panel_registered()` — —
- `test_hyperpixel_panels_registered()` — —
- `test_raspi_config_i2c_enable()` — —
- `test_raspi_config_spi_disable()` — —
- `test_raspi_config_invalid_interface()` — —
- `test_raspi_config_invalid_state()` — —
- `test_autostart_entry_render_with_comment()` — —
- `test_autostart_entry_render_no_comment()` — —
- `test_ensure_autostart_entry_appends_to_empty()` — —
- `test_ensure_autostart_entry_no_op_when_correct()` — —
- `test_ensure_autostart_entry_replaces_stale_line()` — —
- `test_ensure_autostart_entry_appends_preserving_existing()` — —
- `test_ensure_autostart_entry_no_double_newline()` — —
- `test_generate_labwc_autostart_has_kanshi_first()` — —
- `test_generate_labwc_autostart_sleep_between()` — —
- `test_generate_labwc_autostart_default_browser_path()` — —
- `test_generate_labwc_autostart_custom_browser_path()` — —
- `test_generate_labwc_autostart_extra_entries()` — —
- `test_output_profile_to_kanshi_config_basic()` — —
- `test_output_profile_transform_included()` — —
- `test_output_profile_mode_included()` — —
- `test_dsi_only_profile_defaults()` — —
- `test_dsi_only_profile_custom_connector()` — —
- `test_dsi_only_profile_with_transform()` — —
- `test_dsi_only_profile_kanshi_output()` — —
- `test_labwc_uses_kanshi()` — —
- `test_labwc_autostart_path_expands()` — —
- `test_labwc_required_packages()` — —
- `test_compositors_registry_contains_labwc()` — —
- `test_labwc_notes_mention_password_store()` — —
- `test_labwc_notes_warn_about_windowed_flag()` — —
- `test_chromium_kiosk_required_flags()` — —
- `test_chromium_kiosk_incompatible_windowed()` — —
- `test_build_launch_cmd_basic()` — —
- `test_build_launch_cmd_raises_on_incompatible_flag()` — —
- `test_chromium_notes_mention_keyring()` — —
- `test_chromium_wayland_platform_flag()` — —
- `test_no_dsi_overlay_when_dsi_overlays_empty()` — —
- `test_no_dsi_overlay_rule_absent_when_overlay_present()` — —
- `test_auto_detect_conflict_flagged()` — —
- `test_auto_detect_no_conflict_when_zero()` — —
- `test_overlay_but_no_drm_connector_flagged()` — —
- `test_overlay_with_drm_connector_no_connector_error()` — —
- `test_dsi_disconnected_flagged()` — —
- `test_no_backlight_when_dsi_connected()` — —
- `test_backlight_power_off_flagged()` — —
- `test_backlight_brightness_zero_flagged()` — —
- `test_all_ok_emits_info()` — —
- `test_all_ok_no_wayland_warns()` — —
- `test_i2c_chip_missing_flagged()` — —
- `test_i2c_chip_present_no_warn()` — —
- `write_compose()` — —
- `test_parse_docker_ps_full_format()` — —
- `test_parse_docker_ps_partial_format()` — —
- `test_parse_docker_ps_skips_empty_lines()` — —
- `test_parse_docker_ps_skips_no_containers_marker()` — —
- `test_parse_docker_ps_empty()` — —
- `test_parse_container_line_full()` — —
- `test_parse_container_line_no_image()` — —
- `test_parse_container_line_invalid_returns_none()` — —
- `test_parse_system_info_basic()` — —
- `test_parse_system_info_disk()` — —
- `test_parse_system_info_memory()` — —
- `test_parse_system_info_unknown_lines_ignored()` — —
- `test_parse_diagnostics_sections()` — —
- `test_parse_diagnostics_empty()` — —
- `test_parse_diagnostics_docker_section_alias()` — —
- `test_parse_diagnostics_skips_no_markers()` — —
- `test_parse_health_info_full()` — —
- `test_parse_health_info_invalid_health_code()` — —
- `test_parse_health_info_empty()` — —
- `build_c2004_schema()` — —
- `call_llm()` — —
- `test_schema_discovers_c2004_specs()` — —
- `test_schema_has_command_catalogue()` — —
- `test_schema_has_version_and_cwd()` — —
- `test_prompt_dry_run_plan_polish()` — —
- `test_prompt_deploy_english()` — —
- `test_prompt_diagnose_polish()` — —
- `test_prompt_fix_kiosk_polish()` — —
- `test_prompt_bump_minor()` — —
- `test_prompt_fix_with_hint()` — —
- `test_prompt_list_specs()` — —
- `test_prompt_response_has_required_fields()` — —
- `test_prompt_argv_always_starts_with_redeploy()` — —
- `test_prompt_uses_real_spec_paths()` — —
- `test_prompt_cli_schema_only()` — —
- `test_prompt_cli_dry_run_no_confirm()` — —
- `test_placeholder()` — —
- `test_import()` — —
- `to_yaml()` — —
- `load()` — —
- `has_dsi()` — —
- `kms_enabled()` — —
- `dsi_connected()` — —
- `dsi_physically_connected()` — —
- `dsi_enabled()` — —
- `backlight_on()` — —
- `errors()` — —
- `warnings()` — —
- `from_file()` — —
- `resolve_versions()` — —
- `to_infra_state()` — —
- `to_target_config()` — —
- `find_and_load()` — —
- `find_css()` — —
- `env()` — —
- `resolve_env()` — —
- `from_dotenv()` — —
- `apply_to_spec()` — —
- `last_deploy()` — —
- `is_reachable()` — —
- `record_deploy()` — —
- `has_errors()` — —
- `display_summary()` — —
- `save()` — —
- `load_for()` — —
- `list_saved()` — —
- `service()` — —
- `upsert()` — —
- `remove()` — —
- `by_tag()` — —
- `by_strategy()` — —
- `reachable()` — —
- `default_path()` — —
- `ok()` — —
- `add()` — —
- `passed()` — —
- `failed()` — —
- `warned()` — —
- `skipped()` — —
- `summary()` — —
- `to_dict()` — —
- `extras()` — —
- `collect()` — —
- `has_binary()` — —
- `has_path()` — —
- `port_listening()` — —
- `has_image()` — —
- `has_systemd_unit()` — —
- `apt_package()` — —
- `disk_free_gib()` — —
- `ts()` — —
- `host()` — —
- `app()` — —
- `from_strategy()` — —
- `to_strategy()` — —
- `elapsed_s()` — —
- `steps_total()` — —
- `steps_ok()` — —
- `steps_failed()` — —
- `pattern()` — —
- `version()` — —
- `dry_run()` — —
- `steps()` — —
- `error()` — —
- `record()` — —
- `tail()` — —
- `filter()` — —
- `clear()` — —
- `text()` — —
- `yaml()` — —
- `summary_line()` — —
- `ssh_user()` — —
- `ssh_ip()` — —
- `is_local()` — —
- `is_prod()` — —
- `has_tag()` — —
- `has_expectation()` — —
- `verify_expectations()` — —
- `get_device()` — —
- `by_stage()` — —
- `prod_devices()` — —
- `from_registry()` — —
- `from_config()` — —
- `prod()` — —
- `merge()` — —
- `print()` — —
- `cmd_deploy()` — —
- `hardware_cmd()` — —
- `render()` — —
- `apply_query()` — —
- `capture()` — —
- `to_yaml()` — —
- `load()` — —
- `query()` — —
- `apply_config()` — —
- `list_saved()` — —
- `snapshot_command()` — —
- `cmd()` — —
- `notify_slack()` — —
- `notify_slack()` — —
- `print()` — —
- `list_patterns()` — —
- `expand()` — —
- `load_migration_spec()` — —
- `print()` — —
- `deploy()` — —
- `my_migration()` — —
- `ssh_available()` — —
- `scp()` — —
- `wait()` — —
- `ssh()` — —
- `rsync()` — —
- `restart_service()` — —
- `deploy_docker_compose()` — —
- `print()` — —
- `test_deployment()` — —
- `test_real_deployment()` — —
- `http_expect()` — —
- `generate_readme()` — —
- `can_parse()` — —
- `parse()` — —
- `build_schema(root)` — Build the workspace schema dict.
- `collect_sqlite_counts(app_root, db_specs)` — Collect row counts for the given SQLite tables under *app_root*.
- `rsync_timeout_for_path(path, minimum, base, per_mb)` — Compute a conservative rsync timeout based on file size (seconds).
- `collect_diagnostics(host, failed_step)` — Run targeted SSH diagnostics for a failed step, return combined output.
- `ask_llm(failed_step, step_output, diag, spec_text)` — Ask LiteLLM to propose a fixed YAML block for the failed step.
- `apply_fix_to_spec(spec_path, failed_step, llm_response)` — Extract YAML block from LLM response and patch it into the spec file.
- `write_repair_log(spec_path, version, repairs)` — Write/update REPAIR_LOG.md adjacent to spec file.
- `parse_failed_step(executor_summary, executor)` — Extract (step_id, step_output) from executor state or summary string.
- `parse_docker_ps(output)` — Parse 'docker ps --format "{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}|{{.State}}"' output.
- `parse_container_line(line)` — Parse a single NAME|STATUS|IMAGE pipe-delimited container line.
- `parse_system_info(output)` — Parse KEY:VALUE system info lines (HOSTNAME, UPTIME, DISK, MEM, LOAD) into a dict.
- `parse_diagnostics(output)` — Parse multi-section SSH diagnostics output into structured dict.
- `parse_health_info(output)` — Parse health-check SSH output (HOSTNAME, UPTIME, HEALTH, DISK, LOAD) into a dict.
- `verify_data_integrity(ctx, local_counts, remote_counts)` — Compare local vs remote SQLite row counts and record results in *ctx*.
- `load_migration_spec(path)` — Load a deployment spec from disk.
- `get_pattern(name)` — Return pattern class by name, or None if not found.
- `list_patterns()` — Return all registered pattern names.
- `discover(subnet, ssh_users, ssh_port, ping)` — Discover SSH-accessible hosts in the local network.
- `update_registry(hosts, registry, save)` — Merge discovered hosts into DeviceRegistry and optionally save.
- `auto_probe(ip_or_host, users, port, timeout)` — Autonomously probe a host — try all available SSH keys and users.
- `audit_spec(spec_path)` — Convenience: load spec from file and run an audit.
- `schema(directory)` — Discover the workspace: find migration specs, read version, git branch.
- `plan_spec(spec, cwd)` — Preview a migration spec: show all steps without executing anything.
- `run_spec(spec, force, dry_run, heal)` — Apply a migration spec.
- `fix_spec(spec_or_dir, hint, bump, retries)` — Self-healing deploy: bump version → apply spec → LLM retry on failure.
- `bump_version(spec_or_dir, level, cwd)` — Bump the project version and update migration spec header.
- `diagnose(host)` — Run SSH diagnostics on a deployment target and return system state.
- `list_specs(directory)` — List all migration specs found in a directory.
- `exec_ssh(host, command)` — Run an ad-hoc SSH command on a remote host.
- `nlp_command(instruction, dry_run, cwd)` — Translate a natural-language instruction into a redeploy command and run it.
- `get_spec_content(path)` — Read the raw content of a migration spec file.
- `get_workspace()` — Return the workspace schema as JSON string.
- `serve(transport, host, port)` — Start the MCP server.
- `probe_hardware(p)` — Probe hardware state of the remote host and return ``HardwareInfo``.
- `analyze(hw)` — Run all diagnostic rules against *hw* and return findings.
- `build_context(state, probe, manifest)` — Flatten InfraState + ProbeResult into a flat dict for condition evaluation.
- `probe_runtime(p)` — Detect installed runtimes: docker, k3s, podman, systemd.
- `probe_ports(p)` — Detect listening ports and which process owns them.
- `probe_iptables_dnat(p, ports)` — Find iptables DNAT rules stealing specific ports (returns [(port, target_ip)]).
- `probe_docker_services(p)` — List running Docker containers.
- `probe_k3s_services(p, namespaces)` — List running k3s pods.
- `probe_systemd_services(p, app)` — List app-related systemd units (also catches kiosk/chromium/openbox).
- `probe_health(host, app, domain)` — HTTP health checks against known endpoints.
- `detect_conflicts(ports, iptables_dnat, runtime, docker_services)` — Identify conflicts: port stealing, duplicate services, etc.
- `detect_strategy(runtime, docker_services, k3s_services, systemd_services)` — Infer the current deployment strategy from detected services.
- `apply_config_dict(data, probe, console)` — Apply *data* to the host behind *probe*.
- `apply_config_file(path)` — Load *path* and apply its hardware/infra settings to the remote host.
- `load_config_file(path)` — Read *path* and return a dict (YAML or JSON auto-detected).
- `print_plan_table(console, migration)` — Print migration plan as a table.
- `print_infrastructure_summary(console, state, host)` — Print infrastructure summary from detection state.
- `print_docker_services(console, state)` — Print Docker container status.
- `print_k3s_pods(console, state)` — Print k3s pod status.
- `print_conflicts(console, state)` — Print detection conflicts.
- `print_inspect_app_metadata(console, result)` — Print app metadata from inspect result.
- `print_inspect_environments(console, result)` — Print environments from inspect result.
- `print_inspect_templates(console, result)` — Print detection templates from inspect result.
- `print_inspect_workflows(console, result)` — Print workflows from inspect result.
- `print_inspect_devices(console, result)` — Print devices from inspect result.
- `print_inspect_raw_nodes_summary(console, result)` — Print raw nodes summary from inspect result.
- `print_workflow_summary_table(console, result)` — Print workflow summary as a table.
- `print_workflow_host_details(console, result)` — Print detailed host information from workflow result.
- `generate_workflow_output_css(console, result, app, save_yaml)` — Generate and display/save CSS output from workflow.
- `generate_workflow_output_yaml(console, result, save_yaml)` — Generate and display/save YAML output from workflow.
- `print_import_spec(console, spec)` — Print a ParsedSpec summary to the Rich console.
- `execute_query(obj, query_expr, output_fmt, echo)` — Run a JMESPath *query_expr* against *obj* and echo the result.
- `cli(ctx, verbose)` — redeploy — Infrastructure migration toolkit: detect → plan → apply
- `load_spec_or_exit(console, path)` — Load a migration spec or exit with error.
- `find_manifest_path()` — Find redeploy.yaml manifest in current or parent directories.
- `resolve_device(console, device_id)` — Resolve device from registry or auto-probe.
- `load_spec_with_manifest(console, spec_file, dev)` — Load spec and apply manifest/device overlays.
- `overlay_device_onto_spec(spec, dev, console)` — Overlay device values onto spec target configuration.
- `run_detect_for_spec(console, spec, do_detect)` — Run detect if requested and return planner.
- `run_detect_workflow(console, hosts, manifest, app)` — Run DetectionWorkflow and print rich report.
- `target(device_id, spec_file, dry_run, plan_only)` — Deploy a spec to a specific registered device.
- `devices(tag, strategy, rpi, reachable)` — List known devices from ~/.config/redeploy/devices.yaml.
- `scan(subnet, ssh_users, ssh_port, ping)` — Discover SSH-accessible devices on the local network.
- `device_add(host, device_id, name, tags)` — Add or update a device in the registry.
- `device_rm(device_id)` — Remove a device from the registry.
- `state_cmd(ctx, action, spec_file, host)` — Inspect or clear resume checkpoints.
- `inspect(ctx, css_file)` — Show parsed content of redeploy.css — environments, templates, workflows.
- `render_yaml(dm)` — Emit *dm* as YAML to stdout.
- `render_json(dm)` — Emit *dm* as indented JSON to stdout.
- `render_rich(console, dm)` — Full rich console report with hardware, infra and issues tables.
- `bump_cmd(spec_or_dir, minor, major)` — Bump the project version (patch by default).
- `fix_cmd(spec_or_dir, hint, bump, minor)` — Self-healing deploy: bump version, then run with LLM auto-fix on failure.
- `exec_cmd(ctx, ref, host, markdown_file)` — Execute a script from a markdown codeblock by reference.
- `exec_multi_cmd(ctx, refs, host, markdown_file)` — Execute multiple scripts from markdown codeblocks by reference.
- `blueprint_cmd()` — Extract, generate and apply DeviceBlueprints (portable deploy recipes).
- `capture(host, name, compose_files, migration_file)` — Probe HOST and extract a DeviceBlueprint from all available sources.
- `twin(blueprint_file, out_path, platform, port_offset)` — Generate a docker-compose.twin.yml from BLUEPRINT_FILE for local testing.
- `deploy(blueprint_file, target_host, out_path, remote_dir)` — Generate (and optionally run) a migration.yaml for TARGET_HOST from BLUEPRINT_FILE.
- `show(blueprint_file, fmt, apply_config, query_expr)` — Display a saved DeviceBlueprint.
- `list_blueprints()` — List all saved DeviceBlueprints.
- `export_cmd(ctx, output, src_file, fmt)` — Convert between redeploy.css and redeploy.yaml formats.
- `init(host, app, domain, strategy)` — Scaffold migration.yaml + redeploy.yaml for this project.
- `status(spec_file)` — Show current project manifest and spec summary.
- `probe(hosts, subnet, users, ssh_port)` — Autonomously probe one or more hosts — detect SSH credentials, strategy, app.
- `mcp_cmd(transport, host, port)` — Start the redeploy MCP server.
- `plugin_cmd(ctx, subcommand, name)` — List or inspect registered redeploy plugins.
- `import_cmd(source, output, target_host, target_strategy)` — Parse an IaC/CI-CD file and produce a migration.yaml scaffold.
- `plan(ctx, infra, target, strategy)` — Generate migration-plan.yaml from infra.yaml + target config.
- `apply(ctx, plan_file, dry_run, step)` — Execute a migration plan.
- `migrate(ctx, host, app, domain)` — Full pipeline: detect → plan → apply.
- `run(ctx, spec_file, dry_run, plan_only)` — Execute migration from a single YAML spec (source + target in one file).
- `detect(ctx, host, app, domain)` — Probe infrastructure and produce infra.yaml.
- `device_map_cmd(host, name, tags, save)` — Generate a full standardized device snapshot (hardware + infra + diagnostics).
- `hardware(host, output_fmt, show_fix, apply_fix_component)` — Probe and diagnose hardware on a remote host.
- `prompt_cmd(instruction, schema_only, dry_run, yes)` — Natural-language → redeploy command via LLM.
- `diff(ci_file, host, from_src, to_src)` — Compare IaC file vs live host (drift detection).  [Phase 3 — coming soon]
- `workflow_cmd(ctx, name, css_file, dry_run)` — Run a named workflow from redeploy.css.
- `push(host, files, dry_run, ssh_key)` — Apply desired-state YAML/JSON file(s) to a remote host.
- `patterns(name)` — List available deploy patterns or show detail for one.
- `diagnose(ctx, spec, host, ssh_key)` — Compare a migration spec against the live target host.
- `audit(last, host, app, only_failed)` — Show deploy audit log from ~/.config/redeploy/audit.jsonl.
- `version_cmd()` — Declarative version management: bump, verify, diff.
- `version_current(manifest, package_name, all_packages)` — Show current version from manifest.
- `version_list(manifest, package_name, all_packages)` — List all version sources and their values.
- `version_verify(manifest, package_name, all_packages)` — Verify all sources match manifest version.
- `version_bump(type, manifest, package, all_packages)` — Bump version across all sources atomically.
- `version_set(version, manifest_path_str, package_name, all_packages)` — Set an explicit version across all manifest sources.
- `version_init(scan, review, interactive, excluded_paths)` — Initialize .redeploy/version.yaml manifest.
- `version_diff(manifest, package_name, all_packages, spec)` — Compare manifest version vs spec vs live.
- `register_plugin(name)` — Decorator shortcut: @register_plugin('browser_reload').
- `load_user_plugins()` — Load user plugins from project-local and user-global directories.
- `notify(ctx)` — —
- `process_control(ctx)` — Kill processes on specified ports.
- `browser_reload(ctx)` — —
- `systemd_reload(ctx)` — —
- `hardware_diagnostic(ctx)` — Perform hardware diagnostics and provide recommendations.
- `ssh(host, command, timeout, check)` — Execute a command on a remote host via SSH.
- `ssh_available(host, timeout, interval)` — Wait for SSH to become available on a host.
- `rsync(src, dst, exclude, delete)` — Synchronize files using rsync.
- `scp(src, dst, timeout)` — Copy files using SCP.
- `wait(seconds, message)` — Wait for specified seconds.
- `http_expect(url, expect, timeout, retries)` — Verify HTTP endpoint returns expected content.
- `version_check(manifest_path, expect, host, url)` — Verify deployed version matches expectation.
- `main()` — CLI entry point for running Python migrations.
- `migration(name, version, description, author)` — Decorator to mark a function as a migration.
- `register(panel)` — Register a panel in the registry.
- `get(panel_id)` — Get a panel by ID.
- `all_panels()` — Get all registered panels sorted by vendor and ID.
- `infer_from_hardware(hw)` — Heuristic panel detection from HardwareInfo.
- `ensure_line(content, line)` — Ensure `line` is present in [section] of config.txt.
- `ensure_lines(content, lines)` — Apply multiple lines in one pass — important because each `ensure_line` re-parses.
- `fix_dsi_not_enabled(hw, panel)` — Generate steps to configure DSI panel + reboot + verify.
- `fix_enable_i2c(hw, panel)` — Enable I2C interface via raspi-config.
- `fix_enable_spi(hw, panel)` — Enable SPI interface via raspi-config.
- `generate_fix_plan(hw, component, panel)` — From a component name or rule name, return fix steps.
- `build_raspi_config_command(interface, state)` — Build a raspi-config nonint command.
- `ensure_autostart_entry(content, entry)` — Idempotently add or replace an entry in an autostart file.
- `generate_labwc_autostart(kiosk_script, kanshi_settle_secs, extra_entries)` — Generate a complete labwc autostart file for a kiosk deployment.
- `dsi_only_profile(dsi_connector, hdmi_connectors, profile_name, transform)` — Factory: DSI panel enabled, all HDMI outputs disabled.
- `parse_markpact_file(path)` — —
- `parse_markpact_text(text)` — —
- `parse_markpact_file_with_refs(path)` — Parse markpact file and extract all referenced scripts.
- `extract_script_by_ref(text, ref_id, language)` — Extract script from codeblock marked with markpact:ref <ref_id>.
- `extract_script_from_markdown(text, section_id, language)` — Extract script content from a markdown code block by section heading.
- `compile_markpact_document(document)` — —
- `compile_markpact_document_to_data(document)` — —
- `state_key(spec_path, host)` — Stable, filesystem-safe identifier for one (spec, host) checkpoint.
- `default_state_path(spec_path, host, base_dir)` — —
- `filter_resumable(step_ids, state)` — Return ids that are NOT yet completed (preserves order).
- `detect_handler(data)` — Return the first handler that accepts *data*, or None.
- `apply_state(data, p, console)` — Auto-detect file type and apply desired state.
- `run_ssh(step, probe)` — Execute SSH command on remote host.
- `run_scp(step, probe, plan)` — Copy file via SCP.
- `run_rsync(step, probe, plan)` — Sync files via rsync.
- `run_docker_build(step, probe, emitter)` — Run docker compose build on remote with periodic progress polling.
- `run_podman_build(step, probe, emitter)` — Run podman build on remote with periodic progress polling.
- `run_docker_health_wait(step, probe)` — Wait until all containers reach 'healthy' or 'running' status.
- `run_container_log_tail(step, probe)` — Fetch and log the last N lines from each container after start.
- `run_http_check(step, probe, retries, delay)` — HTTP check via SSH curl on the remote host (avoids local network/firewall issues).
- `run_version_check(step, probe)` — Version check via SSH curl on the remote host.
- `run_plugin(step, probe, plan, emitter)` — Dispatch to a registered plugin handler.
- `run_wait(step)` — Wait for specified number of seconds.
- `run_inline_script(step, probe, plan)` — Execute multiline bash script via SSH using base64 encoding.
- `run_ensure_config_line(step, probe)` — Idempotent add/replace a line in a remote config.txt.
- `run_raspi_config(step, probe)` — Run raspi-config nonint to enable/disable an interface.
- `run_ensure_kanshi_profile(step, probe)` — Idempotently write or replace a named kanshi output profile.
- `run_ensure_autostart_entry(step, probe)` — Idempotently add or replace keyed entries in a compositor autostart file.
- `run_ensure_browser_kiosk_script(step, probe)` — Write a kiosk-launch.sh script to the remote device.
- `rollback_steps(completed_steps, probe, state)` — Rollback completed steps in reverse order.
- `bump_version(manifest, bump_type, new_version)` — Bump version across all sources atomically.
- `verify_sources(manifest)` — Verify all sources are in sync with manifest.version.
- `bump_version_with_git(manifest, bump_type, repo_path, new_version)` — Bump version with optional git integration.
- `bump_package(manifest, package_name, bump_type, new_version)` — Bump version of a single package in a monorepo manifest.
- `bump_all_packages(manifest, bump_type)` — Bump all packages in a monorepo manifest independently.
- `get_commits_since_tag(repo_path, tag)` — Get commit messages since tag.
- `read_local_version(workspace_root, app)` — Read VERSION file from local workspace.
- `read_remote_version(remote, remote_dir, app)` — Read VERSION file from remote device via SSH.
- `check_version(local, remote)` — Compare local vs remote version string. Returns (match, detail_line).
- `check_version_http(base_url, expected_version, timeout, endpoint)` — Call *endpoint* on a running service. Returns (ok, summary_line, payload).
- `diff_manifest_vs_spec(manifest, spec_version)` — Compare manifest version vs migration.yaml target.version.
- `diff_manifest_vs_live(manifest, live_version)` — Compare manifest version vs live deployed version.
- `format_diff_report(diffs, manifest_version)` — Format diff results as human-readable report.
- `parse_conventional(message)` — Parse a conventional commit message.
- `analyze_commits(since_tag, repo_path, config)` — Analyze commits since tag to determine bump type.
- `format_analysis_report(analysis)` — Format bump analysis as human-readable report.
- `get_adapter(format_name)` — Get adapter by format name.
- `register_adapter(format_name, adapter)` — Register custom adapter.
- `extract_blueprint()` — Build a DeviceBlueprint by reconciling all available sources.
- `build_hw_requirements(hw)` — Derive hardware requirements from a probed *hw* object.
- `merge_compose_files(compose_files, services, seen)` — Parse each docker-compose file and merge specs into *services* / *seen*.
- `extract_services_from_infra(infra, seen)` — Return :class:`ServiceSpec` objects for every service found in *infra*.
- `infer_app_url(infra)` — Guess the application URL from open ports on *infra*.
- `parse_migration_meta(path)` — Read *path* and return ``{"version": "…", "strategy": "…"}`` if found.
- `generate_twin(blueprint)` — Render a docker-compose YAML string for a local digital-twin.
- `generate_migration(blueprint)` — Render a migration.yaml for deploying blueprint to *target_host*.
- `make_op3_context_from_ssh_client(ssh_client)` — Convert :class:`redeploy.ssh.SshClient` -> :class:`opstree.SSHContext`.
- `snapshot_to_infra_state(snapshot, host)` — Convert opstree.Snapshot -> redeploy.InfraState (backward compat).
- `snapshot_to_hardware_info(snapshot)` — Convert opstree.Snapshot -> redeploy.HardwareInfo.
- `diagnostics_to_hardware_diagnostics(diagnostics)` — Convert op3 :class:`opstree.diagnostics.Diagnostic` -> redeploy :class:`redeploy.models.HardwareDiagnostic`.
- `snapshot_to_device_map(snapshot, host, tags)` — Convert opstree.Snapshot -> redeploy.DeviceMap.
- `load_css(path)` — Parse ``redeploy.css`` and return manifest + templates + workflows.
- `load_css_text(text, source_file)` — Parse CSS text directly (for tests).
- `manifest_to_css(manifest, app)` — Render a ProjectManifest back to ``redeploy.css`` format.
- `templates_to_css(templates)` — Render DetectionTemplate list to CSS block.
- `parse_file(path)` — Parse a single file with auto-detected format.
- `parse_dir(root, recursive, skip_errors)` — Parse all recognised files under *root*.
- `parse_json_file(path)` — Tiny helper for plugin authors; currently unused by built-ins.
- `verify_deployment()` — —
- `print()` — —
- `check_prerequisites()` — —
- `print()` — —
- `verify_all_services()` — —
- `print()` — —
- `exit()` — —
- `probe()` — —
- `version_cmd()` — —
- `version_current()` — —
- `version_list()` — —
- `version_verify()` — —
- `version_bump()` — —
- `version_set()` — —
- `version_init()` — —
- `version_diff()` — —
- `parse_json_file()` — —
- `load_css()` — —
- `load_css_text()` — —
- `manifest_to_css()` — —
- `templates_to_css()` — —
- `devices()` — —
- `scan()` — —
- `device_add()` — —
- `device_rm()` — —
- `render_yaml()` — —
- `render_json()` — —
- `render_rich()` — —
- `extract_blueprint()` — —
- `import_cmd()` — —
- `merge_compose_files()` — —
- `blueprint_cmd()` — —
- `capture()` — —
- `twin()` — —
- `deploy()` — —
- `show()` — —
- `list_blueprints()` — —
- `device_map_cmd()` — —
- `generate_twin()` — —
- `generate_migration()` — —
- `audit()` — —
- `detect_handler()` — —
- `apply_state()` — —
- `parse_conventional()` — —
- `analyze_commits()` — —
- `format_analysis_report()` — —
- `collect_diagnostics()` — —
- `ask_llm()` — —
- `apply_fix_to_spec()` — —
- `write_repair_log()` — —
- `parse_failed_step()` — —
- `discover()` — —
- `update_registry()` — —
- `auto_probe()` — —
- `bump_cmd()` — —
- `fix_cmd()` — —
- `browser_reload()` — —
- `run_ssh()` — —
- `run_scp()` — —
- `run_rsync()` — —
- `run_docker_build()` — —
- `run_podman_build()` — —
- `run_docker_health_wait()` — —
- `run_container_log_tail()` — —
- `run_http_check()` — —
- `run_version_check()` — —
- `run_plugin()` — —
- `run_wait()` — —
- `run_inline_script()` — —
- `run_ensure_config_line()` — —
- `run_raspi_config()` — —
- `run_ensure_kanshi_profile()` — —
- `run_ensure_autostart_entry()` — —
- `run_ensure_browser_kiosk_script()` — —
- `prompt_cmd()` — —
- `push()` — —
- `main()` — —
- `build_schema()` — —
- `audit_spec()` — —
- `hardware_diagnostic()` — —
- `ensure_line()` — —
- `ensure_lines()` — —
- `parse_markpact_file()` — —
- `parse_markpact_text()` — —
- `parse_markpact_file_with_refs()` — —
- `extract_script_by_ref()` — —
- `extract_script_from_markdown()` — —
- `parse_file()` — —
- `parse_dir()` — —
- `probe_runtime()` — —
- `probe_ports()` — —
- `probe_iptables_dnat()` — —
- `probe_docker_services()` — —
- `probe_k3s_services()` — —
- `probe_systemd_services()` — —
- `probe_health()` — —
- `detect_conflicts()` — —
- `detect_strategy()` — —
- `plugin_cmd()` — —
- `plan()` — —
- `apply()` — —
- `migrate()` — —
- `run()` — —
- `hardware()` — —
- `bump_version()` — —
- `verify_sources()` — —
- `bump_version_with_git()` — —
- `bump_package()` — —
- `bump_all_packages()` — —
- `build_hw_requirements()` — —
- `parse_docker_ps()` — —
- `parse_container_line()` — —
- `parse_system_info()` — —
- `parse_diagnostics()` — —
- `parse_health_info()` — —
- `status()` — —
- `systemd_reload()` — —
- `process_control()` — —
- `compile_markpact_document()` — —
- `compile_markpact_document_to_data()` — —
- `load_spec_or_exit()` — —
- `find_manifest_path()` — —
- `resolve_device()` — —
- `load_spec_with_manifest()` — —
- `overlay_device_onto_spec()` — —
- `run_detect_for_spec()` — —
- `run_detect_workflow()` — —
- `target()` — —
- `exec_cmd()` — —
- `exec_multi_cmd()` — —
- `init()` — —
- `detect()` — —
- `workflow_cmd()` — —
- `make_op3_context_from_ssh_client()` — —
- `snapshot_to_infra_state()` — —
- `snapshot_to_hardware_info()` — —
- `diagnostics_to_hardware_diagnostics()` — —
- `snapshot_to_device_map()` — —
- `build_context()` — —
- `print_plan_table()` — —
- `print_infrastructure_summary()` — —
- `print_docker_services()` — —
- `print_k3s_pods()` — —
- `print_conflicts()` — —
- `print_inspect_app_metadata()` — —
- `print_inspect_environments()` — —
- `print_inspect_templates()` — —
- `print_inspect_workflows()` — —
- `print_inspect_devices()` — —
- `print_inspect_raw_nodes_summary()` — —
- `print_workflow_summary_table()` — —
- `print_workflow_host_details()` — —
- `generate_workflow_output_css()` — —
- `generate_workflow_output_yaml()` — —
- `print_import_spec()` — —
- `export_cmd()` — —
- `parse_migration_meta()` — —
- `read_local_version()` — —
- `read_remote_version()` — —
- `check_version()` — —
- `check_version_http()` — —
- `verify_data_integrity()` — —
- `patterns()` — —
- `rollback_steps()` — —
- `diff_manifest_vs_spec()` — —
- `diff_manifest_vs_live()` — —
- `format_diff_report()` — —
- `extract_services_from_infra()` — —
- `infer_app_url()` — —
- `collect_sqlite_counts()` — —
- `rsync_timeout_for_path()` — —
- `state_cmd()` — —
- `register_plugin()` — —
- `load_user_plugins()` — —
- `ssh()` — —
- `ssh_available()` — —
- `rsync()` — —
- `scp()` — —
- `wait()` — —
- `http_expect()` — —
- `version_check()` — —
- `fix_dsi_not_enabled()` — —
- `fix_enable_i2c()` — —
- `fix_enable_spi()` — —
- `generate_fix_plan()` — —
- `get_commits_since_tag()` — —
- `notify()` — —
- `ensure_autostart_entry()` — —
- `generate_labwc_autostart()` — —
- `cli()` — —
- `get_pattern()` — —
- `list_patterns()` — —
- `schema()` — —
- `plan_spec()` — —
- `run_spec()` — —
- `fix_spec()` — —
- `diagnose()` — —
- `list_specs()` — —
- `exec_ssh()` — —
- `nlp_command()` — —
- `get_spec_content()` — —
- `get_workspace()` — —
- `serve()` — —
- `execute_query()` — —
- `dsi_only_profile()` — —
- `state_key()` — —
- `default_state_path()` — —
- `filter_resumable()` — —
- `load_migration_spec()` — —
- `probe_hardware()` — —
- `apply_config_dict()` — —
- `apply_config_file()` — —
- `inspect()` — —
- `analyze()` — —
- `load_config_file()` — —
- `migration()` — —
- `build_raspi_config_command()` — —
- `register()` — —
- `get()` — —
- `all_panels()` — —
- `infer_from_hardware()` — —
- `get_adapter()` — —
- `register_adapter()` — —
- `mcp_cmd()` — —
- `diff()` — —
- `by_tag()` — —
- `by_stage()` — —
- `by_strategy()` — —
- `reachable()` — —
- `from_file()` — —
- `from_registry()` — —
- `merge()` — —
- `expand()` — —
- `print()` — —
- `cmd_deploy()` — —
- `hardware_cmd()` — —
- `render()` — —
- `apply_query()` — —
- `to_yaml()` — —
- `load()` — —
- `query()` — —
- `apply_config()` — —
- `list_saved()` — —
- `snapshot_command()` — —
- `cmd()` — —
- `notify_slack()` — —
- `my_migration()` — —
- `restart_service()` — —
- `deploy_docker_compose()` — —
- `test_deployment()` — —
- `test_real_deployment()` — —
- `can_parse()` — —
- `parse()` — —
- `verify_deployment()` — —
- `check_prerequisites()` — —
- `verify_all_services()` — —
- `exit()` — —
- `generate_readme()` — —
- `run_container_build()` — —
- `test_nodes_of_type()` — —
- `test_manifest_to_css_roundtrip()` — —
- `test_templates_to_css()` — —
- `test_load_css_file()` — —
- `test_parse_file()` — —
- `test_parse_dir()` — —
- `test_parse_dir_skip_errors()` — —
- `test_warning_str_with_location()` — —
- `test_warning_str_no_location()` — —
- `test_compile_markpact_document_yaml_subset_to_spec()` — —
- `test_compile_markpact_document_supports_toml_config_and_steps()` — —
- `test_compile_markpact_document_rejects_unsupported_block_kind()` — —
- `test_compile_markpact_document_rejects_unsupported_step_keys()` — —
- `test_parse_markpact_text_extracts_blocks_and_lines()` — —
- `test_parse_markpact_text_requires_markpact_blocks()` — —
- `test_extract_script_by_ref_markpact_ref()` — —
- `test_extract_script_by_ref_not_found()` — —
- `test_parse_markpact_text_with_ref_id()` — —
- `test_plan_k3s_to_docker_generates_stop_k3s()` — —
- `test_plan_no_conflicts_no_stop_k3s()` — —
- `test_plan_risk_elevated_when_stop_steps()` — —
- `test_plan_downtime_rolling_when_same_strategy()` — —
- `test_plan_downtime_includes_seconds_for_cross_strategy()` — —
- `test_infra_state_serializes()` — —
- `test_spec_to_infra_state()` — —
- `test_spec_to_target_config()` — —
- `test_planner_from_spec_generates_steps()` — —
- `test_planner_from_spec_appends_notes()` — —
- `test_planner_from_spec_extra_steps()` — —
- `test_spec_roundtrip_yaml()` — —
- `test_migration_plan_step_count_sane()` — —
- `test_public_api_all_importable()` — —
- `test_executor_writes_audit()` — —
- `test_executor_audit_disabled()` — —
- `test_list_patterns()` — —
- `test_get_pattern_known()` — —
- `test_get_pattern_unknown()` — —
- `test_pattern_registry_keys()` — —
- `test_load_user_plugins_empty_dirs()` — —
- `test_all_names_importable()` — —
- `test_version_string()` — —
- `test_deploy_strategy_values()` — —
- `test_step_action_values()` — —
- `test_step_status_values()` — —
- `test_conflict_severity_values()` — —
- `test_migration_step_construct()` — —
- `test_target_config_defaults()` — —
- `test_target_config_strategy_alias_docker_compose()` — —
- `test_target_config_strategy_alias_kiosk_appliance()` — —
- `test_target_config_strategy_alias_quadlet()` — —
- `test_target_config_strategy_alias_kubernetes()` — —
- `test_target_config_strategy_alias_k8s()` — —
- `test_target_config_strategy_canonical_passthrough()` — —
- `test_infra_state_construct()` — —
- `test_migration_plan_construct()` — —
- `test_planner_importable()` — —
- `test_executor_importable()` — —
- `test_detector_importable()` — —
- `test_ssh_client_local()` — —
- `test_ssh_result_ok()` — —
- `test_ssh_result_fail()` — —
- `test_device_registry_empty()` — —
- `test_known_device_construct()` — —
- `test_fleet_config_importable()` — —
- `test_step_library_importable()` — —
- `test_fleet_importable()` — —
- `test_fleet_empty()` — —
- `test_fleet_from_registry_empty()` — —
- `test_fleet_merge()` — —
- `test_planner_kiosk_appliance_generates_steps()` — —
- `test_planner_docker_compose_alias()` — —
- `test_load_migration_spec_reads_yaml()` — —
- `test_load_migration_spec_reads_supported_markdown()` — —
- `test_load_migration_spec_rejects_unsupported_markdown_block()` — —
- `test_ssh_result_success_alias()` — —
- `test_ssh_result_out_strips()` — —
- `test_local_run_echo()` — —
- `test_local_is_reachable()` — —
- `test_ssh_opts_with_key()` — —
- `test_ssh_opts_no_key()` — —
- `test_run_success()` — —
- `test_run_failure()` — —
- `test_run_timeout()` — —
- `test_remote_probe_is_local()` — —
- `test_remote_probe_not_local()` — —
- `test_check_version_match()` — —
- `test_check_version_mismatch()` — —
- `test_check_version_no_local()` — —
- `test_read_local_version()` — —
- `test_collect_sqlite_counts()` — —
- `test_collect_sqlite_missing_db()` — —
- `test_verify_context_pass()` — —
- `test_verify_context_fail()` — —
- `test_verify_data_integrity_ok()` — —
- `test_verify_data_integrity_mismatch()` — —
- `src()` — —
- `mock_device_map()` — —
- `test_snapshot_to_device_map_roundtrip()` — —
- `mock_infra()` — —
- `test_snapshot_to_infra_state_parity()` — —
- `mock_hw()` — —
- `test_hardware_yaml_shape()` — —
- `test_op3_importable()` — —
- `test_require_op3_is_noop_when_available()` — —
- `test_make_scanner_defaults_to_hardware_layers()` — —
- `test_make_scanner_instances_are_isolated()` — —
- `test_make_ssh_context_forwards_key()` — —
- `test_end_to_end_mock_scan_physical_display()` — —
- `compose_file()` — —
- `test_add_new_line_to_all_section()` — —
- `test_no_op_when_line_already_present()` — —
- `test_replace_existing_dsi_overlay()` — —
- `test_replace_is_idempotent_for_same_line()` — —
- `test_add_to_pi5_section()` — —
- `test_add_to_existing_section()` — —
- `test_no_op_for_existing_line_in_section()` — —
- `test_ensure_lines_multiple()` — —
- `test_ensure_lines_no_change_when_all_present()` — —
- `test_ensure_lines_partial_update()` — —
- `test_all_panels_non_empty()` — —
- `test_waveshare_8_inch_registered()` — —
- `test_overlay_line_dsi1()` — —
- `test_overlay_line_dsi0()` — —
- `test_official_rpi_panel_registered()` — —
- `test_hyperpixel_panels_registered()` — —
- `test_raspi_config_i2c_enable()` — —
- `test_raspi_config_spi_disable()` — —
- `test_raspi_config_invalid_interface()` — —
- `test_raspi_config_invalid_state()` — —
- `test_autostart_entry_render_with_comment()` — —
- `test_autostart_entry_render_no_comment()` — —
- `test_ensure_autostart_entry_appends_to_empty()` — —
- `test_ensure_autostart_entry_no_op_when_correct()` — —
- `test_ensure_autostart_entry_replaces_stale_line()` — —
- `test_ensure_autostart_entry_appends_preserving_existing()` — —
- `test_ensure_autostart_entry_no_double_newline()` — —
- `test_generate_labwc_autostart_has_kanshi_first()` — —
- `test_generate_labwc_autostart_sleep_between()` — —
- `test_generate_labwc_autostart_default_browser_path()` — —
- `test_generate_labwc_autostart_custom_browser_path()` — —
- `test_generate_labwc_autostart_extra_entries()` — —
- `test_output_profile_to_kanshi_config_basic()` — —
- `test_output_profile_transform_included()` — —
- `test_output_profile_mode_included()` — —
- `test_dsi_only_profile_defaults()` — —
- `test_dsi_only_profile_custom_connector()` — —
- `test_dsi_only_profile_with_transform()` — —
- `test_dsi_only_profile_kanshi_output()` — —
- `test_labwc_uses_kanshi()` — —
- `test_labwc_autostart_path_expands()` — —
- `test_labwc_required_packages()` — —
- `test_compositors_registry_contains_labwc()` — —
- `test_labwc_notes_mention_password_store()` — —
- `test_labwc_notes_warn_about_windowed_flag()` — —
- `test_chromium_kiosk_required_flags()` — —
- `test_chromium_kiosk_incompatible_windowed()` — —
- `test_build_launch_cmd_basic()` — —
- `test_build_launch_cmd_raises_on_incompatible_flag()` — —
- `test_chromium_notes_mention_keyring()` — —
- `test_chromium_wayland_platform_flag()` — —
- `test_no_dsi_overlay_when_dsi_overlays_empty()` — —
- `test_no_dsi_overlay_rule_absent_when_overlay_present()` — —
- `test_auto_detect_conflict_flagged()` — —
- `test_auto_detect_no_conflict_when_zero()` — —
- `test_overlay_but_no_drm_connector_flagged()` — —
- `test_overlay_with_drm_connector_no_connector_error()` — —
- `test_dsi_disconnected_flagged()` — —
- `test_no_backlight_when_dsi_connected()` — —
- `test_backlight_power_off_flagged()` — —
- `test_backlight_brightness_zero_flagged()` — —
- `test_all_ok_emits_info()` — —
- `test_all_ok_no_wayland_warns()` — —
- `test_i2c_chip_missing_flagged()` — —
- `test_i2c_chip_present_no_warn()` — —
- `write_compose()` — —
- `test_parse_docker_ps_full_format()` — —
- `test_parse_docker_ps_partial_format()` — —
- `test_parse_docker_ps_skips_empty_lines()` — —
- `test_parse_docker_ps_skips_no_containers_marker()` — —
- `test_parse_docker_ps_empty()` — —
- `test_parse_container_line_full()` — —
- `test_parse_container_line_no_image()` — —
- `test_parse_container_line_invalid_returns_none()` — —
- `test_parse_system_info_basic()` — —
- `test_parse_system_info_disk()` — —
- `test_parse_system_info_memory()` — —
- `test_parse_system_info_unknown_lines_ignored()` — —
- `test_parse_diagnostics_sections()` — —
- `test_parse_diagnostics_empty()` — —
- `test_parse_diagnostics_docker_section_alias()` — —
- `test_parse_diagnostics_skips_no_markers()` — —
- `test_parse_health_info_full()` — —
- `test_parse_health_info_invalid_health_code()` — —
- `test_parse_health_info_empty()` — —
- `build_c2004_schema()` — —
- `call_llm()` — —
- `test_schema_discovers_c2004_specs()` — —
- `test_schema_has_command_catalogue()` — —
- `test_schema_has_version_and_cwd()` — —
- `test_prompt_dry_run_plan_polish()` — —
- `test_prompt_deploy_english()` — —
- `test_prompt_diagnose_polish()` — —
- `test_prompt_fix_kiosk_polish()` — —
- `test_prompt_bump_minor()` — —
- `test_prompt_fix_with_hint()` — —
- `test_prompt_list_specs()` — —
- `test_prompt_response_has_required_fields()` — —
- `test_prompt_argv_always_starts_with_redeploy()` — —
- `test_prompt_uses_real_spec_paths()` — —
- `test_prompt_cli_schema_only()` — —
- `test_prompt_cli_dry_run_no_confirm()` — —
- `test_placeholder()` — —
- `test_import()` — —
- `has_dsi()` — —
- `kms_enabled()` — —
- `dsi_connected()` — —
- `dsi_physically_connected()` — —
- `dsi_enabled()` — —
- `backlight_on()` — —
- `errors()` — —
- `warnings()` — —
- `resolve_versions()` — —
- `to_infra_state()` — —
- `to_target_config()` — —
- `find_and_load()` — —
- `find_css()` — —
- `env()` — —
- `resolve_env()` — —
- `from_dotenv()` — —
- `apply_to_spec()` — —
- `last_deploy()` — —
- `is_reachable()` — —
- `record_deploy()` — —
- `has_errors()` — —
- `display_summary()` — —
- `save()` — —
- `load_for()` — —
- `service()` — —
- `upsert()` — —
- `remove()` — —
- `default_path()` — —
- `ok()` — —
- `add()` — —
- `passed()` — —
- `failed()` — —
- `warned()` — —
- `skipped()` — —
- `summary()` — —
- `to_dict()` — —
- `extras()` — —
- `collect()` — —
- `has_binary()` — —
- `has_path()` — —
- `port_listening()` — —
- `has_image()` — —
- `has_systemd_unit()` — —
- `apt_package()` — —
- `disk_free_gib()` — —
- `ts()` — —
- `host()` — —
- `app()` — —
- `from_strategy()` — —
- `to_strategy()` — —
- `elapsed_s()` — —
- `steps_total()` — —
- `steps_ok()` — —
- `steps_failed()` — —
- `pattern()` — —
- `version()` — —
- `dry_run()` — —
- `steps()` — —
- `error()` — —
- `record()` — —
- `tail()` — —
- `filter()` — —
- `clear()` — —
- `text()` — —
- `yaml()` — —
- `summary_line()` — —
- `ssh_user()` — —
- `ssh_ip()` — —
- `is_local()` — —
- `is_prod()` — —
- `has_tag()` — —
- `has_expectation()` — —
- `verify_expectations()` — —
- `get_device()` — —
- `prod_devices()` — —
- `from_config()` — —
- `prod()` — —


## Project Structure

📄 `.redeploy.state.migration-local-92efc860`
📄 `.redeploy.state.migration-local-e4114daa`
📄 `.redeploy.state.test-local-036bc2a0`
📄 `.redeploy.state.test-local-09b68243`
📄 `.redeploy.state.test-local-0a0a5446`
📄 `.redeploy.state.test-local-179edfed`
📄 `.redeploy.state.test-local-24cd498c`
📄 `.redeploy.state.test-local-35782b9c`
📄 `.redeploy.state.test-local-36935faf`
📄 `.redeploy.state.test-local-3ad44506`
📄 `.redeploy.state.test-local-46c5e2ce`
📄 `.redeploy.state.test-local-4d4cf12b`
📄 `.redeploy.state.test-local-50622a24`
📄 `.redeploy.state.test-local-563ceb24`
📄 `.redeploy.state.test-local-56cb0635`
📄 `.redeploy.state.test-local-5a1d7483`
📄 `.redeploy.state.test-local-6279ef2c`
📄 `.redeploy.state.test-local-63f620b6`
📄 `.redeploy.state.test-local-68ae2b20`
📄 `.redeploy.state.test-local-6bb4cec7`
📄 `.redeploy.state.test-local-7f5ddd97`
📄 `.redeploy.state.test-local-831fd1ab`
📄 `.redeploy.state.test-local-891787e9`
📄 `.redeploy.state.test-local-9c9d5826`
📄 `.redeploy.state.test-local-9cc88960`
📄 `.redeploy.state.test-local-a70e54ce`
📄 `.redeploy.state.test-local-a929f336`
📄 `.redeploy.state.test-local-ab92e6d9`
📄 `.redeploy.state.test-local-abe8802f`
📄 `.redeploy.state.test-local-ad30ec23`
📄 `.redeploy.state.test-local-be94eb0c`
📄 `.redeploy.state.test-local-c05a99a2`
📄 `.redeploy.state.test-local-c1ec6b35`
📄 `.redeploy.state.test-local-c9849e24`
📄 `.redeploy.state.test-local-d3c0fad8`
📄 `.redeploy.state.test-local-da199855`
📄 `.redeploy.state.test-local-db469906`
📄 `.redeploy.state.test-local-df0d6ff6`
📄 `.redeploy.state.test-local-e069dd9f`
📄 `.redeploy.state.test-local-e1009318`
📄 `.redeploy.state.test-local-e322f022`
📄 `.redeploy.state.test-local-e3a0f31a`
📄 `.redeploy.state.test-local-ea908429`
📄 `.redeploy.state.test-local-eac354f9`
📄 `.redeploy.state.test-local-ec3c5638`
📄 `.redeploy.state.test-local-ed7da478`
📄 `.redeploy.state.test-local-ee51c059`
📄 `.redeploy.state.test-local-efd3d620`
📄 `.redeploy.state.test-local-f868d117`
📄 `.redeploy.version`
📄 `CHANGELOG` (1 functions)
📄 `DOQL-INTEGRATION` (3 functions)
📄 `Makefile`
📄 `README` (1 functions)
📄 `REFACTORING` (9 functions, 6 classes)
📄 `REPAIR_LOG`
📄 `SUMD` (859 functions, 50 classes)
📄 `SUMR` (163 functions, 50 classes)
📄 `TODO` (11 functions, 1 classes)
📄 `code2llm_output.README`
📄 `code2llm_output.analysis.toon`
📄 `code2llm_output.context`
📄 `docs.README` (1 functions)
📄 `docs.dsl-migration` (35 functions)
📄 `docs.fleet` (3 functions)
📄 `docs.markpact-audit`
📄 `docs.markpact-implementation-plan` (1 functions)
📄 `docs.observe`
📄 `docs.parsers.README` (2 functions, 1 classes)
📄 `docs.patterns` (5 functions, 1 classes)
📄 `examples.README`
📄 `examples.hardware.enable-i2c-spi`
📄 `examples.hardware.official-dsi-7-inch`
📄 `examples.hardware.rpi5-waveshare-kiosk`
📄 `examples.hardware.waveshare-8-inch-dsi`
📄 `examples.md.01-rpi5-deploy.migration` (4 functions)
📄 `examples.md.01-vps-version-bump.README`
📄 `examples.md.01-vps-version-bump.migration`
📄 `examples.md.02-k3s-to-docker.README`
📄 `examples.md.02-k3s-to-docker.migration`
📄 `examples.md.02-multi-language.migration` (5 functions)
📄 `examples.md.03-all-actions.migration` (6 functions)
📄 `examples.md.03-docker-to-podman-quadlet.README`
📄 `examples.md.03-docker-to-podman-quadlet.migration`
📄 `examples.md.04-v3-state-reconciliation.migration`
📄 `examples.md.README`
📄 `examples.yaml.01-vps-version-bump.README`
📄 `examples.yaml.01-vps-version-bump.migration`
📄 `examples.yaml.02-k3s-to-docker.README`
📄 `examples.yaml.02-k3s-to-docker.migration`
📄 `examples.yaml.03-docker-to-podman-quadlet.README`
📄 `examples.yaml.03-docker-to-podman-quadlet.migration`
📄 `examples.yaml.04-rpi-kiosk.README`
📄 `examples.yaml.04-rpi-kiosk.migration`
📄 `examples.yaml.04-rpi-kiosk.migration-rpi5`
📄 `examples.yaml.04-rpi-kiosk.redeploy`
📄 `examples.yaml.05-iot-fleet-ota.README`
📄 `examples.yaml.05-iot-fleet-ota.migration`
📄 `examples.yaml.05-iot-fleet-ota.redeploy`
📄 `examples.yaml.06-local-dev.README`
📄 `examples.yaml.06-local-dev.migration`
📄 `examples.yaml.06-local-dev.redeploy`
📄 `examples.yaml.07-staging-to-prod.README`
📄 `examples.yaml.07-staging-to-prod.migration`
📄 `examples.yaml.07-staging-to-prod.redeploy`
📄 `examples.yaml.08-rollback.README`
📄 `examples.yaml.08-rollback.migration`
📄 `examples.yaml.09-fleet-yaml.README`
📄 `examples.yaml.09-fleet-yaml.fleet`
📄 `examples.yaml.09-fleet-yaml.redeploy`
📄 `examples.yaml.10-multienv.README`
📄 `examples.yaml.10-multienv.dev`
📄 `examples.yaml.10-multienv.prod`
📄 `examples.yaml.10-multienv.redeploy`
📄 `examples.yaml.10-multienv.staging`
📄 `examples.yaml.11-traefik-tls.README`
📄 `examples.yaml.11-traefik-tls.migration`
📄 `examples.yaml.11-traefik-tls.traefik.dynamic.tls`
📄 `examples.yaml.12-ci-pipeline.README`
📄 `examples.yaml.12-ci-pipeline.migration`
📄 `examples.yaml.12-ci-pipeline.redeploy`
📄 `examples.yaml.13-kiosk-appliance`
📄 `examples.yaml.13-multi-app-monorepo.README`
📄 `examples.yaml.13-multi-app-monorepo.fleet`
📄 `examples.yaml.13-multi-app-monorepo.migration`
📄 `examples.yaml.13-multi-app-monorepo.redeploy`
📄 `examples.yaml.14-blue-green`
📄 `examples.yaml.15-canary`
📄 `examples.yaml.16-auto-rollback`
📄 `goal`
📄 `project`
📄 `project.README`
📄 `project.analysis.toon`
📄 `project.calls`
📄 `project.calls.toon`
📄 `project.code2llm_output.README`
📄 `project.code2llm_output.analysis.toon`
📄 `project.code2llm_output.context`
📄 `project.context`
📄 `project.duplication.toon`
📄 `project.evolution.toon`
📄 `project.map.toon` (2241 functions)
📄 `project.project.toon`
📄 `project.prompt`
📄 `project.validation.toon`
📄 `pyproject`
📄 `pyqual`
📦 `redeploy`
📦 `redeploy.apply`
📄 `redeploy.apply.exceptions` (1 functions, 1 classes)
📄 `redeploy.apply.executor` (13 functions, 1 classes)
📄 `redeploy.apply.handlers` (20 functions)
📄 `redeploy.apply.progress` (11 functions, 1 classes)
📄 `redeploy.apply.rollback` (1 functions)
📄 `redeploy.apply.state` (13 functions, 1 classes)
📄 `redeploy.apply.state_apply` (9 functions, 4 classes)
📦 `redeploy.apply.utils`
📄 `redeploy.audit` (32 functions, 6 classes)
📦 `redeploy.blueprint`
📄 `redeploy.blueprint.extractor` (1 functions)
📦 `redeploy.blueprint.generators`
📄 `redeploy.blueprint.generators.docker_compose` (2 functions)
📄 `redeploy.blueprint.generators.migration` (1 functions)
📦 `redeploy.blueprint.sources`
📄 `redeploy.blueprint.sources.compose` (6 functions)
📄 `redeploy.blueprint.sources.hardware` (1 functions)
📄 `redeploy.blueprint.sources.infra` (2 functions)
📄 `redeploy.blueprint.sources.migration` (1 functions)
📦 `redeploy.cli` (3 functions)
📦 `redeploy.cli.commands`
📄 `redeploy.cli.commands.audit` (1 functions)
📄 `redeploy.cli.commands.blueprint` (8 functions)
📄 `redeploy.cli.commands.bump_fix` (12 functions)
📄 `redeploy.cli.commands.detect` (1 functions)
📄 `redeploy.cli.commands.device_map` (5 functions)
📄 `redeploy.cli.commands.device_map_renderers` (7 functions)
📄 `redeploy.cli.commands.devices` (4 functions)
📄 `redeploy.cli.commands.diagnose` (1 functions)
📄 `redeploy.cli.commands.diff` (1 functions)
📄 `redeploy.cli.commands.exec_` (6 functions)
📄 `redeploy.cli.commands.export` (6 functions)
📄 `redeploy.cli.commands.hardware` (11 functions)
📄 `redeploy.cli.commands.import_` (4 functions)
📄 `redeploy.cli.commands.init` (1 functions)
📄 `redeploy.cli.commands.inspect` (2 functions)
📄 `redeploy.cli.commands.mcp_cmd` (1 functions)
📄 `redeploy.cli.commands.patterns` (1 functions)
📄 `redeploy.cli.commands.plan_apply` (11 functions)
📄 `redeploy.cli.commands.plugin` (1 functions)
📄 `redeploy.cli.commands.probe` (1 functions)
📄 `redeploy.cli.commands.prompt_cmd` (4 functions)
📄 `redeploy.cli.commands.push` (1 functions)
📄 `redeploy.cli.commands.state` (4 functions)
📄 `redeploy.cli.commands.status` (1 functions)
📄 `redeploy.cli.commands.target` (1 functions)
📦 `redeploy.cli.commands.version`
📄 `redeploy.cli.commands.version.commands` (8 functions)
📄 `redeploy.cli.commands.version.helpers` (10 functions)
📄 `redeploy.cli.commands.version.monorepo` (5 functions)
📄 `redeploy.cli.commands.version.release` (6 functions)
📄 `redeploy.cli.commands.version.scanner` (18 functions)
📄 `redeploy.cli.commands.workflow` (3 functions)
📄 `redeploy.cli.core` (7 functions)
📄 `redeploy.cli.display` (25 functions)
📄 `redeploy.cli.query` (1 functions)
📦 `redeploy.config_apply`
📄 `redeploy.config_apply.applier` (3 functions)
📄 `redeploy.config_apply.loader` (1 functions)
📄 `redeploy.data_sync` (2 functions)
📦 `redeploy.detect`
📦 `redeploy.detect.builtin`
📄 `redeploy.detect.builtin.templates`
📄 `redeploy.detect.detector` (4 functions, 1 classes)
📄 `redeploy.detect.hardware` (2 functions)
📄 `redeploy.detect.hardware_rules` (3 functions)
📄 `redeploy.detect.probes` (9 functions)
📄 `redeploy.detect.remote`
📄 `redeploy.detect.templates` (13 functions, 6 classes)
📄 `redeploy.detect.workflow` (12 functions, 3 classes)
📄 `redeploy.discovery` (26 functions, 2 classes)
📦 `redeploy.dsl`
📄 `redeploy.dsl.loader` (12 functions, 3 classes)
📄 `redeploy.dsl.parser` (8 functions, 2 classes)
📦 `redeploy.dsl_python`
📄 `redeploy.dsl_python.context` (3 functions, 1 classes)
📄 `redeploy.dsl_python.decorators` (8 functions, 4 classes)
📄 `redeploy.dsl_python.docker_steps` (6 functions, 2 classes)
📄 `redeploy.dsl_python.exceptions` (4 functions, 6 classes)
📄 `redeploy.dsl_python.runner` (5 functions, 1 classes)
📄 `redeploy.dsl_python.steps` (7 functions)
📄 `redeploy.fleet` (23 functions, 6 classes)
📦 `redeploy.hardware`
📄 `redeploy.hardware.config_txt` (2 functions, 1 classes)
📦 `redeploy.hardware.data`
📄 `redeploy.hardware.data.hyperpixel`
📄 `redeploy.hardware.data.official`
📄 `redeploy.hardware.data.waveshare`
📄 `redeploy.hardware.fixes` (6 functions)
📦 `redeploy.hardware.kiosk`
📄 `redeploy.hardware.kiosk.autostart` (3 functions, 1 classes)
📄 `redeploy.hardware.kiosk.browsers` (1 functions, 1 classes)
📄 `redeploy.hardware.kiosk.compositors` (1 functions, 1 classes)
📄 `redeploy.hardware.kiosk.output_profiles` (2 functions, 1 classes)
📄 `redeploy.hardware.panels` (5 functions, 1 classes)
📄 `redeploy.hardware.raspi_config` (1 functions)
📄 `redeploy.heal` (10 functions, 1 classes)
📦 `redeploy.iac`
📄 `redeploy.iac.base` (13 functions, 7 classes)
📄 `redeploy.iac.config_hints` (15 functions, 1 classes)
📄 `redeploy.iac.docker_compose` (11 functions, 1 classes)
📦 `redeploy.iac.parsers`
📄 `redeploy.iac.parsers.compose` (13 functions, 1 classes)
📄 `redeploy.iac.registry` (4 functions)
📦 `redeploy.integrations`
📄 `redeploy.integrations.op3_bridge` (5 functions)
📦 `redeploy.markpact`
📄 `redeploy.markpact.compiler` (6 functions, 1 classes)
📄 `redeploy.markpact.models` (2 classes)
📄 `redeploy.markpact.parser` (9 functions, 1 classes)
📄 `redeploy.mcp_server` (14 functions)
📄 `redeploy.models` (29 functions, 33 classes)
📄 `redeploy.observe` (14 functions, 3 classes)
📄 `redeploy.parse` (10 functions)
📄 `redeploy.patterns` (11 functions, 4 classes)
📦 `redeploy.plan`
📄 `redeploy.plan.planner` (21 functions, 1 classes)
📦 `redeploy.plugins` (10 functions, 2 classes)
📦 `redeploy.plugins.builtin`
📄 `redeploy.plugins.builtin.browser_reload` (3 functions)
📄 `redeploy.plugins.builtin.hardware_diagnostic` (11 functions, 1 classes)
📄 `redeploy.plugins.builtin.notify` (7 functions)
📄 `redeploy.plugins.builtin.process_control` (3 functions)
📄 `redeploy.plugins.builtin.systemd_reload` (2 functions)
📄 `redeploy.schema` (5 functions)
📄 `redeploy.spec_loader` (1 functions, 2 classes)
📄 `redeploy.ssh` (17 functions, 4 classes)
📦 `redeploy.steps` (4 functions, 1 classes)
📄 `redeploy.steps.builtins` (1 functions)
📄 `redeploy.steps.kiosk`
📄 `redeploy.templates.process_control_template`
📄 `redeploy.verify` (7 functions, 1 classes)
📦 `redeploy.version` (4 functions)
📄 `redeploy.version.bump` (6 functions)
📄 `redeploy.version.changelog` (15 functions, 1 classes)
📄 `redeploy.version.commits` (3 functions, 2 classes)
📄 `redeploy.version.diff` (3 functions, 1 classes)
📄 `redeploy.version.git_integration` (13 functions, 2 classes)
📄 `redeploy.version.git_transaction` (5 functions, 2 classes)
📄 `redeploy.version.manifest` (10 functions, 8 classes)
📦 `redeploy.version.sources` (5 functions, 1 classes)
📄 `redeploy.version.sources.base` (5 functions, 1 classes)
📄 `redeploy.version.sources.json_` (3 functions, 1 classes)
📄 `redeploy.version.sources.plain` (2 functions, 1 classes)
📄 `redeploy.version.sources.regex` (2 functions, 1 classes)
📄 `redeploy.version.sources.toml_` (3 functions, 1 classes)
📄 `redeploy.version.sources.yaml_` (3 functions, 1 classes)
📄 `redeploy.version.transaction` (6 functions, 2 classes)
📄 `reports.hardware-108`
📄 `reports.hardware-109`
📄 `scripts.quality_gate`
📄 `sumd`
📄 `tree`

## Requirements

- Python >= >=3.11
- pydantic >=2.0- pyyaml >=6.0- markdown-it-py >=3.0- click >=8.0- loguru >=0.7- paramiko >=3.0- httpx >=0.25- rich >=13.0- jmespath >=1.0- goal >=2.1.0- costs >=0.1.20- pfix >=0.1.60

## Contributing

**Contributors:**
- Tom Softreck <tom@sapletta.com>

We welcome contributions! Open an issue or pull request to get started.
### Development Setup

```bash
# Clone the repository
git clone https://github.com/maskservice/redeploy
cd redeploy

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest
```

## Documentation

- 💡 [Examples](./examples) — Usage examples and code samples

### Generated Files

| Output | Description | Link |
|--------|-------------|------|
| `README.md` | Project overview (this file) | — |
| `examples` | Usage examples and code samples | [View](./examples) |

<!-- code2docs:end -->
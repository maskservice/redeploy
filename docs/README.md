<!-- code2docs:start --># redeploy

![version](https://img.shields.io/badge/version-0.1.0-blue) ![python](https://img.shields.io/badge/python-%3E%3D3.11-blue) ![coverage](https://img.shields.io/badge/coverage-unknown-lightgrey) ![functions](https://img.shields.io/badge/functions-716-green)
> **716** functions | **139** classes | **124** files | CC̄ = 5.1

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
├── project
├── tree
    ├── version/
    ├── data_sync
    ├── detect/
        ├── remote
    ├── spec_loader
    ├── observe
        ├── hardware
    ├── steps
        ├── builtin/
    ├── parse
    ├── cli/
    ├── verify
            ├── target
        ├── probes
        ├── core
            ├── state
            ├── inspect
├── redeploy/
            ├── devices
            ├── status
            ├── export
            ├── plugin
            ├── init
            ├── probe
            ├── blueprint
    ├── ssh
        ├── commands/
        ├── display
            ├── exec_
    ├── patterns
            ├── detect
            ├── diff
            ├── import_
            ├── hardware
            ├── audit
            ├── workflow
            ├── diagnose
            ├── patterns
            ├── version/
                ├── monorepo
            ├── plan_apply
            ├── device_map
        ├── builtin/
                ├── release
            ├── browser_reload
                ├── helpers
                ├── commands
        ├── exceptions
        ├── steps
    ├── dsl_python/
        ├── runner
                ├── scanner
            ├── process_control
            ├── notify
        ├── config_txt
    ├── hardware/
    ├── plugins/
        ├── fixes
        ├── data/
        ├── raspi_config
            ├── official
            ├── waveshare
    ├── markpact/
            ├── hyperpixel
        ├── parser
        ├── detector
            ├── systemd_reload
        ├── exceptions
        ├── compiler
    ├── apply/
        ├── progress
    ├── audit
        ├── rollback
        ├── utils/
        ├── handlers
        ├── bump
        ├── executor
        ├── changelog
    ├── discovery
        ├── models
        ├── git_integration
        ├── workflow
        ├── templates
            ├── base
            ├── regex
            ├── toml_
        ├── sources/
            ├── yaml_
            ├── plain
        ├── hardware_rules
    ├── plan/
    ├── blueprint/
            ├── json_
            ├── docker_compose
        ├── generators/
            ├── migration
        ├── planner
            ├── hardware_diagnostic
    ├── dsl/
        ├── extractor
        ├── parser
        ├── registry
    ├── iac/
        ├── parsers/
        ├── docker_compose
            ├── compose
        ├── loader
        ├── docker_steps
        ├── transaction
        ├── panels
        ├── base
        ├── context
        ├── git_transaction
        ├── diff
        ├── decorators
        ├── commits
    ├── models
    ├── fleet
        ├── manifest
        ├── state
```

## API Overview

### Classes

- **`SpecLoaderError`** — Base error raised when a deployment spec cannot be loaded.
- **`UnsupportedSpecFormatError`** — Raised when the spec file uses an unsupported format.
- **`AuditEntry`** — Single audit log entry — immutable snapshot of one deployment.
- **`DeployAuditLog`** — Persistent audit log — newline-delimited JSON at ``path``.
- **`DeployReport`** — Human-readable post-deploy report from an AuditEntry.
- **`StepLibrary`** — Registry of pre-defined named MigrationSteps.
- **`VerifyContext`** — Accumulates check results during verification.
- **`SshResult`** — —
- **`SshClient`** — Execute commands on a remote host via SSH (or locally).
- **`RemoteProbe`** — Thin wrapper kept for redeploy.detect compatibility.
- **`RemoteExecutor`** — Thin wrapper kept for deploy.core compatibility.
- **`DeployPattern`** — Base class for all deploy patterns.
- **`BlueGreenPattern`** — Zero-downtime blue/green deploy via Traefik (or any label-based proxy).
- **`CanaryPattern`** — Gradual canary rollout: deploy new version, scale up in stages.
- **`RollbackOnFailurePattern`** — Capture pre-deploy image tag, roll back automatically on failure.
- **`DSLException`** — Base exception for DSL errors.
- **`StepError`** — Raised when a step fails.
- **`TimeoutError`** — Raised when a step times out.
- **`VerificationError`** — Raised when verification fails.
- **`ConnectionError`** — Raised when SSH/connection fails.
- **`RollbackError`** — Raised when rollback fails.
- **`PythonMigrationRunner`** — Runner for Python-based migrations.
- **`ConfigEdit`** — Result of a config.txt edit operation.
- **`PluginContext`** — Passed to every plugin handler.
- **`PluginRegistry`** — Central registry mapping plugin_type strings to handler callables.
- **`MarkpactParseError`** — Raised when a markdown markpact document cannot be parsed.
- **`Detector`** — Probe infrastructure and produce InfraState.
- **`StepError`** — Exception raised when a migration step fails.
- **`MarkpactCompileError`** — Raised when a markpact document cannot be compiled to MigrationSpec.
- **`ProgressEmitter`** — Emits YAML-formatted progress events to a stream (default: stdout).
- **`AuditCheck`** — Outcome of a single audit probe.
- **`AuditReport`** — —
- **`Auditor`** — Compare a MigrationSpec's expectations against a live target host.
- **`Executor`** — Execute MigrationPlan steps on a remote host.
- **`ChangelogManager`** — Manage CHANGELOG.md in keep-a-changelog format.
- **`DiscoveredHost`** — —
- **`ProbeResult`** — Full autonomous probe result for a single host.
- **`MarkpactBlock`** — —
- **`MarkpactDocument`** — —
- **`GitIntegrationError`** — Git operation failed.
- **`GitIntegration`** — Git operations for version management.
- **`HostDetectionResult`** — Full detection result for a single host.
- **`WorkflowResult`** — Aggregated result across all probed hosts.
- **`DetectionWorkflow`** — Multi-host detection workflow with template scoring.
- **`Condition`** — A single scoreable condition.
- **`DetectionTemplate`** — Named template for a device+environment+strategy combination.
- **`TemplateMatch`** — Scored template match.
- **`DetectionResult`** — Full result of template-based detection.
- **`TemplateEngine`** — Score all templates against a context and return ranked matches.
- **`BaseAdapter`** — Base class for source adapters with common utilities.
- **`RegexAdapter`** — Read/write version using regex pattern with capture group.
- **`TomlAdapter`** — Read/write version from TOML files using tomllib/tomli.
- **`SourceAdapter`** — Protocol for version source adapters.
- **`YamlAdapter`** — Read/write version from YAML files.
- **`PlainAdapter`** — Read/write version from plain text file.
- **`DiagnosticRule`** — A single hardware diagnostic rule.
- **`JsonAdapter`** — Read/write version from JSON files.
- **`Planner`** — Generate a MigrationPlan from detected infra + desired target.
- **`HardwareInfo`** — Hardware diagnostic information.
- **`DSLNode`** — One parsed block from the CSS-like file.
- **`RedeployDSLParser`** — Parse a ``redeploy.css`` or ``redeploy.less`` file into a list of DSLNode objects.
- **`DockerComposeParser`** — Parser for docker-compose.yml / compose.yaml files.
- **`DockerComposeParser`** — Parser for Docker Compose files (v2 + v3 schema, Compose Spec).
- **`WorkflowStep`** — —
- **`WorkflowDef`** — Named deployment workflow parsed from ``workflow[name="…"] { … }``.
- **`LoadResult`** — Full result of loading a ``redeploy.css`` file.
- **`DockerComposeResult`** — Result of docker compose command.
- **`DockerDSL`** — Docker-related DSL actions.
- **`StagingResult`** — Result of staging one source.
- **`VersionBumpTransaction`** — Atomic transaction for bumping version across multiple sources.
- **`PanelDefinition`** — Definition of a Raspberry Pi display panel.
- **`PortInfo`** — A published / exposed port mapping.
- **`VolumeInfo`** — A volume or bind-mount.
- **`ServiceInfo`** — One logical service / container / pod / deployment.
- **`ConversionWarning`** — A warning emitted by a parser or converter about lossy / uncertain data.
- **`ParsedSpec`** — Common intermediate representation from any IaC/CI-CD parser.
- **`Parser`** — Protocol every format-specific parser must satisfy.
- **`ParserRegistry`** — Dispatch file → registered parser.
- **`StepContext`** — Tracks the execution of a single step.
- **`GitTransactionResult`** — Result of full version bump transaction with git.
- **`GitVersionBumpTransaction`** — Version bump transaction with Git integration.
- **`VersionDiff`** — Version comparison result.
- **`MigrationMeta`** — Metadata for a migration.
- **`MigrationRegistry`** — Global registry of migration functions.
- **`StepManager`** — Manages step execution and tracking.
- **`step`** — Context manager for a deployment step.
- **`ConventionalCommit`** — Parsed conventional commit.
- **`BumpAnalysis`** — Result of analyzing commits for bump decision.
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
- **`DeviceArch`** — —
- **`Stage`** — —
- **`DeviceExpectation`** — Declarative assertions about required infrastructure on a device.
- **`FleetDevice`** — Generic device descriptor — superset of ``deploy``'s DeviceConfig.
- **`FleetConfig`** — Top-level fleet manifest — list of devices with stage / tag organisation.
- **`Fleet`** — Unified first-class fleet — wraps FleetConfig and/or DeviceRegistry.
- **`SourceConfig`** — Single source of version truth (one file).
- **`GitConfig`** — Git integration settings.
- **`ChangelogConfig`** — Changelog generation settings.
- **`CommitRules`** — Conventional commits → bump type mapping.
- **`CommitsConfig`** — Conventional commits analysis settings.
- **`PackageConfig`** — Single package in monorepo (for policy=independent).
- **`Constraint`** — Cross-package version constraint.
- **`VersionManifest`** — Root manifest model for .redeploy/version.yaml.
- **`ResumeState`** — Checkpoint for a single MigrationPlan execution.

### Functions

- `collect_sqlite_counts(app_root, db_specs)` — Collect row counts for the given SQLite tables under *app_root*.
- `rsync_timeout_for_path(path, minimum, base, per_mb)` — Compute a conservative rsync timeout based on file size (seconds).
- `load_migration_spec(path)` — Load a deployment spec from disk.
- `probe_board(p)` — Return (board_model, kernel_version).
- `probe_config_txt(p)` — Read /boot/firmware/config.txt (RPi5) or /boot/config.txt.
- `probe_drm_outputs(p)` — Enumerate /sys/class/drm/ connectors.
- `probe_wlr_randr(p)` — Run wlr-randr via the user's Wayland socket and parse output.
- `probe_backlights(p)` — Read all /sys/class/backlight/* devices.
- `probe_framebuffers(p)` — —
- `probe_i2c_buses(p)` — List I2C buses. Scan if i2cdetect is available.
- `probe_dsi_dmesg(p)` — Collect relevant DSI/panel/backlight lines from dmesg.
- `probe_hardware(p)` — Probe hardware state of the remote host and return HardwareInfo with diagnostics.
- `parse_docker_ps(output)` — Parse 'docker ps --format "{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}|{{.State}}"' output.
- `parse_container_line(line)` — Parse a single NAME|STATUS|IMAGE pipe-delimited container line.
- `parse_system_info(output)` — Parse KEY:VALUE system info lines (HOSTNAME, UPTIME, DISK, MEM, LOAD) into a dict.
- `parse_diagnostics(output)` — Parse multi-section SSH diagnostics output into structured dict.
- `parse_health_info(output)` — Parse health-check SSH output (HOSTNAME, UPTIME, HEALTH, DISK, LOAD) into a dict.
- `cli(ctx, verbose)` — redeploy — Infrastructure migration toolkit: detect → plan → apply
- `verify_data_integrity(ctx, local_counts, remote_counts)` — Compare local vs remote SQLite row counts and record results in *ctx*.
- `target(device_id, spec_file, dry_run, plan_only)` — Deploy a spec to a specific registered device.
- `probe_runtime(p)` — Detect installed runtimes: docker, k3s, podman, systemd.
- `probe_ports(p)` — Detect listening ports and which process owns them.
- `probe_iptables_dnat(p, ports)` — Find iptables DNAT rules stealing specific ports (returns [(port, target_ip)]).
- `probe_docker_services(p)` — List running Docker containers.
- `probe_k3s_services(p, namespaces)` — List running k3s pods.
- `probe_systemd_services(p, app)` — List app-related systemd units (also catches kiosk/chromium/openbox).
- `probe_health(host, app, domain)` — HTTP health checks against known endpoints.
- `detect_conflicts(ports, iptables_dnat, runtime, docker_services)` — Identify conflicts: port stealing, duplicate services, etc.
- `detect_strategy(runtime, docker_services, k3s_services, systemd_services)` — Infer the current deployment strategy from detected services.
- `load_spec_or_exit(console, path)` — Load a migration spec or exit with error.
- `find_manifest_path()` — Find redeploy.yaml manifest in current or parent directories.
- `resolve_device(console, device_id)` — Resolve device from registry or auto-probe.
- `load_spec_with_manifest(console, spec_file, dev)` — Load spec and apply manifest/device overlays.
- `overlay_device_onto_spec(spec, dev, console)` — Overlay device values onto spec target configuration.
- `run_detect_for_spec(console, spec, do_detect)` — Run detect if requested and return planner.
- `run_detect_workflow(console, hosts, manifest, app)` — Run DetectionWorkflow and print rich report.
- `state_cmd(ctx, action, spec_file, host)` — Inspect or clear resume checkpoints.
- `inspect(ctx, css_file)` — Show parsed content of redeploy.css — environments, templates, workflows.
- `devices(tag, strategy, rpi, reachable)` — List known devices from ~/.config/redeploy/devices.yaml.
- `scan(subnet, ssh_users, ssh_port, ping)` — Discover SSH-accessible devices on the local network.
- `device_add(host, device_id, name, tags)` — Add or update a device in the registry.
- `device_rm(device_id)` — Remove a device from the registry.
- `status(spec_file)` — Show current project manifest and spec summary.
- `export_cmd(ctx, fmt, output, src_file)` — Convert between redeploy.css and redeploy.yaml formats.
- `plugin_cmd(ctx, subcommand, name)` — List or inspect registered redeploy plugins.
- `init(host, app, domain, strategy)` — Scaffold migration.yaml + redeploy.yaml for this project.
- `probe(hosts, subnet, users, ssh_port)` — Autonomously probe one or more hosts — detect SSH credentials, strategy, app.
- `blueprint_cmd()` — Extract, generate and apply DeviceBlueprints (portable deploy recipes).
- `capture(host, name, compose_files, migration_file)` — Probe HOST and extract a DeviceBlueprint from all available sources.
- `twin(blueprint_file, out_path, platform, port_offset)` — Generate a docker-compose.twin.yml from BLUEPRINT_FILE for local testing.
- `deploy(blueprint_file, target_host, out_path, remote_dir)` — Generate (and optionally run) a migration.yaml for TARGET_HOST from BLUEPRINT_FILE.
- `show(blueprint_file, fmt)` — Display a saved DeviceBlueprint.
- `list_blueprints()` — List all saved DeviceBlueprints.
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
- `exec_cmd(ctx, ref, host, markdown_file)` — Execute a script from a markdown codeblock by reference.
- `exec_multi_cmd(ctx, refs, host, markdown_file)` — Execute multiple scripts from markdown codeblocks by reference.
- `get_pattern(name)` — Return pattern class by name, or None if not found.
- `list_patterns()` — Return all registered pattern names.
- `detect(ctx, host, app, domain)` — Probe infrastructure and produce infra.yaml.
- `diff(ci_file, host, from_src, to_src)` — Compare IaC file vs live host (drift detection).  [Phase 3 — coming soon]
- `import_cmd(source, output, target_host, target_strategy)` — Parse an IaC/CI-CD file and produce a migration.yaml scaffold.
- `hardware(host, output_fmt, show_fix, apply_fix_component)` — Probe and diagnose hardware on a remote host.
- `audit(last, host, app, only_failed)` — Show deploy audit log from ~/.config/redeploy/audit.jsonl.
- `workflow_cmd(ctx, name, css_file, dry_run)` — Run a named workflow from redeploy.css.
- `diagnose(ctx, spec, host, ssh_key)` — Compare a migration spec against the live target host.
- `patterns(name)` — List available deploy patterns or show detail for one.
- `plan(ctx, infra, target, strategy)` — Generate migration-plan.yaml from infra.yaml + target config.
- `apply(ctx, plan_file, dry_run, step)` — Execute a migration plan.
- `migrate(ctx, host, app, domain)` — Full pipeline: detect → plan → apply.
- `run(ctx, spec_file, dry_run, plan_only)` — Execute migration from a single YAML spec (source + target in one file).
- `device_map_cmd(host, name, tags, save)` — Generate a full standardized device snapshot (hardware + infra + diagnostics).
- `browser_reload(ctx)` — —
- `version_cmd()` — Declarative version management: bump, verify, diff.
- `version_current(manifest, package_name, all_packages)` — Show current version from manifest.
- `version_list(manifest, package_name, all_packages)` — List all version sources and their values.
- `version_verify(manifest, package_name, all_packages)` — Verify all sources match manifest version.
- `version_bump(type, manifest, package, all_packages)` — Bump version across all sources atomically.
- `version_set(version, manifest_path_str, package_name, all_packages)` — Set an explicit version across all manifest sources.
- `version_init(scan, review, interactive, excluded_paths)` — Initialize .redeploy/version.yaml manifest.
- `version_diff(manifest, package_name, all_packages, spec)` — Compare manifest version vs spec vs live.
- `ssh(host, command, timeout, check)` — Execute a command on a remote host via SSH.
- `ssh_available(host, timeout, interval)` — Wait for SSH to become available on a host.
- `rsync(src, dst, exclude, delete)` — Synchronize files using rsync.
- `scp(src, dst, timeout)` — Copy files using SCP.
- `wait(seconds, message)` — Wait for specified seconds.
- `http_expect(url, expect, timeout, retries)` — Verify HTTP endpoint returns expected content.
- `version_check(manifest_path, expect, host, url)` — Verify deployed version matches expectation.
- `main()` — CLI entry point for running Python migrations.
- `process_control(ctx)` — Kill processes on specified ports.
- `notify(ctx)` — —
- `ensure_line(content, line)` — Ensure `line` is present in [section] of config.txt.
- `ensure_lines(content, lines)` — Apply multiple lines in one pass — important because each `ensure_line` re-parses.
- `register_plugin(name)` — Decorator shortcut: @register_plugin('browser_reload').
- `load_user_plugins()` — Load user plugins from project-local and user-global directories.
- `fix_dsi_not_enabled(hw, panel)` — Generate steps to configure DSI panel + reboot + verify.
- `fix_enable_i2c(hw, panel)` — Enable I2C interface via raspi-config.
- `fix_enable_spi(hw, panel)` — Enable SPI interface via raspi-config.
- `generate_fix_plan(hw, component, panel)` — From a component name or rule name, return fix steps.
- `build_raspi_config_command(interface, state)` — Build a raspi-config nonint command.
- `parse_markpact_file(path)` — —
- `parse_markpact_text(text)` — —
- `parse_markpact_file_with_refs(path)` — Parse markpact file and extract all referenced scripts.
- `extract_script_by_ref(text, ref_id, language)` — Extract script from codeblock marked with markpact:ref <ref_id>.
- `extract_script_from_markdown(text, section_id, language)` — Extract script content from a markdown code block by section heading.
- `systemd_reload(ctx)` — —
- `compile_markpact_document(document)` — —
- `compile_markpact_document_to_data(document)` — —
- `audit_spec(spec_path)` — Convenience: load spec from file and run an audit.
- `rollback_steps(completed_steps, probe, state)` — Rollback completed steps in reverse order.
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
- `bump_version(manifest, bump_type, new_version)` — Bump version across all sources atomically.
- `verify_sources(manifest)` — Verify all sources are in sync with manifest.version.
- `bump_version_with_git(manifest, bump_type, repo_path, new_version)` — Bump version with optional git integration.
- `bump_package(manifest, package_name, bump_type, new_version)` — Bump version of a single package in a monorepo manifest.
- `bump_all_packages(manifest, bump_type)` — Bump all packages in a monorepo manifest independently.
- `get_commits_since_tag(repo_path, tag)` — Get commit messages since tag.
- `discover(subnet, ssh_users, ssh_port, ping)` — Discover SSH-accessible hosts in the local network.
- `update_registry(hosts, registry, save)` — Merge discovered hosts into DeviceRegistry and optionally save.
- `auto_probe(ip_or_host, users, port, timeout)` — Autonomously probe a host — try all available SSH keys and users.
- `read_local_version(workspace_root, app)` — Read VERSION file from local workspace.
- `read_remote_version(remote, remote_dir, app)` — Read VERSION file from remote device via SSH.
- `check_version(local, remote)` — Compare local vs remote version string. Returns (match, detail_line).
- `check_version_http(base_url, expected_version, timeout, endpoint)` — Call *endpoint* on a running service. Returns (ok, summary_line, payload).
- `build_context(state, probe, manifest)` — Flatten InfraState + ProbeResult into a flat dict for condition evaluation.
- `get_adapter(format_name)` — Get adapter by format name.
- `register_adapter(format_name, adapter)` — Register custom adapter.
- `analyze(hw)` — Run all diagnostic rules against *hw* and return findings.
- `generate_twin(blueprint)` — Render a docker-compose YAML string for a local digital-twin.
- `generate_migration(blueprint)` — Render a migration.yaml for deploying blueprint to *target_host*.
- `hardware_diagnostic(ctx)` — Perform hardware diagnostics and provide recommendations.
- `extract_blueprint()` — Build a DeviceBlueprint by reconciling all available sources.
- `parse_file(path)` — Parse a single file with auto-detected format.
- `parse_dir(root, recursive, skip_errors)` — Parse all recognised files under *root*.
- `load_css(path)` — Parse ``redeploy.css`` and return manifest + templates + workflows.
- `load_css_text(text, source_file)` — Parse CSS text directly (for tests).
- `manifest_to_css(manifest, app)` — Render a ProjectManifest back to ``redeploy.css`` format.
- `templates_to_css(templates)` — Render DetectionTemplate list to CSS block.
- `register(panel)` — Register a panel in the registry.
- `get(panel_id)` — Get a panel by ID.
- `all_panels()` — Get all registered panels sorted by vendor and ID.
- `infer_from_hardware(hw)` — Heuristic panel detection from HardwareInfo.
- `diff_manifest_vs_spec(manifest, spec_version)` — Compare manifest version vs migration.yaml target.version.
- `diff_manifest_vs_live(manifest, live_version)` — Compare manifest version vs live deployed version.
- `format_diff_report(diffs, manifest_version)` — Format diff results as human-readable report.
- `migration(name, version, description, author)` — Decorator to mark a function as a migration.
- `parse_conventional(message)` — Parse a conventional commit message.
- `analyze_commits(since_tag, repo_path, config)` — Analyze commits since tag to determine bump type.
- `format_analysis_report(analysis)` — Format bump analysis as human-readable report.
- `state_key(spec_path, host)` — Stable, filesystem-safe identifier for one (spec, host) checkpoint.
- `default_state_path(spec_path, host, base_dir)` — —
- `filter_resumable(step_ids, state)` — Return ids that are NOT yet completed (preserves order).


## Project Structure

📄 `project`
📦 `redeploy`
📦 `redeploy.apply`
📄 `redeploy.apply.exceptions` (1 functions, 1 classes)
📄 `redeploy.apply.executor` (13 functions, 1 classes)
📄 `redeploy.apply.handlers` (17 functions)
📄 `redeploy.apply.progress` (11 functions, 1 classes)
📄 `redeploy.apply.rollback` (1 functions)
📄 `redeploy.apply.state` (13 functions, 1 classes)
📦 `redeploy.apply.utils`
📄 `redeploy.audit` (32 functions, 6 classes)
📦 `redeploy.blueprint`
📄 `redeploy.blueprint.extractor` (8 functions)
📦 `redeploy.blueprint.generators`
📄 `redeploy.blueprint.generators.docker_compose` (2 functions)
📄 `redeploy.blueprint.generators.migration` (1 functions)
📦 `redeploy.cli` (3 functions)
📦 `redeploy.cli.commands`
📄 `redeploy.cli.commands.audit` (1 functions)
📄 `redeploy.cli.commands.blueprint` (7 functions)
📄 `redeploy.cli.commands.detect` (1 functions)
📄 `redeploy.cli.commands.device_map` (4 functions)
📄 `redeploy.cli.commands.devices` (4 functions)
📄 `redeploy.cli.commands.diagnose` (1 functions)
📄 `redeploy.cli.commands.diff` (1 functions)
📄 `redeploy.cli.commands.exec_` (6 functions)
📄 `redeploy.cli.commands.export` (6 functions)
📄 `redeploy.cli.commands.hardware` (9 functions)
📄 `redeploy.cli.commands.import_` (4 functions)
📄 `redeploy.cli.commands.init` (1 functions)
📄 `redeploy.cli.commands.inspect` (2 functions)
📄 `redeploy.cli.commands.patterns` (1 functions)
📄 `redeploy.cli.commands.plan_apply` (8 functions)
📄 `redeploy.cli.commands.plugin` (1 functions)
📄 `redeploy.cli.commands.probe` (1 functions)
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
📄 `redeploy.data_sync` (2 functions)
📦 `redeploy.detect`
📦 `redeploy.detect.builtin`
📄 `redeploy.detect.detector` (4 functions, 1 classes)
📄 `redeploy.detect.hardware` (11 functions)
📄 `redeploy.detect.hardware_rules` (10 functions, 1 classes)
📄 `redeploy.detect.probes` (9 functions)
📄 `redeploy.detect.remote`
📄 `redeploy.detect.templates` (11 functions, 5 classes)
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
📄 `redeploy.hardware.panels` (5 functions, 1 classes)
📄 `redeploy.hardware.raspi_config` (1 functions)
📦 `redeploy.iac`
📄 `redeploy.iac.base` (13 functions, 7 classes)
📄 `redeploy.iac.docker_compose` (11 functions, 1 classes)
📦 `redeploy.iac.parsers`
📄 `redeploy.iac.parsers.compose` (13 functions, 1 classes)
📄 `redeploy.iac.registry` (2 functions)
📦 `redeploy.markpact`
📄 `redeploy.markpact.compiler` (6 functions, 1 classes)
📄 `redeploy.markpact.models` (2 classes)
📄 `redeploy.markpact.parser` (9 functions, 1 classes)
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
📄 `redeploy.spec_loader` (1 functions, 2 classes)
📄 `redeploy.ssh` (17 functions, 4 classes)
📄 `redeploy.steps` (5 functions, 1 classes)
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
📄 `tree`

## Requirements

- Python >= >=3.11
- pydantic >=2.0- pyyaml >=6.0- markdown-it-py >=3.0- click >=8.0- loguru >=0.7- paramiko >=3.0- httpx >=0.25- rich >=13.0- goal >=2.1.0- costs >=0.1.20- pfix >=0.1.60

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
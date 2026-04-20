<!-- code2docs:start --># redeploy

![version](https://img.shields.io/badge/version-0.1.0-blue) ![python](https://img.shields.io/badge/python-%3E%3D3.11-blue) ![coverage](https://img.shields.io/badge/coverage-unknown-lightgrey) ![functions](https://img.shields.io/badge/functions-466-green)
> **466** functions | **109** classes | **62** files | CC̄ = 5.3

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
├── tree
├── project
        ├── remote
    ├── observe
    ├── version/
    ├── detect/
        ├── probes
    ├── patterns
        ├── builtin/
    ├── plugins/
├── redeploy/
            ├── systemd_reload
        ├── exceptions
        ├── steps
    ├── verify
    ├── dsl_python/
        ├── runner
    ├── data_sync
    ├── apply/
            ├── notify
    ├── cli
        ├── bump
            ├── browser_reload
        ├── changelog
        ├── executor
    ├── steps
    ├── parse
        ├── detector
        ├── git_integration
            ├── base
        ├── templates
            ├── regex
            ├── toml_
            ├── yaml_
            ├── plain
    ├── plan/
            ├── json_
        ├── planner
    ├── ssh
    ├── dsl/
        ├── loader
    ├── discovery
        ├── registry
    ├── iac/
        ├── parsers/
        ├── docker_compose
        ├── base
        ├── parser
            ├── compose
        ├── workflow
        ├── git_transaction
        ├── decorators
        ├── commits
        ├── docker_steps
        ├── transaction
        ├── diff
        ├── context
        ├── sources/
        ├── manifest
    ├── fleet
    ├── models
```

## API Overview

### Classes

- **`AuditEntry`** — Single audit log entry — immutable snapshot of one deployment.
- **`DeployAuditLog`** — Persistent audit log — newline-delimited JSON at ``path``.
- **`DeployReport`** — Human-readable post-deploy report from an AuditEntry.
- **`DeployPattern`** — Base class for all deploy patterns.
- **`BlueGreenPattern`** — Zero-downtime blue/green deploy via Traefik (or any label-based proxy).
- **`CanaryPattern`** — Gradual canary rollout: deploy new version, scale up in stages.
- **`RollbackOnFailurePattern`** — Capture pre-deploy image tag, roll back automatically on failure.
- **`PluginContext`** — Passed to every plugin handler.
- **`PluginRegistry`** — Central registry mapping plugin_type strings to handler callables.
- **`DSLException`** — Base exception for DSL errors.
- **`StepError`** — Raised when a step fails.
- **`TimeoutError`** — Raised when a step times out.
- **`VerificationError`** — Raised when verification fails.
- **`ConnectionError`** — Raised when SSH/connection fails.
- **`RollbackError`** — Raised when rollback fails.
- **`VerifyContext`** — Accumulates check results during verification.
- **`PythonMigrationRunner`** — Runner for Python-based migrations.
- **`ChangelogManager`** — Manage CHANGELOG.md in keep-a-changelog format.
- **`ProgressEmitter`** — Emits YAML-formatted progress events to a stream (default: stdout).
- **`StepError`** — —
- **`Executor`** — Execute MigrationPlan steps on a remote host.
- **`StepLibrary`** — Registry of pre-defined named MigrationSteps.
- **`Detector`** — Probe infrastructure and produce InfraState.
- **`GitIntegrationError`** — Git operation failed.
- **`GitIntegration`** — Git operations for version management.
- **`BaseAdapter`** — Base class for source adapters with common utilities.
- **`Condition`** — A single scoreable condition.
- **`DetectionTemplate`** — Named template for a device+environment+strategy combination.
- **`TemplateMatch`** — Scored template match.
- **`DetectionResult`** — Full result of template-based detection.
- **`TemplateEngine`** — Score all templates against a context and return ranked matches.
- **`RegexAdapter`** — Read/write version using regex pattern with capture group.
- **`TomlAdapter`** — Read/write version from TOML files using tomllib/tomli.
- **`YamlAdapter`** — Read/write version from YAML files.
- **`PlainAdapter`** — Read/write version from plain text file.
- **`JsonAdapter`** — Read/write version from JSON files.
- **`Planner`** — Generate a MigrationPlan from detected infra + desired target.
- **`SshResult`** — —
- **`SshClient`** — Execute commands on a remote host via SSH (or locally).
- **`RemoteProbe`** — Thin wrapper kept for redeploy.detect compatibility.
- **`RemoteExecutor`** — Thin wrapper kept for deploy.core compatibility.
- **`WorkflowStep`** — —
- **`WorkflowDef`** — Named deployment workflow parsed from ``workflow[name="…"] { … }``.
- **`LoadResult`** — Full result of loading a ``redeploy.css`` file.
- **`DiscoveredHost`** — —
- **`ProbeResult`** — Full autonomous probe result for a single host.
- **`DockerComposeParser`** — Parser for docker-compose.yml / compose.yaml files.
- **`PortInfo`** — A published / exposed port mapping.
- **`VolumeInfo`** — A volume or bind-mount.
- **`ServiceInfo`** — One logical service / container / pod / deployment.
- **`ConversionWarning`** — A warning emitted by a parser or converter about lossy / uncertain data.
- **`ParsedSpec`** — Common intermediate representation from any IaC/CI-CD parser.
- **`Parser`** — Protocol every format-specific parser must satisfy.
- **`ParserRegistry`** — Dispatch file → registered parser.
- **`DSLNode`** — One parsed block from the CSS-like file.
- **`RedeployDSLParser`** — Parse a ``redeploy.css`` or ``redeploy.less`` file into a list of DSLNode objects.
- **`DockerComposeParser`** — Parser for Docker Compose files (v2 + v3 schema, Compose Spec).
- **`HostDetectionResult`** — Full detection result for a single host.
- **`WorkflowResult`** — Aggregated result across all probed hosts.
- **`DetectionWorkflow`** — Multi-host detection workflow with template scoring.
- **`GitTransactionResult`** — Result of full version bump transaction with git.
- **`GitVersionBumpTransaction`** — Version bump transaction with Git integration.
- **`MigrationMeta`** — Metadata for a migration.
- **`MigrationRegistry`** — Global registry of migration functions.
- **`StepManager`** — Manages step execution and tracking.
- **`step`** — Context manager for a deployment step.
- **`ConventionalCommit`** — Parsed conventional commit.
- **`BumpAnalysis`** — Result of analyzing commits for bump decision.
- **`DockerComposeResult`** — Result of docker compose command.
- **`DockerDSL`** — Docker-related DSL actions.
- **`StagingResult`** — Result of staging one source.
- **`VersionBumpTransaction`** — Atomic transaction for bumping version across multiple sources.
- **`VersionDiff`** — Version comparison result.
- **`StepContext`** — Tracks the execution of a single step.
- **`SourceAdapter`** — Protocol for version source adapters.
- **`SourceConfig`** — Single source of version truth (one file).
- **`GitConfig`** — Git integration settings.
- **`ChangelogConfig`** — Changelog generation settings.
- **`CommitRules`** — Conventional commits → bump type mapping.
- **`CommitsConfig`** — Conventional commits analysis settings.
- **`PackageConfig`** — Single package in monorepo (for policy=independent).
- **`Constraint`** — Cross-package version constraint.
- **`VersionManifest`** — Root manifest model for .redeploy/version.yaml.
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
- **`ServiceInfo`** — —
- **`PortInfo`** — —
- **`ConflictInfo`** — —
- **`RuntimeInfo`** — —
- **`AppHealthInfo`** — —
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
- **`DeviceRegistry`** — Persistent device registry — stored at ~/.config/redeploy/devices.yaml.

### Functions

- `read_local_version(workspace_root, app)` — Read VERSION file from local workspace.
- `read_remote_version(remote, remote_dir, app)` — Read VERSION file from remote device via SSH.
- `check_version(local, remote)` — Compare local vs remote version string. Returns (match, detail_line).
- `check_version_http(base_url, expected_version, timeout, endpoint)` — Call *endpoint* on a running service. Returns (ok, summary_line, payload).
- `probe_runtime(p)` — Detect installed runtimes: docker, k3s, podman, systemd.
- `probe_ports(p)` — Detect listening ports and which process owns them.
- `probe_iptables_dnat(p, ports)` — Find iptables DNAT rules stealing specific ports (returns [(port, target_ip)]).
- `probe_docker_services(p)` — List running Docker containers.
- `probe_k3s_services(p, namespaces)` — List running k3s pods.
- `probe_systemd_services(p, app)` — List app-related systemd units (also catches kiosk/chromium/openbox).
- `probe_health(host, app, domain)` — HTTP health checks against known endpoints.
- `detect_conflicts(ports, iptables_dnat, runtime, docker_services)` — Identify conflicts: port stealing, duplicate services, etc.
- `detect_strategy(runtime, docker_services, k3s_services, systemd_services)` — Infer the current deployment strategy from detected services.
- `get_pattern(name)` — Return pattern class by name, or None if not found.
- `list_patterns()` — Return all registered pattern names.
- `register_plugin(name)` — Decorator shortcut: @register_plugin('browser_reload').
- `load_user_plugins()` — Load user plugins from project-local and user-global directories.
- `systemd_reload(ctx)` — —
- `ssh(host, command, timeout, check)` — Execute a command on a remote host via SSH.
- `ssh_available(host, timeout, interval)` — Wait for SSH to become available on a host.
- `rsync(src, dst, exclude, delete)` — Synchronize files using rsync.
- `scp(src, dst, timeout)` — Copy files using SCP.
- `wait(seconds, message)` — Wait for specified seconds.
- `http_expect(url, expect, timeout, retries)` — Verify HTTP endpoint returns expected content.
- `version_check(manifest_path, expect, host, url)` — Verify deployed version matches expectation.
- `verify_data_integrity(ctx, local_counts, remote_counts)` — Compare local vs remote SQLite row counts and record results in *ctx*.
- `main()` — CLI entry point for running Python migrations.
- `collect_sqlite_counts(app_root, db_specs)` — Collect row counts for the given SQLite tables under *app_root*.
- `rsync_timeout_for_path(path, minimum, base, per_mb)` — Compute a conservative rsync timeout based on file size (seconds).
- `notify(ctx)` — —
- `cli(ctx, verbose)` — redeploy — Infrastructure migration toolkit: detect → plan → apply
- `detect(ctx, host, app, domain)` — Probe infrastructure and produce infra.yaml.
- `inspect(ctx, css_file)` — Show parsed content of redeploy.css — environments, templates, workflows.
- `workflow_cmd(ctx, name, css_file, dry_run)` — Run a named workflow from redeploy.css.
- `export_cmd(ctx, fmt, output, src_file)` — Convert between redeploy.css and redeploy.yaml formats.
- `plugin_cmd(ctx, subcommand, name)` — List or inspect registered redeploy plugins.
- `plan(ctx, infra, target, strategy)` — Generate migration-plan.yaml from infra.yaml + target config.
- `apply(ctx, plan_file, dry_run, step)` — Execute a migration plan.
- `migrate(ctx, host, app, domain)` — Full pipeline: detect → plan → apply.
- `run(ctx, spec_file, dry_run, plan_only)` — Execute migration from a single YAML spec (source + target in one file).
- `init(host, app, domain, strategy)` — Scaffold migration.yaml + redeploy.yaml for this project.
- `status(spec_file)` — Show current project manifest and spec summary.
- `devices(tag, strategy, reachable, as_json)` — List known devices from ~/.config/redeploy/devices.yaml.
- `scan(subnet, ssh_users, ssh_port, ping)` — Discover SSH-accessible devices on the local network.
- `device_add(host, device_id, name, tags)` — Add or update a device in the registry.
- `device_rm(device_id)` — Remove a device from the registry.
- `target(device_id, spec_file, dry_run, plan_only)` — Deploy a spec to a specific registered device.
- `probe(hosts, subnet, users, ssh_port)` — Autonomously probe one or more hosts — detect SSH credentials, strategy, app.
- `import_cmd(source, output, target_host, target_strategy)` — Parse an IaC/CI-CD file and produce a migration.yaml scaffold.
- `diff(ci_file, host, from_src, to_src)` — Compare IaC file vs live host (drift detection).  [Phase 3 — coming soon]
- `audit(last, host, app, only_failed)` — Show deploy audit log from ~/.config/redeploy/audit.jsonl.
- `patterns(name)` — List available deploy patterns or show detail for one.
- `version_cmd()` — Declarative version management: bump, verify, diff.
- `version_current(manifest)` — Show current version from manifest.
- `version_list(manifest, package_name, all_packages)` — List all version sources and their values.
- `version_verify(manifest, package_name, all_packages)` — Verify all sources match manifest version.
- `version_bump(type, manifest, package, all_packages)` — Bump version across all sources atomically.
- `version_set(version, manifest_path_str, package_name, all_packages)` — Set an explicit version across all manifest sources.
- `version_init(scan, force)` — Initialize .redeploy/version.yaml manifest.
- `version_diff(manifest, spec, live, app)` — Compare manifest version vs spec vs live.
- `bump_version(manifest, bump_type, new_version)` — Bump version across all sources atomically.
- `verify_sources(manifest)` — Verify all sources are in sync with manifest.version.
- `bump_version_with_git(manifest, bump_type, repo_path, new_version)` — Bump version with optional git integration.
- `bump_package(manifest, package_name, bump_type, new_version)` — Bump version of a single package in a monorepo manifest.
- `bump_all_packages(manifest, bump_type)` — Bump all packages in a monorepo manifest independently.
- `browser_reload(ctx)` — —
- `get_commits_since_tag(repo_path, tag)` — Get commit messages since tag.
- `parse_docker_ps(output)` — Parse 'docker ps --format "{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}|{{.State}}"' output.
- `parse_container_line(line)` — Parse a single NAME|STATUS|IMAGE pipe-delimited container line.
- `parse_system_info(output)` — Parse KEY:VALUE system info lines (HOSTNAME, UPTIME, DISK, MEM, LOAD) into a dict.
- `parse_diagnostics(output)` — Parse multi-section SSH diagnostics output into structured dict.
- `parse_health_info(output)` — Parse health-check SSH output (HOSTNAME, UPTIME, HEALTH, DISK, LOAD) into a dict.
- `build_context(state, probe, manifest)` — Flatten InfraState + ProbeResult into a flat dict for condition evaluation.
- `load_css(path)` — Parse ``redeploy.css`` and return manifest + templates + workflows.
- `load_css_text(text, source_file)` — Parse CSS text directly (for tests).
- `manifest_to_css(manifest, app)` — Render a ProjectManifest back to ``redeploy.css`` format.
- `templates_to_css(templates)` — Render DetectionTemplate list to CSS block.
- `discover(subnet, ssh_users, ssh_port, ping)` — Discover SSH-accessible hosts in the local network.
- `update_registry(hosts, registry, save)` — Merge discovered hosts into DeviceRegistry and optionally save.
- `auto_probe(ip_or_host, users, port, timeout)` — Autonomously probe a host — try all available SSH keys and users.
- `parse_file(path)` — Parse a single file with auto-detected format.
- `parse_dir(root, recursive, skip_errors)` — Parse all recognised files under *root*.
- `migration(name, version, description, author)` — Decorator to mark a function as a migration.
- `parse_conventional(message)` — Parse a conventional commit message.
- `analyze_commits(since_tag, repo_path, config)` — Analyze commits since tag to determine bump type.
- `format_analysis_report(analysis)` — Format bump analysis as human-readable report.
- `diff_manifest_vs_spec(manifest, spec_version)` — Compare manifest version vs migration.yaml target.version.
- `diff_manifest_vs_live(manifest, live_version)` — Compare manifest version vs live deployed version.
- `format_diff_report(diffs, manifest_version)` — Format diff results as human-readable report.
- `get_adapter(format_name)` — Get adapter by format name.
- `register_adapter(format_name, adapter)` — Register custom adapter.


## Project Structure

📄 `project`
📦 `redeploy`
📦 `redeploy.apply`
📄 `redeploy.apply.executor` (30 functions, 3 classes)
📄 `redeploy.cli` (58 functions)
📄 `redeploy.data_sync` (2 functions)
📦 `redeploy.detect`
📄 `redeploy.detect.detector` (3 functions, 1 classes)
📄 `redeploy.detect.probes` (9 functions)
📄 `redeploy.detect.remote`
📄 `redeploy.detect.templates` (10 functions, 5 classes)
📄 `redeploy.detect.workflow` (12 functions, 3 classes)
📄 `redeploy.discovery` (16 functions, 2 classes)
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
📦 `redeploy.iac`
📄 `redeploy.iac.base` (13 functions, 7 classes)
📄 `redeploy.iac.docker_compose` (11 functions, 1 classes)
📦 `redeploy.iac.parsers`
📄 `redeploy.iac.parsers.compose` (13 functions, 1 classes)
📄 `redeploy.iac.registry` (2 functions)
📄 `redeploy.models` (21 functions, 20 classes)
📄 `redeploy.observe` (14 functions, 3 classes)
📄 `redeploy.parse` (6 functions)
📄 `redeploy.patterns` (11 functions, 4 classes)
📦 `redeploy.plan`
📄 `redeploy.plan.planner` (21 functions, 1 classes)
📦 `redeploy.plugins` (10 functions, 2 classes)
📦 `redeploy.plugins.builtin`
📄 `redeploy.plugins.builtin.browser_reload` (3 functions)
📄 `redeploy.plugins.builtin.notify` (7 functions)
📄 `redeploy.plugins.builtin.systemd_reload` (2 functions)
📄 `redeploy.ssh` (17 functions, 4 classes)
📄 `redeploy.steps` (5 functions, 1 classes)
📄 `redeploy.verify` (7 functions, 1 classes)
📦 `redeploy.version` (4 functions)
📄 `redeploy.version.bump` (6 functions)
📄 `redeploy.version.changelog` (10 functions, 1 classes)
📄 `redeploy.version.commits` (3 functions, 2 classes)
📄 `redeploy.version.diff` (3 functions, 1 classes)
📄 `redeploy.version.git_integration` (13 functions, 2 classes)
📄 `redeploy.version.git_transaction` (5 functions, 2 classes)
📄 `redeploy.version.manifest` (10 functions, 8 classes)
📦 `redeploy.version.sources` (5 functions, 1 classes)
📄 `redeploy.version.sources.base` (4 functions, 1 classes)
📄 `redeploy.version.sources.json_` (4 functions, 1 classes)
📄 `redeploy.version.sources.plain` (3 functions, 1 classes)
📄 `redeploy.version.sources.regex` (3 functions, 1 classes)
📄 `redeploy.version.sources.toml_` (4 functions, 1 classes)
📄 `redeploy.version.sources.yaml_` (4 functions, 1 classes)
📄 `redeploy.version.transaction` (6 functions, 2 classes)
📄 `tree`

## Requirements

- Python >= >=3.11
- pydantic >=2.0- pyyaml >=6.0- click >=8.0- loguru >=0.7- paramiko >=3.0- httpx >=0.25- rich >=13.0- goal >=2.1.0- costs >=0.1.20- pfix >=0.1.60

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
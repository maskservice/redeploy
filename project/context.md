# System Architecture Analysis

## Overview

- **Project**: /home/tom/github/maskservice/redeploy
- **Primary Language**: python
- **Languages**: python: 186, md: 52, yaml: 45, shell: 2, json: 1
- **Analysis Mode**: static
- **Total Functions**: 2902
- **Total Classes**: 290
- **Modules**: 290
- **Entry Points**: 2507

## Architecture by Module

### project.map.toon
- **Functions**: 2444
- **File**: `map.toon.yaml`

### SUMD
- **Functions**: 931
- **Classes**: 51
- **File**: `SUMD.md`

### SUMR
- **Functions**: 164
- **Classes**: 51
- **File**: `SUMR.md`

### docs.dsl-migration
- **Functions**: 35
- **File**: `dsl-migration.md`

### redeploy.audit
- **Functions**: 32
- **Classes**: 6
- **File**: `audit.py`

### redeploy.analyze.spec_analyzer
- **Functions**: 30
- **Classes**: 14
- **File**: `spec_analyzer.py`

### redeploy.discovery
- **Functions**: 26
- **Classes**: 2
- **File**: `discovery.py`

### redeploy.cli.display
- **Functions**: 25
- **File**: `display.py`

### redeploy.fleet
- **Functions**: 23
- **Classes**: 6
- **File**: `fleet.py`

### redeploy.iac.docker_compose
- **Functions**: 23
- **Classes**: 1
- **File**: `docker_compose.py`

### redeploy.apply.handlers
- **Functions**: 22
- **File**: `handlers.py`

### redeploy.plan.planner
- **Functions**: 21
- **Classes**: 1
- **File**: `planner.py`

### redeploy.cli.commands.plan_apply
- **Functions**: 19
- **File**: `plan_apply.py`

### redeploy.cli.commands.version.scanner
- **Functions**: 18
- **File**: `scanner.py`

### redeploy.iac.parsers.compose
- **Functions**: 18
- **Classes**: 1
- **File**: `compose.py`

### redeploy.ssh
- **Functions**: 17
- **Classes**: 4
- **File**: `ssh.py`

### redeploy.apply.executor
- **Functions**: 17
- **Classes**: 1
- **File**: `executor.py`

### redeploy.mcp_server
- **Functions**: 15
- **File**: `mcp_server.py`

### redeploy.cli.commands.gh_workflow
- **Functions**: 15
- **File**: `gh_workflow.py`

### redeploy.version.changelog
- **Functions**: 15
- **Classes**: 1
- **File**: `changelog.py`

## Key Entry Points

Main execution flows into the system:

### redeploy.cli.commands.plan_apply.run
> Execute migration from a single YAML spec (source + target in one file).

SPEC defaults to migration.yaml (or value from redeploy.yaml manifest).


E
- **Calls**: click.command, click.argument, click.option, click.option, click.option, click.option, click.option, click.option

### redeploy.cli.commands.device_map.device_map_cmd
> Generate a full standardized device snapshot (hardware + infra + diagnostics).

The DeviceMap is a portable, persisted YAML file that captures the com
- **Calls**: click.command, click.argument, click.option, click.option, click.option, click.option, click.option, click.option

### redeploy.cli.commands.import_.import_cmd
> Parse an IaC/CI-CD file and produce a migration.yaml scaffold.

    Auto-detects format from filename. Built-in parsers cover:
    docker-compose, Doc
- **Calls**: click.command, click.argument, click.option, click.option, click.option, click.option, click.option, click.option

### redeploy.cli.commands.version.commands.version_init
> Initialize .redeploy/version.yaml manifest.
- **Calls**: version_cmd.command, click.option, click.option, click.option, click.option, click.option, Console, Path

### redeploy.cli.commands.audit.audit
> Show deploy audit log from ~/.config/redeploy/audit.jsonl.


Examples:
    redeploy audit
    redeploy audit --last 50 --failed
    redeploy audit --
- **Calls**: click.command, click.option, click.option, click.option, click.option, click.option, click.option, click.option

### redeploy.cli.commands.probe.probe
> Autonomously probe one or more hosts — detect SSH credentials, strategy, app.

Tries all available SSH keys (~/.ssh/) and common usernames.
Detects de
- **Calls**: click.command, click.argument, click.option, click.option, click.option, click.option, click.option, click.option

### redeploy.cli.commands.patterns.patterns
> List available deploy patterns or show detail for one.


Examples:
    redeploy patterns
    redeploy patterns blue_green
    redeploy patterns canar
- **Calls**: click.command, click.argument, Console, console.print, Table, t.add_column, t.add_column, t.add_column

### redeploy.cli.commands.gh_workflow.gh_workflow_run
> Trigger a GitHub Actions workflow_dispatch run on demand via gh CLI.
- **Calls**: gh_workflow_cmd.command, click.argument, click.option, click.option, click.option, click.option, click.option, Console

### redeploy.cli.commands.hardware.hardware
> Probe and diagnose hardware on a remote host.

Checks DSI display, DRM connectors, backlight controller, I2C buses,
config.txt overlays and Wayland co
- **Calls**: click.command, click.argument, click.option, click.option, click.option, click.option, click.option, click.option

### redeploy.cli.commands.bump_fix.fix_cmd
> Self-healing deploy: bump version, then run with LLM auto-fix on failure.


PATH is a spec file or directory containing migration.yaml / migration.md
- **Calls**: click.command, click.argument, click.option, click.option, click.option, click.option, click.option, click.option

### redeploy.cli.commands.lint.lint
> Static analysis of a migration spec (YAML or markpact .md).

Detects missing files, broken references, missing command_ref blocks,
docker-compose inco
- **Calls**: click.command, click.argument, click.option, click.option, click.option, Console, ProjectManifest.find_and_load, SUMD.load_spec_or_exit

### redeploy.cli.commands.plan_apply.migrate
> Full pipeline: detect → plan → apply.
- **Calls**: click.command, click.option, click.option, click.option, click.option, click.option, click.option, click.option

### redeploy.analyze.spec_analyzer._ComposeChecker._scan_compose
- **Calls**: data.get, services.items, svc.get, isinstance, svc.get, isinstance, svc.get, yaml.safe_load

### redeploy.cli.commands.plan_apply.plan
> Generate migration-plan.yaml from infra.yaml + target config.
- **Calls**: click.command, click.option, click.option, click.option, click.option, click.option, click.option, click.option

### redeploy.cli.commands.exec_.exec_cmd
> Execute a script from a markdown codeblock by reference.

REF format: #section-id or ./file.md#section-id or just ref-id (for markpact:ref)

Extracts 
- **Calls**: click.command, click.argument, click.option, click.option, click.option, click.option, Console, console.print

### examples.redeploy_iac_parsers.argocd_flux.FluxKustomizationParser.parse
- **Calls**: ParsedSpec, str, None.strip, None.strip, None.strip, None.strip, None.strip, None.strip

### redeploy.heal.runner.HealRunner._heal_step
> Single heal iteration: diagnose → LLM → decide.

Returns *(decision, failed_step, loop_hint)*.
- **Calls**: SUMD.parse_failed_step, self.console.print, self.console.print, SUMD.collect_diagnostics, next, os.getenv, self.console.print, self.spec_path.read_text

### redeploy.cli.commands.push.push
> Apply desired-state YAML/JSON file(s) to a remote host.

Reads each FILE, detects its schema (hardware, infra, …) and applies
only the settings that d
- **Calls**: click.command, click.argument, click.argument, click.option, click.option, Console, console.print, RemoteProbe

### redeploy.cli.commands.version.commands.version_bump
> Bump version across all sources atomically.

Examples:
    redeploy version bump patch
    redeploy version bump patch --commit --tag --push
    redep
- **Calls**: version_cmd.command, click.argument, click.option, click.option, click.option, click.option, click.option, click.option

### redeploy.cli.commands.plugin.plugin_cmd
> List or inspect registered redeploy plugins.


Examples:
    redeploy plugin list
    redeploy plugin info browser_reload
    redeploy plugin info sy
- **Calls**: click.command, click.argument, click.argument, Console, SUMD.load_user_plugins, registry.names, registry.names, console.print

### redeploy.cli.commands.version.commands.version_list
> List all version sources and their values.
- **Calls**: version_cmd.command, click.option, click.option, click.option, Console, Path, VersionManifest.load, SUMD._resolve_monorepo_targets

### redeploy.iac.config_hints.ConfigHintsParser._parse_k8s_yaml
- **Calls**: self._new_spec, redeploy.steps.StepLibrary.list, spec.runtime_hints.append, yaml.safe_load_all, None.lower, str, path.read_text, isinstance

### examples.redeploy_iac_parsers.argocd_flux.ArgoCDApplicationParser.parse
- **Calls**: ParsedSpec, str, None.strip, None.strip, None.strip, None.strip, None.strip, None.strip

### redeploy.analyze.spec_analyzer._DockerBuildChecker.check
- **Calls**: set, step.get, sid.startswith, step.get, step.get, self.FILE_FLAG_RE.finditer, cmd.split, context.startswith

### redeploy.cli.commands.prompt_cmd.prompt_cmd
> Natural-language → redeploy command via LLM.


INSTRUCTION is a free-text description of what you want to do.


Examples:
    redeploy prompt "deplo
- **Calls**: click.command, click.argument, click.option, click.option, click.option, click.option, Console, SUMD.build_schema

### redeploy.cli.commands.blueprint._print_blueprint
- **Calls**: console.print, console.print, console.print, console.print, console.print, click.echo, click.echo, None.join

### redeploy.cli.commands.exec_.exec_multi_cmd
> Execute multiple scripts from markdown codeblocks by reference.

REFS format: comma-separated list of ref ids (markpact:ref or section headings)


Ex
- **Calls**: click.command, click.argument, click.option, click.option, click.option, click.option, click.option, Console

### redeploy.cli.commands.blueprint.capture
> Probe HOST and extract a DeviceBlueprint from all available sources.
- **Calls**: blueprint_cmd.command, click.argument, click.option, click.option, click.option, click.option, click.option, click.option

### redeploy.cli.commands.detect.detect
> Probe infrastructure and produce infra.yaml.

With --workflow: multi-host detection with template scoring.
Reads hosts from redeploy.yaml / redeploy.c
- **Calls**: click.command, click.option, click.option, click.option, click.option, click.option, click.option, click.option

### redeploy.cli.commands.version.helpers._bump_single
> Bump version for a single manifest (or package).
- **Calls**: m.git.tag_format.format, SUMD.analyze_commits, console.print, console.print, console.print, sys.exit, SUMD._calculate_bump, console.print

## Process Flows

Key execution flows identified:

### Flow 1: run
```
run [redeploy.cli.commands.plan_apply]
```

### Flow 2: device_map_cmd
```
device_map_cmd [redeploy.cli.commands.device_map]
```

### Flow 3: import_cmd
```
import_cmd [redeploy.cli.commands.import_]
```

### Flow 4: version_init
```
version_init [redeploy.cli.commands.version.commands]
```

### Flow 5: audit
```
audit [redeploy.cli.commands.audit]
```

### Flow 6: probe
```
probe [redeploy.cli.commands.probe]
```

### Flow 7: patterns
```
patterns [redeploy.cli.commands.patterns]
```

### Flow 8: gh_workflow_run
```
gh_workflow_run [redeploy.cli.commands.gh_workflow]
```

### Flow 9: hardware
```
hardware [redeploy.cli.commands.hardware]
```

### Flow 10: fix_cmd
```
fix_cmd [redeploy.cli.commands.bump_fix]
```

## Key Classes

### redeploy.plan.planner.Planner
> Generate a MigrationPlan from detected infra + desired target.
- **Methods**: 21
- **Key Methods**: redeploy.plan.planner.Planner.__init__, redeploy.plan.planner.Planner.run, redeploy.plan.planner.Planner._plan_conflict_fixes, redeploy.plan.planner.Planner._plan_stop_old_services, redeploy.plan.planner.Planner._plan_deploy_new, redeploy.plan.planner.Planner._plan_docker_full, redeploy.plan.planner.Planner._plan_podman_quadlet, redeploy.plan.planner.Planner._plan_kiosk, redeploy.plan.planner.Planner._plan_kiosk_appliance, redeploy.plan.planner.Planner._plan_systemd

### redeploy.apply.executor.Executor
> Execute MigrationPlan steps on a remote host.
- **Methods**: 20
- **Key Methods**: redeploy.apply.executor.Executor.__init__, redeploy.apply.executor.Executor.completed_steps, redeploy.apply.executor.Executor.state, redeploy.apply.executor.Executor.state_path, redeploy.apply.executor.Executor.run, redeploy.apply.executor.Executor._execute_steps_loop, redeploy.apply.executor.Executor._skip_step, redeploy.apply.executor.Executor._handle_step_failure, redeploy.apply.executor.Executor._handle_completion, redeploy.apply.executor.Executor._fire_hooks

### redeploy.observe.AuditEntry
> Single audit log entry — immutable snapshot of one deployment.
- **Methods**: 18
- **Key Methods**: redeploy.observe.AuditEntry.__init__, redeploy.observe.AuditEntry.ts, redeploy.observe.AuditEntry.host, redeploy.observe.AuditEntry.app, redeploy.observe.AuditEntry.from_strategy, redeploy.observe.AuditEntry.to_strategy, redeploy.observe.AuditEntry.ok, redeploy.observe.AuditEntry.elapsed_s, redeploy.observe.AuditEntry.steps_total, redeploy.observe.AuditEntry.steps_ok

### redeploy.iac.docker_compose.DockerComposeParser
> Parser for docker-compose.yml / compose.yaml files.
- **Methods**: 18
- **Key Methods**: redeploy.iac.docker_compose.DockerComposeParser.can_parse, redeploy.iac.docker_compose.DockerComposeParser.parse, redeploy.iac.docker_compose.DockerComposeParser._load_merged, redeploy.iac.docker_compose.DockerComposeParser._find_override, redeploy.iac.docker_compose.DockerComposeParser._load_dotenv, redeploy.iac.docker_compose.DockerComposeParser._resolve_image_and_build, redeploy.iac.docker_compose.DockerComposeParser._parse_service_ports, redeploy.iac.docker_compose.DockerComposeParser._parse_service_volumes, redeploy.iac.docker_compose.DockerComposeParser._parse_service_env, redeploy.iac.docker_compose.DockerComposeParser._parse_service_env_files

### redeploy.iac.parsers.compose.DockerComposeParser
> Parser for Docker Compose files (v2 + v3 schema, Compose Spec).
- **Methods**: 18
- **Key Methods**: redeploy.iac.parsers.compose.DockerComposeParser.can_parse, redeploy.iac.parsers.compose.DockerComposeParser.parse, redeploy.iac.parsers.compose.DockerComposeParser._collect_service_secrets, redeploy.iac.parsers.compose.DockerComposeParser._merge_service_env_files, redeploy.iac.parsers.compose.DockerComposeParser._collect_service_image, redeploy.iac.parsers.compose.DockerComposeParser._parse_service_networks, redeploy.iac.parsers.compose.DockerComposeParser._parse_service_replicas, redeploy.iac.parsers.compose.DockerComposeParser._parse_service, redeploy.iac.parsers.compose.DockerComposeParser._parse_build, redeploy.iac.parsers.compose.DockerComposeParser._parse_command

### redeploy.fleet.Fleet
> Unified first-class fleet — wraps FleetConfig and/or DeviceRegistry.

Provides a single query interf
- **Methods**: 15
- **Key Methods**: redeploy.fleet.Fleet.__init__, redeploy.fleet.Fleet.from_file, redeploy.fleet.Fleet.from_registry, redeploy.fleet.Fleet.from_config, redeploy.fleet.Fleet.devices, redeploy.fleet.Fleet.get, redeploy.fleet.Fleet.by_tag, redeploy.fleet.Fleet.by_stage, redeploy.fleet.Fleet.by_strategy, redeploy.fleet.Fleet.prod

### redeploy.ssh.SshClient
> Execute commands on a remote host via SSH (or locally).

Args:
    host:     ``user@ip`` string, or 
- **Methods**: 15
- **Key Methods**: redeploy.ssh.SshClient.__init__, redeploy.ssh.SshClient.key, redeploy.ssh.SshClient.key, redeploy.ssh.SshClient.run, redeploy.ssh.SshClient.rsync, redeploy.ssh.SshClient.scp, redeploy.ssh.SshClient.put_file, redeploy.ssh.SshClient.is_reachable, redeploy.ssh.SshClient.is_ssh_ready, redeploy.ssh.SshClient.ping

### redeploy.version.changelog.ChangelogManager
> Manage CHANGELOG.md in keep-a-changelog format.
- **Methods**: 14
- **Key Methods**: redeploy.version.changelog.ChangelogManager.__init__, redeploy.version.changelog.ChangelogManager.exists, redeploy.version.changelog.ChangelogManager.read, redeploy.version.changelog.ChangelogManager._default_template, redeploy.version.changelog.ChangelogManager.get_unreleased_section, redeploy.version.changelog.ChangelogManager.prepare_release, redeploy.version.changelog.ChangelogManager._format_release_content, redeploy.version.changelog.ChangelogManager._init_categories, redeploy.version.changelog.ChangelogManager._categorize_commits, redeploy.version.changelog.ChangelogManager._format_commit_entry

### redeploy.iac.config_hints.ConfigHintsParser
> Best-effort parser for common DevOps/IaC config files.
- **Methods**: 14
- **Key Methods**: redeploy.iac.config_hints.ConfigHintsParser.can_parse, redeploy.iac.config_hints.ConfigHintsParser.parse, redeploy.iac.config_hints.ConfigHintsParser._new_spec, redeploy.iac.config_hints.ConfigHintsParser._read_text, redeploy.iac.config_hints.ConfigHintsParser._parse_dockerfile, redeploy.iac.config_hints.ConfigHintsParser._parse_nginx, redeploy.iac.config_hints.ConfigHintsParser._looks_like_k8s, redeploy.iac.config_hints.ConfigHintsParser._parse_k8s_yaml, redeploy.iac.config_hints.ConfigHintsParser._parse_terraform, redeploy.iac.config_hints.ConfigHintsParser._parse_toml

### redeploy.version.git_integration.GitIntegration
> Git operations for version management.
- **Methods**: 13
- **Key Methods**: redeploy.version.git_integration.GitIntegration.__init__, redeploy.version.git_integration.GitIntegration._run, redeploy.version.git_integration.GitIntegration.require_clean, redeploy.version.git_integration.GitIntegration.is_clean, redeploy.version.git_integration.GitIntegration.get_dirty_files, redeploy.version.git_integration.GitIntegration.stage_files, redeploy.version.git_integration.GitIntegration.commit, redeploy.version.git_integration.GitIntegration.tag, redeploy.version.git_integration.GitIntegration.push, redeploy.version.git_integration.GitIntegration.tag_exists

### redeploy.audit.Auditor
> Compare a MigrationSpec's expectations against a live target host.
- **Methods**: 12
- **Key Methods**: redeploy.audit.Auditor.__init__, redeploy.audit.Auditor.run, redeploy.audit.Auditor._dispatch, redeploy.audit.Auditor._probe_one, redeploy.audit.Auditor._probe_binary, redeploy.audit.Auditor._probe_directory, redeploy.audit.Auditor._probe_file, redeploy.audit.Auditor._probe_local_file, redeploy.audit.Auditor._probe_port_listening, redeploy.audit.Auditor._probe_container_image

### redeploy.heal.HealRunner
> Wraps Executor with self-healing loop.

Parameters
----------
migration : Migration
    Planned migr
- **Methods**: 11
- **Key Methods**: redeploy.heal.HealRunner.__init__, redeploy.heal.HealRunner._make_executor, redeploy.heal.HealRunner._reload_migration, redeploy.heal.HealRunner._run_executor_attempt, redeploy.heal.HealRunner._collect_diag_with_hint, redeploy.heal.HealRunner._extract_diag_hint, redeploy.heal.HealRunner._ask_and_apply_fix, redeploy.heal.HealRunner._record_repair, redeploy.heal.HealRunner._is_repeating_loop, redeploy.heal.HealRunner._retry_after_heal

### redeploy.verify.VerifyContext
> Accumulates check results during verification.
- **Methods**: 11
- **Key Methods**: redeploy.verify.VerifyContext.check, redeploy.verify.VerifyContext.add_pass, redeploy.verify.VerifyContext.add_fail, redeploy.verify.VerifyContext.add_warn, redeploy.verify.VerifyContext.add_info, redeploy.verify.VerifyContext.passed, redeploy.verify.VerifyContext.failed, redeploy.verify.VerifyContext.warned, redeploy.verify.VerifyContext.total, redeploy.verify.VerifyContext.ok

### redeploy.apply.progress.ProgressEmitter
> Emits YAML-formatted progress events to a stream (default: stdout).

Each event is a YAML document (
- **Methods**: 11
- **Key Methods**: redeploy.apply.progress.ProgressEmitter.__init__, redeploy.apply.progress.ProgressEmitter._ts, redeploy.apply.progress.ProgressEmitter._elapsed, redeploy.apply.progress.ProgressEmitter._emit, redeploy.apply.progress.ProgressEmitter.start, redeploy.apply.progress.ProgressEmitter.step_start, redeploy.apply.progress.ProgressEmitter.step_done, redeploy.apply.progress.ProgressEmitter.step_fail, redeploy.apply.progress.ProgressEmitter.progress, redeploy.apply.progress.ProgressEmitter.done

### redeploy.apply.state.ResumeState
> Checkpoint for a single MigrationPlan execution.
- **Methods**: 10
- **Key Methods**: redeploy.apply.state.ResumeState.load, redeploy.apply.state.ResumeState.load_or_new, redeploy.apply.state.ResumeState.save, redeploy.apply.state.ResumeState.remove, redeploy.apply.state.ResumeState.mark_done, redeploy.apply.state.ResumeState.mark_failed, redeploy.apply.state.ResumeState.reset, redeploy.apply.state.ResumeState.is_done, redeploy.apply.state.ResumeState.completed_count, redeploy.apply.state.ResumeState.remaining
- **Inherits**: BaseModel

### redeploy.models.devices.DeviceRegistry
> Persistent device registry — stored at ~/.config/redeploy/devices.yaml.
- **Methods**: 9
- **Key Methods**: redeploy.models.devices.DeviceRegistry.get, redeploy.models.devices.DeviceRegistry.upsert, redeploy.models.devices.DeviceRegistry.remove, redeploy.models.devices.DeviceRegistry.by_tag, redeploy.models.devices.DeviceRegistry.by_strategy, redeploy.models.devices.DeviceRegistry.reachable, redeploy.models.devices.DeviceRegistry.default_path, redeploy.models.devices.DeviceRegistry.load, redeploy.models.devices.DeviceRegistry.save
- **Inherits**: BaseModel

### redeploy.audit.AuditReport
- **Methods**: 8
- **Key Methods**: redeploy.audit.AuditReport.add, redeploy.audit.AuditReport.passed, redeploy.audit.AuditReport.failed, redeploy.audit.AuditReport.warned, redeploy.audit.AuditReport.skipped, redeploy.audit.AuditReport.ok, redeploy.audit.AuditReport.summary, redeploy.audit.AuditReport.to_dict

### redeploy.audit._Probe
> Thin wrapper around SshClient with sensible audit timeouts.
- **Methods**: 8
- **Key Methods**: redeploy.audit._Probe.__init__, redeploy.audit._Probe.has_binary, redeploy.audit._Probe.has_path, redeploy.audit._Probe.port_listening, redeploy.audit._Probe.has_image, redeploy.audit._Probe.has_systemd_unit, redeploy.audit._Probe.apt_package, redeploy.audit._Probe.disk_free_gib

### redeploy.models.hardware.HardwareInfo
> Hardware state produced by hardware probe.
- **Methods**: 8
- **Key Methods**: redeploy.models.hardware.HardwareInfo.has_dsi, redeploy.models.hardware.HardwareInfo.kms_enabled, redeploy.models.hardware.HardwareInfo.dsi_connected, redeploy.models.hardware.HardwareInfo.dsi_physically_connected, redeploy.models.hardware.HardwareInfo.dsi_enabled, redeploy.models.hardware.HardwareInfo.backlight_on, redeploy.models.hardware.HardwareInfo.errors, redeploy.models.hardware.HardwareInfo.warnings
- **Inherits**: BaseModel

### redeploy.version.manifest.VersionManifest
> Root manifest model for .redeploy/version.yaml.
- **Methods**: 8
- **Key Methods**: redeploy.version.manifest.VersionManifest.load, redeploy.version.manifest.VersionManifest.save, redeploy.version.manifest.VersionManifest.format_version, redeploy.version.manifest.VersionManifest.get_source_paths, redeploy.version.manifest.VersionManifest.get_package, redeploy.version.manifest.VersionManifest.list_packages, redeploy.version.manifest.VersionManifest.is_monorepo, redeploy.version.manifest.VersionManifest.get_all_package_versions
- **Inherits**: BaseModel

## Data Transformation Functions

Key functions that process and transform data:

### SUMR._parse_probe_output

### SUMR._parse_probe_input

### SUMD._parse_container_statuses

### SUMD._parse_compose_ports

### SUMD._parse_compose_volumes

### SUMD._parse_compose_env

### SUMD._parse_compose_healthcheck

### SUMD.parse_migration_meta

### SUMD._format_output

### SUMD._apply_transform

### SUMD._parse_llm_response

### SUMD._format_release_tag

### SUMD._format_version_scan_source_status

### SUMD._format_workflow_header

### SUMD._parse_probe_output

### SUMD._parse_probe_input

### SUMD.format_decision_message

### SUMD.parse_failed_step

### SUMD.parse_json_file

### SUMD._parse_port

### SUMD._parse_volume

### SUMD._load_entrypoint_parsers

### SUMD._load_local_parsers

### SUMD.parse_file

### SUMD.parse_dir

## Behavioral Patterns

### recursion_probe_hardware
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: redeploy.detect.detector.Detector.probe_hardware

### recursion_list
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: redeploy.dsl_python.decorators.MigrationRegistry.list

### recursion__deep_merge
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: redeploy.markpact.compiler._deep_merge

### recursion__parse_port
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: redeploy.iac.docker_compose._parse_port

### recursion__deep_merge
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: redeploy.iac.docker_compose._deep_merge

### state_machine_HardwareInfo
- **Type**: state_machine
- **Confidence**: 0.70
- **Functions**: redeploy.models.hardware.HardwareInfo.has_dsi, redeploy.models.hardware.HardwareInfo.kms_enabled, redeploy.models.hardware.HardwareInfo.dsi_connected, redeploy.models.hardware.HardwareInfo.dsi_physically_connected, redeploy.models.hardware.HardwareInfo.dsi_enabled

### state_machine_step
- **Type**: state_machine
- **Confidence**: 0.70
- **Functions**: redeploy.dsl_python.decorators.step.__enter__, redeploy.dsl_python.decorators.step.__exit__

### state_machine_ResumeState
- **Type**: state_machine
- **Confidence**: 0.70
- **Functions**: redeploy.apply.state.ResumeState.load, redeploy.apply.state.ResumeState.load_or_new, redeploy.apply.state.ResumeState.save, redeploy.apply.state.ResumeState.remove, redeploy.apply.state.ResumeState.mark_done

### state_machine_StateHandler
- **Type**: state_machine
- **Confidence**: 0.70
- **Functions**: redeploy.apply.state_apply.StateHandler.accept, redeploy.apply.state_apply.StateHandler.apply

### state_machine_HardwareStateHandler
- **Type**: state_machine
- **Confidence**: 0.70
- **Functions**: redeploy.apply.state_apply.HardwareStateHandler.accept, redeploy.apply.state_apply.HardwareStateHandler.apply

### state_machine_InfraStateHandler
- **Type**: state_machine
- **Confidence**: 0.70
- **Functions**: redeploy.apply.state_apply.InfraStateHandler.accept, redeploy.apply.state_apply.InfraStateHandler.apply

### state_machine_Executor
- **Type**: state_machine
- **Confidence**: 0.70
- **Functions**: redeploy.apply.executor.Executor.__init__, redeploy.apply.executor.Executor.completed_steps, redeploy.apply.executor.Executor.state, redeploy.apply.executor.Executor.state_path, redeploy.apply.executor.Executor.run

## Public API Surface

Functions exposed as public API (no underscore prefix):

- `redeploy.cli.commands.plan_apply.run` - 110 calls
- `redeploy.cli.commands.device_map.device_map_cmd` - 59 calls
- `redeploy.cli.commands.import_.import_cmd` - 56 calls
- `redeploy.cli.commands.version.commands.version_init` - 56 calls
- `redeploy.cli.commands.audit.audit` - 51 calls
- `redeploy.cli.commands.probe.probe` - 50 calls
- `redeploy.cli.commands.patterns.patterns` - 50 calls
- `redeploy.cli.commands.gh_workflow.gh_workflow_run` - 49 calls
- `redeploy.integrations.op3_bridge.snapshot_to_hardware_info` - 49 calls
- `redeploy.cli.commands.hardware.hardware` - 47 calls
- `redeploy.cli.commands.bump_fix.fix_cmd` - 44 calls
- `redeploy.cli.commands.lint.lint` - 44 calls
- `redeploy.cli.commands.plan_apply.migrate` - 43 calls
- `redeploy.cli.commands.plan_apply.plan` - 41 calls
- `redeploy.cli.commands.exec_.exec_cmd` - 40 calls
- `examples.redeploy_iac_parsers.argocd_flux.FluxKustomizationParser.parse` - 40 calls
- `redeploy.cli.commands.push.push` - 39 calls
- `redeploy.cli.commands.version.commands.version_bump` - 39 calls
- `redeploy.cli.commands.plugin.plugin_cmd` - 38 calls
- `redeploy.cli.commands.version.commands.version_list` - 38 calls
- `examples.redeploy_iac_parsers.argocd_flux.ArgoCDApplicationParser.parse` - 38 calls
- `redeploy.analyze.spec_analyzer._DockerBuildChecker.check` - 37 calls
- `redeploy.cli.commands.prompt_cmd.prompt_cmd` - 37 calls
- `redeploy.cli.commands.exec_.exec_multi_cmd` - 35 calls
- `redeploy.cli.commands.blueprint.capture` - 35 calls
- `redeploy.cli.commands.detect.detect` - 35 calls
- `redeploy.discovery.auto_probe` - 33 calls
- `redeploy.iac.docker_compose.DockerComposeParser.parse` - 33 calls
- `redeploy.cli.commands.target.target` - 31 calls
- `redeploy.cli.commands.devices.scan` - 31 calls
- `redeploy.detect.detector.Detector.run` - 30 calls
- `redeploy.heal.hint_provider.apply_fix_to_spec` - 30 calls
- `redeploy.dsl_python.runner.PythonMigrationRunner.run_file` - 30 calls
- `redeploy.cli.commands.init.init` - 29 calls
- `redeploy.cli.commands.version.commands.version_set` - 29 calls
- `examples.redeploy_iac_parsers.gitops_ci.GitHubActionsGitOpsParser.parse` - 29 calls
- `redeploy.cli.commands.devices.devices` - 28 calls
- `redeploy.apply.state_apply.HardwareStateHandler.apply` - 27 calls
- `examples.redeploy_iac_parsers.helm_kustomize.HelmTemplatesParser.parse` - 27 calls
- `redeploy.cli.commands.status.status` - 26 calls

## System Interactions

How components interact:

```mermaid
graph TD
    run --> command
    run --> argument
    run --> option
    device_map_cmd --> command
    device_map_cmd --> argument
    device_map_cmd --> option
    import_cmd --> command
    import_cmd --> argument
    import_cmd --> option
    version_init --> command
    version_init --> option
    audit --> command
    audit --> option
    probe --> command
    probe --> argument
    probe --> option
    patterns --> command
    patterns --> argument
    patterns --> Console
    patterns --> print
    patterns --> Table
    gh_workflow_run --> command
    gh_workflow_run --> argument
    gh_workflow_run --> option
    hardware --> command
    hardware --> argument
    hardware --> option
    fix_cmd --> command
    fix_cmd --> argument
    fix_cmd --> option
```

## Reverse Engineering Guidelines

1. **Entry Points**: Start analysis from the entry points listed above
2. **Core Logic**: Focus on classes with many methods
3. **Data Flow**: Follow data transformation functions
4. **Process Flows**: Use the flow diagrams for execution paths
5. **API Surface**: Public API functions reveal the interface

## Context for LLM

Maintain the identified architectural patterns and public API surface when suggesting changes.
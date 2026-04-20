# redeploy

SUMD - Structured Unified Markdown Descriptor for AI-aware project refactorization

## Contents

- [Metadata](#metadata)
- [Architecture](#architecture)
- [Dependencies](#dependencies)
- [Source Map](#source-map)
- [Refactoring Analysis](#refactoring-analysis)
- [Intent](#intent)

## Metadata

- **name**: `redeploy`
- **version**: `0.1.3`
- **python_requires**: `>=3.11`
- **ai_model**: `openrouter/qwen/qwen3-coder-next`
- **ecosystem**: SUMD + DOQL + testql + taskfile
- **generated_from**: pyproject.toml, Makefile, goal.yaml, .env.example, src(10 mod), project/(6 analysis files)

## Architecture

```
SUMD (description) → DOQL/source (code) → taskfile (automation) → testql (verification)
```

### Source Modules

- `redeploy.cli`
- `redeploy.data_sync`
- `redeploy.discovery`
- `redeploy.fleet`
- `redeploy.models`
- `redeploy.parse`
- `redeploy.ssh`
- `redeploy.steps`
- `redeploy.verify`
- `redeploy.version`

## Dependencies

### Runtime

```text markpact:deps python
pydantic>=2.0
pyyaml>=6.0
click>=8.0
loguru>=0.7
paramiko>=3.0
httpx>=0.25
rich>=13.0
goal>=2.1.0
costs>=0.1.20
pfix>=0.1.60
```

### Development

```text markpact:deps python scope=dev
pytest>=8.0
ruff>=0.4
goal>=2.1.0
costs>=0.1.20
pfix>=0.1.60
```

## Source Map

*Top 5 modules by symbol density — signatures for LLM orientation.*

### `redeploy.ssh` (`redeploy/ssh.py`)

```python
class SshResult:
    def ok()  # CC=1
    def success()  # CC=1
    def out()  # CC=1
class SshClient:  # Execute commands on a remote host via SSH (or locally).
    def __init__(host, port, key, ssh_id)  # CC=1
    def key()  # CC=1
    def key(v)  # CC=1
    def run(cmd, timeout)  # CC=5
    def rsync(local_path, remote_path, exclude, delete, timeout)  # CC=7
    def scp(local_path, remote_path, timeout)  # CC=4
    def put_file(content, remote_path, mode)  # CC=5
    def is_reachable(timeout)  # CC=3
    def is_ssh_ready()  # CC=2
    def ping()  # CC=4
    def _run_local(cmd, timeout)  # CC=3
    def _ssh_opts()  # CC=2
    def _scp_opts()  # CC=2
    def _detect_ssh_key()  # CC=1
    def _detect_key()  # CC=6
class RemoteProbe:  # Thin wrapper kept for redeploy.detect compatibility.
    def __init__(host)  # CC=1
    def is_local()  # CC=1
    def is_local(v)  # CC=1
class RemoteExecutor:  # Thin wrapper kept for deploy.core compatibility.
    def __init__(device)  # CC=1
    def ssh_target()  # CC=1
    def ssh_opts()  # CC=1
    def scp_opts()  # CC=1
```

### `redeploy.cli` (`redeploy/cli.py`)

```python
def _print_plan_table(console, migration)  # CC=4, fan=6
def _run_apply(console, migration, dry_run, output, ssh_key)  # CC=4, fan=6
def _setup_logging(verbose)  # CC=2, fan=2
def cli(ctx, verbose)  # CC=1, fan=5
def _run_detect_workflow(console, hosts, manifest, app, scan_subnet, deep, save_yaml)  # CC=18, fan=14 ⚠
def detect(ctx, host, app, domain, output, run_workflow, scan_subnet, no_deep, save_yaml)  # CC=24, fan=22 ⚠
def plan(ctx, infra, target, strategy, domain, target_version, compose, env_file, output)  # CC=11, fan=17 ⚠
def apply(ctx, plan_file, dry_run, step, output)  # CC=9, fan=12
def migrate(ctx, host, app, domain, target, strategy, target_version, compose, env_file, dry_run, infra_out, plan_out)  # CC=13, fan=18 ⚠
def run(ctx, spec_file, dry_run, plan_only, do_detect, plan_out, output, env_name)  # CC=17, fan=24 ⚠
def _find_manifest_path()  # CC=3, fan=4
def _resolve_device(console, device_id)  # CC=5, fan=6
def _load_spec_with_manifest(console, spec_file, dev)  # CC=5, fan=8
def _overlay_device_onto_spec(spec, dev, console)  # CC=10, fan=2 ⚠
def _run_detect_for_spec(console, spec, do_detect)  # CC=3, fan=7
def init(host, app, domain, strategy, force)  # CC=10, fan=8 ⚠
def status(spec_file)  # CC=12, fan=16 ⚠
def devices(tag, strategy, reachable, as_json)  # CC=18, fan=14 ⚠
def scan(subnet, ssh_users, ssh_port, ping, no_mdns, timeout, no_save)  # CC=11, fan=12 ⚠
def device_add(host, device_id, name, tags, strategy, app, ssh_port, ssh_key)  # CC=7, fan=13
def device_rm(device_id)  # CC=2, fan=7
def target(device_id, spec_file, dry_run, plan_only, do_detect, plan_out)  # CC=10, fan=18 ⚠
def probe(hosts, subnet, users, ssh_port, app_hint, timeout, no_save, as_json)  # CC=27, fan=22 ⚠
```

### `redeploy.models` (`redeploy/models.py`)

```python
class ConflictSeverity:
class StepAction:
class StepStatus:
class DeployStrategy:
class ServiceInfo:
class PortInfo:
class ConflictInfo:
class RuntimeInfo:
class AppHealthInfo:
class InfraState:  # Full detected state of infrastructure — output of `detect`.
class TargetConfig:  # Desired infrastructure state — input to `plan`.
class MigrationStep:
class InfraSpec:  # Declarative description of one infrastructure state (from OR
class MigrationSpec:  # Single YAML file describing full migration: from-state → to-
    def from_file(cls, path)  # CC=1
    def to_infra_state()  # CC=4
    def to_target_config()  # CC=2
class MigrationPlan:  # Full migration plan — output of `plan`, input to `apply`.
class EnvironmentConfig:  # One named environment (prod / dev / rpi5 / staging …) in red
class ProjectManifest:  # Per-project redeploy.yaml — replaces repetitive Makefile var
    def find_and_load(cls, start)  # CC=3
    def env(name)  # CC=1
    def resolve_env(name)  # CC=9
    def from_dotenv(cls, project_dir)  # CC=12 ⚠
    def apply_to_spec(spec, env_name)  # CC=19 ⚠
class DeployRecord:  # Single deployment event recorded for a device.
class KnownDevice:  # Device known to redeploy — persisted in ~/.config/redeploy/d
    def last_deploy()  # CC=2
    def is_reachable()  # CC=2
    def record_deploy(record)  # CC=1
class DeviceRegistry:  # Persistent device registry — stored at ~/.config/redeploy/de
    def get(device_id)  # CC=3
    def upsert(device)  # CC=3
    def remove(device_id)  # CC=3
    def by_tag(tag)  # CC=3
    def by_strategy(strategy)  # CC=3
    def reachable()  # CC=3
    def default_path(cls)  # CC=1
    def load(cls, path)  # CC=5
    def save(path)  # CC=4
```

### `redeploy.discovery` (`redeploy/discovery.py`)

```python
def _scan_known_hosts(ssh_user)  # CC=10, fan=15 ⚠
def _scan_arp_cache()  # CC=10, fan=11 ⚠
def _scan_mdns(timeout)  # CC=7, fan=10
def _ping_sweep(subnet, timeout)  # CC=6, fan=14
def _probe_ssh(hosts, users, port, timeout, max_workers)  # CC=1, fan=6
def _detect_local_subnet()  # CC=9, fan=11
def _merge(hosts)  # CC=10, fan=2 ⚠
def discover(subnet, ssh_users, ssh_port, ping, mdns, probe_ssh, timeout)  # CC=10, fan=15 ⚠
def update_registry(hosts, registry, save)  # CC=14, fan=6 ⚠
def _run(cmd, timeout)  # CC=2, fan=1
def _is_ip(s)  # CC=1, fan=2
def _collect_ssh_keys()  # CC=14, fan=11 ⚠
def _try_ssh_credentials(ip, users, keys, port, timeout)  # CC=10, fan=3 ⚠
def _detect_strategy_remote(host, key, port, timeout)  # CC=26, fan=10 ⚠
def auto_probe(ip_or_host, users, port, timeout, app_hint, save)  # CC=20, fan=18 ⚠
class DiscoveredHost:
class ProbeResult:  # Full autonomous probe result for a single host.
```

### `redeploy.fleet` (`redeploy/fleet.py`)

```python
class DeviceArch:
class Stage:
class DeviceExpectation:  # Declarative assertions about required infrastructure on a de
class FleetDevice:  # Generic device descriptor — superset of ``deploy``'s DeviceC
    def ssh_user()  # CC=2
    def ssh_ip()  # CC=2
    def is_local()  # CC=1
    def is_prod()  # CC=2
    def has_tag(tag)  # CC=1
    def has_expectation(exp)  # CC=1
    def verify_expectations(state)  # CC=25 ⚠
class FleetConfig:  # Top-level fleet manifest — list of devices with stage / tag 
    def get_device(device_id)  # CC=3
    def by_tag(tag)  # CC=3
    def by_stage(stage)  # CC=3
    def by_strategy(strategy)  # CC=3
    def prod_devices()  # CC=1
    def from_file(cls, path, workspace_root)  # CC=13 ⚠
```

## Refactoring Analysis

*Pre-refactoring snapshot — use this section to identify targets. Generated from `project/` toon files.*

### Call Graph & Complexity (`project/calls.toon.yaml`)

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/maskservice/redeploy
# nodes: 12 | edges: 7 | modules: 6
# CC̄=4.3

HUBS[20]:
  redeploy.cli.run
    CC=12  in:0  out:48  total:48
  redeploy.detect.detector.Detector.run
    CC=9  in:0  out:30  total:30
  redeploy.cli.apply
    CC=9  in:0  out:22  total:22
  redeploy.detect.probes.probe_runtime
    CC=5  in:1  out:15  total:16
  redeploy.detect.probes.probe_ports
    CC=6  in:1  out:11  total:12
  redeploy.ssh.SshClient._detect_key
    CC=6  in:1  out:8  total:9
  redeploy.detect.probes.probe_iptables_dnat
    CC=7  in:1  out:5  total:6
  redeploy.models.MigrationSpec.from_file
    CC=1  in:1  out:4  total:5
  redeploy.apply.executor.Executor.from_file
    CC=1  in:1  out:4  total:5
  redeploy.cli.cli
    CC=1  in:0  out:5  total:5
  redeploy.cli._setup_logging
    CC=2  in:1  out:2  total:3
  redeploy.ssh.SshClient._detect_ssh_key
    CC=1  in:0  out:1  total:1

MODULES:
  redeploy.apply.executor  [1 funcs]
    from_file  CC=1  out:4
  redeploy.cli  [4 funcs]
    _setup_logging  CC=2  out:2
    apply  CC=9  out:22
    cli  CC=1  out:5
    run  CC=12  out:48
  redeploy.detect.detector  [1 funcs]
    run  CC=9  out:30
  redeploy.detect.probes  [3 funcs]
    probe_iptables_dnat  CC=7  out:5
    probe_ports  CC=6  out:11
    probe_runtime  CC=5  out:15
  redeploy.models  [1 funcs]
    from_file  CC=1  out:4
  redeploy.ssh  [2 funcs]
    _detect_key  CC=6  out:8
    _detect_ssh_key  CC=1  out:1

EDGES:
  redeploy.detect.detector.Detector.run → redeploy.detect.probes.probe_runtime
  redeploy.detect.detector.Detector.run → redeploy.detect.probes.probe_ports
  redeploy.detect.detector.Detector.run → redeploy.detect.probes.probe_iptables_dnat
  redeploy.ssh.SshClient._detect_ssh_key → redeploy.ssh.SshClient._detect_key
  redeploy.cli.cli → redeploy.cli._setup_logging
  redeploy.cli.apply → redeploy.apply.executor.Executor.from_file
  redeploy.cli.run → redeploy.models.MigrationSpec.from_file
```

### Code Analysis (`project/analysis.toon.yaml`)

```toon markpact:analysis path=project/analysis.toon.yaml
# code2llm | 17f 2084L | python:15,shell:2 | 2026-04-20
# CC̄=4.3 | critical:1/83 | dups:0 | cycles:0

HEALTH[1]:
  🟡 CC    detect CC=16 (limit:15)

REFACTOR[1]:
  1. split 1 high-CC methods  (CC>15)

PIPELINES[66]:
  [1] Src [run]: run
      PURITY: 100% pure
  [2] Src [_plan_conflict_fixes]: _plan_conflict_fixes
      PURITY: 100% pure
  [3] Src [_plan_stop_old_services]: _plan_stop_old_services
      PURITY: 100% pure
  [4] Src [_plan_deploy_new]: _plan_deploy_new
      PURITY: 100% pure
  [5] Src [_plan_docker_full]: _plan_docker_full
      PURITY: 100% pure

LAYERS:
  redeploy/                       CC̄=4.3    ←in:0  →out:4
  │ !! cli                        378L  0C    7m  CC=16     ←0
  │ planner                    310L  1C   18m  CC=8      ←1
  │ probes                     272L  0C    9m  CC=13     ←1
  │ ssh                        271L  4C   16m  CC=7      ←0
  │ models                     271L  15C    3m  CC=4      ←1
  │ executor                   200L  2C   14m  CC=9      ←1
  │ detector                    96L  1C    3m  CC=9      ←0
  │ version                     95L  0C    4m  CC=8      ←0
  │ verify                      92L  1C    7m  CC=8      ←0
  │ data_sync                   45L  0C    2m  CC=7      ←0
  │ __init__                     4L  0C    0m  CC=0.0    ←0
  │ remote                       4L  0C    0m  CC=0.0    ←0
  │ __init__                     4L  0C    0m  CC=0.0    ←0
  │ __init__                     4L  0C    0m  CC=0.0    ←0
  │ __init__                     2L  0C    0m  CC=0.0    ←0
  │
  ./                              CC̄=0.0    ←in:0  →out:0
  │ project.sh                  35L  0C    0m  CC=0.0    ←0
  │ tree.sh                      1L  0C    0m  CC=0.0    ←0
  │

COUPLING:
                        redeploy   redeploy.plan  redeploy.apply
        redeploy              ──               3               1
   redeploy.plan              ←3              ──                
  redeploy.apply              ←1                              ──
  CYCLES: none

EXTERNAL:
  validation: run `vallm batch .` → validation.toon
  duplication: run `redup scan .` → duplication.toon
```

### Duplication (`project/duplication.toon.yaml`)

```toon markpact:analysis path=project/duplication.toon.yaml
# redup/duplication | 0 groups | 20f 5093L | 2026-04-20

SUMMARY:
  files_scanned: 20
  total_lines:   5093
  dup_groups:    0
  dup_fragments: 0
  saved_lines:   0
  scan_ms:       4365
```

### Evolution / Churn (`project/evolution.toon.yaml`)

```toon markpact:analysis path=project/evolution.toon.yaml
# code2llm/evolution | 83 func | 10f | 2026-04-20

NEXT[1] (ranked by impact):
  [1] !  SPLIT-FUNC      detect  CC=16  fan=20
      WHY: CC=16 exceeds 15
      EFFORT: ~1h  IMPACT: 320


RISKS[0]: none

METRICS-TARGET:
  CC̄:          4.3 → ≤3.0
  max-CC:      16 → ≤8
  god-modules: 0 → 0
  high-CC(≥15): 1 → ≤0
  hub-types:   0 → ≤0

PATTERNS (language parser shared logic):
  _extract_declarations() in base.py — unified extraction for:
    - TypeScript: interfaces, types, classes, functions, arrow funcs
    - PHP: namespaces, traits, classes, functions, includes
    - Ruby: modules, classes, methods, requires
    - C++: classes, structs, functions, #includes
    - C#: classes, interfaces, methods, usings
    - Java: classes, interfaces, methods, imports
    - Go: packages, functions, structs
    - Rust: modules, functions, traits, use statements

  Shared regex patterns per language:
    - import: language-specific import/require/using patterns
    - class: class/struct/trait declarations with inheritance
    - function: function/method signatures with visibility
    - brace_tracking: for C-family languages ({ })
    - end_keyword_tracking: for Ruby (module/class/def...end)

  Benefits:
    - Consistent extraction logic across all languages
    - Reduced code duplication (~70% reduction in parser LOC)
    - Easier maintenance: fix once, apply everywhere
    - Standardized FunctionInfo/ClassInfo models

HISTORY:
  (first run — no previous data)
```

### Validation (`project/validation.toon.yaml`)

```toon markpact:analysis path=project/validation.toon.yaml
# vallm batch | 101f | 0✓ 70⚠ 0✗ | 2026-04-20

SUMMARY:
  scanned: 101  passed: 0 (0.0%)  warnings: 70  errors: 0  unsupported: 0

WARNINGS[70]{path,score}:
  redeploy/cli.py,0.68
    issues[4]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
      complexity.lizard_cc,warning,detect: CC=20 exceeds limit 15,72
      complexity.lizard_cc,warning,devices: CC=18 exceeds limit 15,683
      complexity.lizard_cc,warning,probe: CC=27 exceeds limit 15,961
  redeploy/detect/templates.py,0.71
    issues[3]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
      complexity.lizard_cc,warning,build_context: CC=35 exceeds limit 15,87
      complexity.lizard_length,warning,_build_templates: 155 lines exceeds limit 100,179
  redeploy/discovery.py,0.71
    issues[3]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
      complexity.lizard_cc,warning,_detect_strategy_remote: CC=26 exceeds limit 15,476
      complexity.lizard_cc,warning,auto_probe: CC=20 exceeds limit 15,551
  redeploy/fleet.py,0.74
    issues[2]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
      complexity.lizard_cc,warning,verify_expectations: CC=25 exceeds limit 15,133
  redeploy/models.py,0.74
    issues[2]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
      complexity.lizard_cc,warning,apply_to_spec: CC=19 exceeds limit 15,415
  redeploy/parse.py,0.74
    issues[2]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
      complexity.lizard_cc,warning,parse_diagnostics: CC=16 exceeds limit 15,88
  examples/01-vps-version-bump/migration.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/01-vps-version-bump/redeploy.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/02-k3s-to-docker/migration.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/02-k3s-to-docker/redeploy.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/03-docker-to-podman-quadlet/migration.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/03-docker-to-podman-quadlet/redeploy.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/04-rpi-kiosk/migration-rpi5.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/04-rpi-kiosk/migration.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/04-rpi-kiosk/redeploy.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/05-iot-fleet-ota/migration.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/05-iot-fleet-ota/redeploy.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/06-local-dev/migration.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/06-local-dev/redeploy.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/07-staging-to-prod/migration.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/07-staging-to-prod/redeploy.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/08-rollback/migration.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/08-rollback/redeploy.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/09-fleet-yaml/fleet.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/09-fleet-yaml/redeploy.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/10-multienv/dev.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/10-multienv/prod.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/10-multienv/redeploy.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/10-multienv/staging.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/11-traefik-tls/migration.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/11-traefik-tls/redeploy.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/12-ci-pipeline/migration.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/12-ci-pipeline/redeploy.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/13-multi-app-monorepo/fleet.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/13-multi-app-monorepo/migration.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  examples/13-multi-app-monorepo/redeploy.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  goal.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  project.sh,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse BASH: Download error: Language 'BASH' not available for download. Available groups: [""all""]",
  project/calls.yaml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse YAML: Download error: Language 'YAML' not available for download. Available groups: [""all""]",
  pyproject.toml,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse TOML: Download error: Language 'TOML' not available for download. Available groups: [""all""]",
  redeploy/__init__.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/apply/__init__.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/apply/executor.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/data_sync.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/detect/__init__.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/detect/detector.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/detect/probes.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/detect/remote.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/plan/__init__.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/plan/planner.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/ssh.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/steps.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/tests/__init__.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/tests/test_data_sync.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/tests/test_discovery.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/tests/test_examples.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/tests/test_executor.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/tests/test_fleet.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/tests/test_models.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/tests/test_parse.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/tests/test_planner_edge.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/tests/test_probes.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/tests/test_ssh.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/tests/test_verify.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/tests/test_version.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/verify.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  redeploy/version.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/test_parse.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tests/test_redeploy.py,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse PYTHON: Download error: Language 'PYTHON' not available for download. Available groups: [""all""]",
  tree.sh,0.78
    issues[1]{rule,severity,message,line}:
      syntax.unsupported,warning,"Could not parse BASH: Download error: Language 'BASH' not available for download. Available groups: [""all""]",
```

## Intent

Infrastructure migration toolkit: detect → plan → apply

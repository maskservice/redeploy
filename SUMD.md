# redeploy

Infrastructure migration toolkit: detect → plan → apply

## Contents

- [Metadata](#metadata)
- [Architecture](#architecture)
- [Interfaces](#interfaces)
- [Configuration](#configuration)
- [Dependencies](#dependencies)
- [Deployment](#deployment)
- [Environment Variables (`.env.example`)](#environment-variables-envexample)
- [Release Management (`goal.yaml`)](#release-management-goalyaml)
- [Makefile Targets](#makefile-targets)
- [Code Analysis](#code-analysis)
- [Source Map](#source-map)
- [Call Graph](#call-graph)
- [Intent](#intent)

## Metadata

- **name**: `redeploy`
- **version**: `0.2.29`
- **python_requires**: `>=3.11`
- **ai_model**: `openrouter/qwen/qwen3-coder-next`
- **ecosystem**: SUMD + DOQL + testql + taskfile
- **generated_from**: pyproject.toml, Makefile, goal.yaml, .env.example, src(14 mod), project/(2 analysis files)

## Architecture

```
SUMD (description) → DOQL/source (code) → taskfile (automation) → testql (verification)
```

### Source Modules

- `redeploy.audit`
- `redeploy.cli`
- `redeploy.data_sync`
- `redeploy.discovery`
- `redeploy.fleet`
- `redeploy.models`
- `redeploy.observe`
- `redeploy.parse`
- `redeploy.patterns`
- `redeploy.spec_loader`
- `redeploy.ssh`
- `redeploy.steps`
- `redeploy.verify`
- `redeploy.version`

## Interfaces

### CLI Entry Points

- `redeploy`

## Configuration

```yaml
project:
  name: redeploy
  version: 0.2.29
  env: local
```

## Dependencies

### Runtime

```text markpact:deps python
pydantic>=2.0
pyyaml>=6.0
markdown-it-py>=3.0
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

## Deployment

```bash markpact:run
pip install redeploy

# development install
pip install -e .[dev]
```

## Environment Variables (`.env.example`)

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | `*(not set)*` | Required: OpenRouter API key (https://openrouter.ai/keys) |
| `LLM_MODEL` | `openrouter/qwen/qwen3-coder-next` | Model (default: openrouter/qwen/qwen3-coder-next) |
| `PFIX_AUTO_APPLY` | `true` | true = apply fixes without asking |
| `PFIX_AUTO_INSTALL_DEPS` | `true` | true = auto pip/uv install |
| `PFIX_AUTO_RESTART` | `false` | true = os.execv restart after fix |
| `PFIX_MAX_RETRIES` | `3` |  |
| `PFIX_DRY_RUN` | `false` |  |
| `PFIX_ENABLED` | `true` |  |
| `PFIX_GIT_COMMIT` | `false` | true = auto-commit fixes |
| `PFIX_GIT_PREFIX` | `pfix:` | commit message prefix |
| `PFIX_CREATE_BACKUPS` | `false` | false = disable .pfix_backups/ directory |

## Release Management (`goal.yaml`)

- **versioning**: `semver`
- **commits**: `conventional` scope=`redeploy`
- **changelog**: `keep-a-changelog`
- **build strategies**: `python`, `nodejs`, `rust`
- **version files**: `VERSION`, `pyproject.toml:version`, `redeploy/__init__.py:__version__`

## Makefile Targets

- `PYTHON`
- `VENV`
- `BIN`
- `PIP`
- `PYTEST`
- `RUFF`
- `REDEPLOY`
- `help` — ── help ──────────────────────────────────────────────────────────────────────
- `install` — ── setup ─────────────────────────────────────────────────────────────────────
- `test` — ── dev ───────────────────────────────────────────────────────────────────────
- `lint`
- `fmt`
- `check`
- `run` — ── run (single spec file) ────────────────────────────────────────────────────
- `run-dry`
- `run-plan`
- `run-detect`
- `detect` — ── detect / plan / apply ─────────────────────────────────────────────────────
- `plan`
- `apply`
- `dry-run`
- `migrate`
- `push` — ── git / release ─────────────────────────────────────────────────────────────
- `tag`
- `release`
- `clean` — ── clean ─────────────────────────────────────────────────────────────────────

## Code Analysis

### `project/map.toon.yaml`

```toon markpact:analysis path=project/map.toon.yaml
# redeploy | 17f 2084L | shell:2,python:15 | 2026-04-20
# stats: 83 func | 0 cls | 17 mod | CC̄=4.3 | critical:1 | cycles:0
# alerts[5]: fan-out run=26; fan-out detect=20; fan-out migrate=20; fan-out Detector.run=19; fan-out plan=18
# hotspots[5]: run fan=26; detect fan=20; migrate fan=20; Detector.run fan=19; plan fan=18
# evolution: baseline
# Keys: M=modules, D=details, i=imports, e=exports, c=classes, f=functions, m=methods
M[17]:
  project.sh,35
  redeploy/__init__.py,2
  redeploy/apply/__init__.py,4
  redeploy/apply/executor.py,200
  redeploy/cli.py,378
  redeploy/data_sync.py,45
  redeploy/detect/__init__.py,4
  redeploy/detect/detector.py,96
  redeploy/detect/probes.py,272
  redeploy/detect/remote.py,4
  redeploy/models.py,271
  redeploy/plan/__init__.py,4
  redeploy/plan/planner.py,310
  redeploy/ssh.py,271
  redeploy/verify.py,92
  redeploy/version.py,95
  tree.sh,1
D:
  redeploy/cli.py:
    e: _setup_logging,cli,detect,plan,apply,migrate,run
    _setup_logging(verbose)
    cli(ctx;verbose)
    detect(ctx;host;app;domain;output)
    plan(ctx;infra;target;strategy;domain;target_version;compose;env_file;output)
    apply(ctx;plan_file;dry_run;step;output)
    migrate(ctx;host;app;domain;target;strategy;target_version;compose;env_file;dry_run;infra_out;plan_out)
    run(ctx;spec_file;dry_run;plan_only;do_detect;plan_out;output)
  redeploy/detect/probes.py:
    e: probe_runtime,probe_ports,probe_iptables_dnat,probe_docker_services,probe_k3s_services,probe_systemd_services,probe_health,detect_conflicts,detect_strategy
    probe_runtime(p)
    probe_ports(p)
    probe_iptables_dnat(p;ports)
    probe_docker_services(p)
    probe_k3s_services(p;namespaces)
    probe_systemd_services(p;app)
    probe_health(host;app;domain)
    detect_conflicts(ports;iptables_dnat;runtime;docker_services;k3s_services)
    detect_strategy(runtime;docker_services;k3s_services;systemd_services)
  redeploy/detect/detector.py:
    e: Detector
    Detector: __init__(3),run(0),save(2)  # Probe infrastructure and produce InfraState...
  redeploy/apply/executor.py:
    e: StepError,Executor
    StepError(Exception): __init__(2)
    Executor: __init__(2),run(0),_execute_step(1),_run_ssh(1),_run_scp(1),_run_rsync(1),_run_http_check(3),_run_version_check(1),_run_wait(1),_rollback(0),summary(0),from_file(0),save_results(1)  # Execute MigrationPlan steps on a remote host...
  redeploy/plan/planner.py:
    e: Planner
    Planner: __init__(2),run(0),_plan_conflict_fixes(0),_plan_stop_old_services(0),_plan_deploy_new(0),_plan_docker_full(0),_plan_podman_quadlet(0),_plan_systemd(0),_plan_verify(0),_compose_cmd(0),_compose_file(0),_add_step(1),_assess_risk(0),_estimate_downtime(0),from_files(1),from_spec(0),_append_extra_steps(1),save(2)  # Generate a MigrationPlan from detected infra + desired targe...
  redeploy/version.py:
    e: read_local_version,read_remote_version,check_version,check_version_http
    read_local_version(workspace_root;app)
    read_remote_version(remote;remote_dir;app)
    check_version(local;remote)
    check_version_http(base_url;expected_version;timeout)
  redeploy/verify.py:
    e: VerifyContext,verify_data_integrity
    VerifyContext: check(5),add_pass(1),add_fail(2),add_warn(1),add_info(1),summary(0)  # Accumulates check results during verification...
    verify_data_integrity(ctx;local_counts;remote_counts)
  redeploy/ssh.py:
    e: SshResult,SshClient,RemoteProbe,RemoteExecutor
    SshResult:
    SshClient: __init__(4),key(1),key(1),run(2),rsync(5),scp(3),is_reachable(1),is_ssh_ready(0),ping(0),_run_local(2),_ssh_opts(0),_scp_opts(0),_detect_ssh_key(-1),_detect_key(-1)  # Execute commands on a remote host via SSH (or locally).

Arg...
    RemoteProbe(SshClient): __init__(1),is_local(1),is_local(1)  # Thin wrapper kept for redeploy.detect compatibility.

``Remo...
    RemoteExecutor(SshClient): __init__(1)  # Thin wrapper kept for deploy.core compatibility.

``RemoteEx...
  redeploy/data_sync.py:
    e: collect_sqlite_counts,rsync_timeout_for_path
    collect_sqlite_counts(app_root;db_specs)
    rsync_timeout_for_path(path;minimum;base;per_mb)
  redeploy/models.py:
    e: ConflictSeverity,StepAction,StepStatus,DeployStrategy,ServiceInfo,PortInfo,ConflictInfo,RuntimeInfo,AppHealthInfo,InfraState,TargetConfig,MigrationStep,InfraSpec,MigrationSpec,MigrationPlan
    ConflictSeverity(str,Enum):
    StepAction(str,Enum):
    StepStatus(str,Enum):
    DeployStrategy(str,Enum):
    ServiceInfo(BaseModel):
    PortInfo(BaseModel):
    ConflictInfo(BaseModel):
    RuntimeInfo(BaseModel):
    AppHealthInfo(BaseModel):
    InfraState(BaseModel):  # Full detected state of infrastructure — output of `detect`...
    TargetConfig(BaseModel):  # Desired infrastructure state — input to `plan`...
    MigrationStep(BaseModel):
    InfraSpec(BaseModel):  # Declarative description of one infrastructure state (from OR...
    MigrationSpec(BaseModel): from_file(1),to_infra_state(0),to_target_config(0)  # Single YAML file describing full migration: from-state → to-...
    MigrationPlan(BaseModel):  # Full migration plan — output of `plan`, input to `apply`...
  project.sh:
  tree.sh:
  redeploy/apply/__init__.py:
  redeploy/detect/remote.py:
  redeploy/plan/__init__.py:
  redeploy/__init__.py:
  redeploy/detect/__init__.py:
```

## Source Map

*Top 5 modules by symbol density — signatures for LLM orientation.*

### `redeploy.audit` (`redeploy/audit.py`)

```python
def _extract_port(url)  # CC=5, fan=5
def _normalize_path(path)  # CC=3, fan=4
def _strip_remote_dir(path)  # CC=5, fan=3
def audit_spec(spec_path)  # CC=1, fan=3
class AuditCheck:  # Outcome of a single audit probe.
    def ok()  # CC=1
class AuditReport:
    def add(check)  # CC=1
    def passed()  # CC=3
    def failed()  # CC=3
    def warned()  # CC=3
    def skipped()  # CC=3
    def ok()  # CC=1
    def summary()  # CC=1
    def to_dict()  # CC=2
class _Expect:
    def extras()  # CC=1
class _Extractor:  # Walk a MigrationSpec and emit Expect tuples.
    def __init__(spec)  # CC=4
    def collect()  # CC=4
    def _from_target()  # CC=7
    def _from_step(raw)  # CC=12 ⚠
    def _from_command(cmd, sid)  # CC=14 ⚠
class _Probe:  # Thin wrapper around SshClient with sensible audit timeouts.
    def __init__(client)  # CC=4
    def has_binary(name)  # CC=3
    def has_path(path)  # CC=3
    def port_listening(port)  # CC=4
    def has_image(ref)  # CC=4
    def has_systemd_unit(unit)  # CC=4
    def apt_package(name)  # CC=3
    def disk_free_gib(path)  # CC=3
class Auditor:  # Compare a MigrationSpec's expectations against a live target
    def __init__(spec, spec_path)  # CC=4
    def run()  # CC=5
    def _dispatch(exp, report)  # CC=1
    def _probe_one(exp)  # CC=10 ⚠
    def _probe_binary(exp)  # CC=4
    def _probe_directory(exp)  # CC=4
    def _probe_file(exp)  # CC=4
    def _probe_local_file(exp)  # CC=3
    def _probe_port_listening(exp)  # CC=4
    def _probe_container_image(exp)  # CC=4
    def _probe_systemd_unit(exp, user)  # CC=4
    def _probe_apt_package(exp)  # CC=4
```

### `redeploy.observe` (`redeploy/observe.py`)

```python
class AuditEntry:  # Single audit log entry — immutable snapshot of one deploymen
    def __init__(data)  # CC=1
    def ts()  # CC=1
    def host()  # CC=1
    def app()  # CC=1
    def from_strategy()  # CC=1
    def to_strategy()  # CC=1
    def ok()  # CC=1
    def elapsed_s()  # CC=1
    def steps_total()  # CC=1
    def steps_ok()  # CC=1
    def steps_failed()  # CC=1
    def pattern()  # CC=1
    def version()  # CC=1
    def dry_run()  # CC=1
    def steps()  # CC=1
    def error()  # CC=1
    def to_dict()  # CC=1
    def __repr__()  # CC=2
class DeployAuditLog:  # Persistent audit log — newline-delimited JSON at ``path``.
    def __init__(path)  # CC=1
    def record(plan, completed_steps)  # CC=11 ⚠
    def _append(entry)  # CC=1
    def load(limit)  # CC=5
    def tail(n)  # CC=1
    def filter(host, app, ok, since)  # CC=12 ⚠
    def clear()  # CC=2
class DeployReport:  # Human-readable post-deploy report from an AuditEntry.
    def __init__(entry)  # CC=1
    def text()  # CC=8
    def yaml()  # CC=1
    def summary_line()  # CC=2
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
    def from_file(cls, path, workspace_root)  # CC=1
class Fleet:  # Unified first-class fleet — wraps FleetConfig and/or DeviceR
    def __init__(devices)  # CC=1
    def from_file(cls, path)  # CC=1
    def from_registry(cls, path)  # CC=6
    def from_config(cls, config)  # CC=1
    def devices()  # CC=1
    def get(device_id)  # CC=3
    def by_tag(tag)  # CC=3
    def by_stage(stage)  # CC=3
    def by_strategy(strategy)  # CC=3
    def prod()  # CC=1
    def reachable(within_seconds)  # CC=5
    def merge(other)  # CC=3
    def __len__()  # CC=1
    def __iter__()  # CC=1
    def __repr__()  # CC=1
```

### `redeploy.discovery` (`redeploy/discovery.py`)

```python
def _is_raspberry_pi_mac(mac)  # CC=2, fan=1
def _scan_known_hosts(ssh_user)  # CC=10, fan=15 ⚠
def _scan_arp_cache()  # CC=10, fan=12 ⚠
def _scan_mdns(timeout)  # CC=7, fan=10
def _ping_sweep(subnet, timeout)  # CC=6, fan=14
def _probe_ssh(hosts, users, port, timeout, max_workers)  # CC=1, fan=6
def _detect_local_subnet()  # CC=9, fan=11
def _merge(hosts)  # CC=11, fan=2 ⚠
def discover(subnet, ssh_users, ssh_port, ping, mdns, probe_ssh, timeout)  # CC=14, fan=16 ⚠
def update_registry(hosts, registry, save)  # CC=17, fan=7 ⚠
def _run(cmd, timeout)  # CC=2, fan=1
def _is_ip(s)  # CC=1, fan=2
def _collect_ssh_keys()  # CC=14, fan=11 ⚠
def _tcp_reachable(ip, port, timeout)  # CC=2, fan=1
def _try_ssh_credentials(ip, users, keys, port, timeout)  # CC=14, fan=12 ⚠
def _detect_strategy_remote(host, key, port, timeout)  # CC=3, fan=5
def _build_probe_command()  # CC=1, fan=0
def _build_ssh_command(host, port, timeout, key_opts, probe_cmd)  # CC=1, fan=1
def _run_ssh_probe(cmd, timeout)  # CC=3, fan=1
def _parse_probe_output(out)  # CC=16, fan=6 ⚠
def _infer_strategy(info, services)  # CC=8, fan=2
def _parse_probe_input(ip_or_host, users)  # CC=4, fan=1
def _detect_app_from_services(services, app_hint)  # CC=5, fan=1
def _update_existing_device(existing, result, ssh_user, ssh_key, ip, host_str, port, now)  # CC=5, fan=0
def _create_new_device(result, ssh_user, ssh_key, ip, host_str, port, now)  # CC=2, fan=1
def auto_probe(ip_or_host, users, port, timeout, app_hint, save)  # CC=7, fan=19
class DiscoveredHost:
class ProbeResult:  # Full autonomous probe result for a single host.
```

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

## Call Graph

*12 nodes · 7 edges · 6 modules · CC̄=4.3*

### Hubs (by degree)

| Function | CC | in | out | total |
|----------|----|----|-----|-------|
| `run` *(in redeploy.cli)* | 12 ⚠ | 0 | 48 | **48** |
| `run` *(in redeploy.detect.detector.Detector)* | 9 | 0 | 30 | **30** |
| `apply` *(in redeploy.cli)* | 9 | 0 | 22 | **22** |
| `probe_runtime` *(in redeploy.detect.probes)* | 5 | 1 | 15 | **16** |
| `probe_ports` *(in redeploy.detect.probes)* | 6 | 1 | 11 | **12** |
| `_detect_key` *(in redeploy.ssh.SshClient)* | 6 | 1 | 8 | **9** |
| `probe_iptables_dnat` *(in redeploy.detect.probes)* | 7 | 1 | 5 | **6** |
| `from_file` *(in redeploy.models.MigrationSpec)* | 1 | 1 | 4 | **5** |

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

## Intent

Infrastructure migration toolkit: detect → plan → apply

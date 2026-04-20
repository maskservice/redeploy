# Markpact Implementation Plan

Status: Phase 0 and the Phase 1 MVP are now implemented. The remaining
sections are still useful as the roadmap for unsupported block kinds and
runtime features.

## Goal

Add real support for `redeploy run migration.md` without replacing the current
YAML-based planner and executor.

The minimal viable path is:

`migration.md` -> parsed markpact document -> compiled `MigrationSpec` -> existing planner -> existing executor

This keeps YAML as the reference runtime and treats markdown as another input
format, not as a second deployment engine.

## Constraints From Current Code

- `redeploy run` now loads specs through `redeploy.spec_loader.load_migration_spec()`.
- YAML remains the reference input format; `.md` currently supports only the
  Phase 1 markpact subset.
- `MigrationStep` supports `timeout` and `rollback_command`, but not
  `retry`, `when`, `skip_if`, or `check_cmd`.
- the executor already supports planning, apply, rollback, audit logging, and
  progress output for the compiled YAML-shaped flow.
- most of `examples/md/` still contain prototype semantics that are broader than
  the implemented runtime.

## Non-Goals For MVP

Do not include these in the first implementation:

- arbitrary execution of `markpact:python`
- arbitrary execution of `markpact:bash` or `markpact:shell`
- a separate standalone `markpact` CLI
- persistent execution state such as `.deploy-state.json`
- persistent SSH/session pooling redesign
- one-to-one support for every field currently shown in `examples/md/`

These are valid future stages, but they should not block `redeploy run migration.md`.

## Proposed Architecture

### 1. Introduce a spec loader abstraction

Add a single entry point responsible for loading deployment specs by file type.

Suggested interface:

```python
def load_migration_spec(path: Path) -> MigrationSpec:
    ...
```

Behavior:

- `.yaml` and `.yml`: existing YAML path
- `.md`: markpact parser plus compiler
- anything else: explicit unsupported format error

This isolates the new behavior from the CLI and avoids scattering suffix checks
 across multiple commands.

### 2. Parse markdown via AST, not regex

Use an AST-capable markdown parser such as `markdown-it-py`.

Why:

- fenced blocks are the core unit of markpact
- AST parsing is safer and less brittle than regex against full markdown
- source line information can be preserved for diagnostics

Supported fenced block kinds in the first pass:

- `markpact:config`
- `markpact:steps`

Supported payload formats in the first pass:

- YAML
- TOML
- JSON

Ignored but detected in the first pass:

- `markpact:python`
- `markpact:bash`
- `markpact:shell`
- `markpact:run`
- `markpact:rollback`

For ignored kinds, the compiler should fail with a clear unsupported-block
 error rather than silently dropping behavior.

### 3. Compile parsed blocks into the existing model

The compiler should output a plain dictionary that already matches the current
 `MigrationSpec` schema.

Minimal mapping rules:

- merge `markpact:config` blocks into the top-level migration spec mapping
- append `markpact:steps` blocks into `extra_steps`
- preserve `name`, `description`, `source`, `target`, `notes`, and `extra_steps`
- validate the compiled mapping by constructing `MigrationSpec`

Important rule:

- markdown compilation should not bypass existing validation

That means the compiler emits a dictionary and then relies on Pydantic through
 `MigrationSpec(...)` to catch invalid shapes.

## Phased Delivery

## Phase 0: Refactor the current load path

Deliverable:

- replace direct `MigrationSpec.from_file(path)` calls in CLI entry points with
  `load_migration_spec(path)`

Success criteria:

- no behavior change for YAML
- existing YAML tests remain green

## Phase 1: Add markpact parser and compiler MVP

Deliverable:

- parse markdown fenced blocks via AST
- support `markpact:config` and `markpact:steps`
- compile them into `MigrationSpec`

Success criteria:

- `redeploy run migration.md --plan-only` works for a simple markdown fixture
- invalid block formats fail with line-aware error messages

## Phase 2: Wire CLI and tests

Deliverable:

- `redeploy run migration.md`
- `redeploy run migration.md --plan-only`
- `redeploy run migration.md --dry-run`

Success criteria:

- markdown uses the same planner and executor as YAML
- error output clearly distinguishes parser errors from schema errors

## Phase 3: Parity-first example rollout

Do not try to migrate all markdown examples at once.

Start with one grounded scenario that already exists in YAML, for example:

- `01-vps-version-bump`

Deliverable:

- one markdown example that compiles to the same effective `MigrationSpec` as
  its YAML counterpart

Success criteria:

- plan shape is equivalent enough to compare key steps
- CLI test proves `.yaml` and `.md` versions both plan successfully

## Phase 4: Add minimal runtime extensions needed by examples

Only after MVP works should the runtime grow new semantics.

Recommended order:

1. `retry`
2. `skip_if`
3. `when`
4. `check_cmd`

Why this order:

- `retry` is self-contained in the executor
- `skip_if` and `when` need predicate evaluation but not full state tracking
- `check_cmd` implies a more opinionated idempotency model and should come last

Scope guidance:

- keep predicates allowlisted
- do not evaluate arbitrary shell expressions in v1
- start with a very small predicate set such as `file_exists`, `dir_exists`,
  `step_completed`, and one or two Docker-oriented checks

## Phase 5: Advanced block kinds

Only after the compiled markdown flow is stable should these be considered:

- `markpact:rollback`
- `markpact:run`
- `markpact:python`
- `markpact:bash`

Recommended approach:

- `markpact:rollback`: compile into per-step rollback metadata or dedicated
  rollback sections in an intermediate document model
- `markpact:run`: compile to a final verification step once a safe local action
  model exists
- `markpact:python` and `markpact:bash`: do not execute raw code directly in
  the first implementation; if needed later, bridge through the existing
  `dsl_python` subsystem or a sandboxed runner

## Suggested File Layout

Suggested new modules:

- `redeploy/redeploy/spec_loader.py`
- `redeploy/redeploy/markpact/__init__.py`
- `redeploy/redeploy/markpact/parser.py`
- `redeploy/redeploy/markpact/compiler.py`
- `redeploy/redeploy/markpact/models.py`

Suggested updates:

- `redeploy/redeploy/cli.py`
- `redeploy/redeploy/models.py`

Suggested tests:

- `redeploy/redeploy/tests/test_markpact_parser.py`
- `redeploy/redeploy/tests/test_markpact_compiler.py`
- `redeploy/redeploy/tests/test_markpact_cli.py`

## Test Strategy

### Parser tests

- detects fenced `markpact:*` blocks correctly
- preserves order
- preserves source location information
- rejects malformed fences cleanly

### Compiler tests

- merges multiple config blocks
- appends multiple steps blocks
- validates YAML, TOML, and JSON payloads
- reports unsupported block kinds explicitly

### CLI tests

- `.yaml` behavior unchanged
- `.md` works through `redeploy run --plan-only`
- `.md` works through `redeploy run --dry-run`
- unsupported block kinds fail with actionable errors

### Parity tests

- selected `.md` example compiles to the same high-level spec as its YAML peer
- generated plan contains the expected step ids and actions

## Acceptance Criteria

The MVP is done when all of the following are true:

- `redeploy run migration.md --plan-only` works for at least one real example
- markdown goes through the same planner and executor path as YAML
- unsupported blocks fail loudly and early
- YAML behavior is unchanged
- repository tests cover both parser/compiler and CLI integration

## Why This Plan Is Minimal And Safe

- it reuses the current planner and executor instead of replacing them
- it avoids unsafe arbitrary code execution in phase one
- it narrows markdown support to a compilable subset first
- it keeps YAML as the stable reference implementation
- it creates a clean seam for later features instead of baking markdown logic
  into every part of the runtime

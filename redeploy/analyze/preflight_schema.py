"""Operational preflight schema generation for redeploy runs.

Produces a machine-readable snapshot before apply:
- resolved step graph (ordering refs, command refs)
- local artifact existence checks
- optional remote path probes (best-effort)
- blockers suitable for fail-fast gating
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

import yaml

from ..ssh import SshClient
from .spec_analyzer import AnalysisResult, IssueSeverity


@dataclass
class PreflightResult:
    schema: dict[str, Any]
    blockers: list[dict[str, Any]]

    @property
    def has_blockers(self) -> bool:
        return bool(self.blockers)


def generate_preflight_schema(
    *,
    spec_path: Path,
    spec,
    migration,
    lint_result: AnalysisResult | None,
    base_dir: Path,
    remote_check: bool = True,
) -> PreflightResult:
    blockers: list[dict[str, Any]] = []

    lint_issues = []
    if lint_result is not None:
        for issue in lint_result.issues:
            lint_issues.append({
                "severity": issue.severity.value,
                "category": issue.category,
                "step_id": issue.step_id,
                "message": issue.message,
                "suggestion": issue.suggestion,
            })
            if issue.severity == IssueSeverity.ERROR:
                blockers.append({
                    "type": "lint_error",
                    "step_id": issue.step_id,
                    "message": issue.message,
                })

    command_refs = _resolve_command_refs(spec, spec_path, blockers)
    local_artifacts = _collect_local_artifacts(spec, base_dir, blockers)

    remote = {
        "enabled": bool(remote_check),
        "host": migration.host,
        "reachable": None,
        "checks": [],
    }
    if remote_check:
        remote = _collect_remote_checks(spec, migration.host)

    schema = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "spec": {
            "path": str(spec_path),
            "name": getattr(spec, "name", ""),
            "source_strategy": spec.source.strategy.value,
            "target_strategy": spec.target.strategy.value,
            "host": spec.source.host,
        },
        "plan": {
            "steps_total": len(migration.steps),
            "risk": migration.risk.value,
            "estimated_downtime": migration.estimated_downtime,
            "steps": [
                {
                    "id": s.id,
                    "action": s.action.value,
                    "description": s.description,
                    "has_command_ref": bool(getattr(s, "command_ref", None)),
                    "insert_before": getattr(s, "insert_before", None),
                }
                for s in migration.steps
            ],
        },
        "checks": {
            "lint": {
                "enabled": lint_result is not None,
                "errors": len(lint_result.errors()) if lint_result else 0,
                "warnings": len(lint_result.warnings()) if lint_result else 0,
                "issues": lint_issues,
            },
            "command_refs": command_refs,
            "local_artifacts": local_artifacts,
            "remote": remote,
        },
        "blockers": blockers,
        "summary": {
            "blockers": len(blockers),
            "local_missing": sum(1 for x in local_artifacts if not x["exists"]),
            "refs_missing": sum(1 for x in command_refs if not x["resolved"]),
            "remote_failed_checks": sum(1 for x in remote.get("checks", []) if x.get("ok") is False),
        },
    }

    return PreflightResult(schema=schema, blockers=blockers)


def save_preflight_schema(schema: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(schema, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _resolve_command_refs(spec, spec_path: Path, blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from ..markpact.parser import extract_script_by_ref, extract_script_from_markdown

    out: list[dict[str, Any]] = []
    for step in spec.extra_steps:
        sid = step.get("id")
        cref = step.get("command_ref")
        if not cref:
            continue

        entry = {
            "step_id": sid,
            "command_ref": cref,
            "file": None,
            "ref": None,
            "resolved": False,
            "mode": None,
        }

        if "#" in cref:
            file_part, ref_id = cref.split("#", 1)
            ref_file = (spec_path.parent / file_part).resolve() if file_part else spec_path.resolve()
            entry["file"] = str(ref_file)
            entry["ref"] = ref_id
            if not ref_file.exists():
                out.append(entry)
                blockers.append({
                    "type": "missing_command_ref_file",
                    "step_id": sid,
                    "message": f"command_ref file missing: {file_part}",
                })
                continue
            text = ref_file.read_text(encoding="utf-8", errors="replace")
            by_ref = extract_script_by_ref(text, ref_id, language="bash")
            by_heading = extract_script_from_markdown(text, ref_id, language="bash")
            if by_ref is not None:
                entry["resolved"] = True
                entry["mode"] = "markpact_ref"
            elif by_heading is not None:
                entry["resolved"] = True
                entry["mode"] = "heading"
            else:
                blockers.append({
                    "type": "missing_command_ref",
                    "step_id": sid,
                    "message": f"command_ref '#{ref_id}' not found in {ref_file}",
                })
            out.append(entry)
            continue

        # Simple ref id in current spec markdown.
        ref_file = spec_path.resolve()
        entry["file"] = str(ref_file)
        entry["ref"] = cref
        text = ref_file.read_text(encoding="utf-8", errors="replace") if ref_file.exists() else ""
        by_ref = extract_script_by_ref(text, cref, language="bash")
        by_heading = extract_script_from_markdown(text, cref, language="bash")
        if by_ref is not None:
            entry["resolved"] = True
            entry["mode"] = "markpact_ref"
        elif by_heading is not None:
            entry["resolved"] = True
            entry["mode"] = "heading"
        else:
            blockers.append({
                "type": "missing_command_ref",
                "step_id": sid,
                "message": f"command_ref '{cref}' not found in {ref_file}",
            })
        out.append(entry)

    return out


def _collect_local_artifacts(spec, base_dir: Path, blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: dict[tuple[str, str], dict[str, Any]] = {}

    def add(path_raw: str, kind: str, step_id: str | None):
        key = (kind, path_raw)
        if key not in items:
            resolved = _resolve_local_path(path_raw, base_dir)
            exists = resolved.exists() if resolved is not None else False
            items[key] = {
                "kind": kind,
                "path": path_raw,
                "resolved": str(resolved) if resolved else None,
                "exists": bool(exists),
                "steps": [],
            }
            if not exists and kind in {"src", "config_file", "env_file"}:
                blockers.append({
                    "type": "missing_local_artifact",
                    "step_id": step_id,
                    "message": f"Missing local {kind}: {path_raw}",
                })
        if step_id and step_id not in items[key]["steps"]:
            items[key]["steps"].append(step_id)

    # target-level env file
    target_env = getattr(spec.target, "env_file", None) or getattr(spec.source, "env_file", None)
    if target_env:
        add(str(target_env), "env_file", None)

    for step in spec.extra_steps:
        sid = step.get("id")
        for field in ("src", "config_file"):
            val = step.get(field)
            if val:
                add(str(val), field, sid)

    return sorted(items.values(), key=lambda x: (x["kind"], x["path"]))


def _collect_remote_checks(spec, host: str) -> dict[str, Any]:
    probe = SshClient(host)
    reachable = probe.is_reachable(timeout=10)
    out = {
        "enabled": True,
        "host": host,
        "reachable": reachable,
        "checks": [],
    }
    if not reachable:
        out["checks"].append({
            "type": "ssh_reachability",
            "ok": False,
            "message": f"Cannot reach host via SSH: {host}",
        })
        return out

    # Best-effort path checks for common remote dependencies in commands.
    remote_paths: set[str] = set()
    path_re = re.compile(r"(~\/[^\s'\";&|)]+|\/home\/[^\s'\";&|)]+)")
    for step in spec.extra_steps:
        cmd = step.get("command") or ""
        for m in path_re.finditer(cmd):
            remote_paths.add(m.group(1).rstrip("/"))

    for p in sorted(remote_paths):
        cmd = f"test -e {p}"
        r = probe.run(cmd, timeout=20)
        out["checks"].append({
            "type": "remote_path_exists",
            "path": p,
            "ok": bool(r.ok),
            "message": "exists" if r.ok else (r.stderr or "missing"),
        })

    return out


def _resolve_local_path(val: str, base_dir: Path) -> Path | None:
    val = val.strip()
    if re.search(r"^[\w.-]+@", val):
        return None
    if val.startswith("~/"):
        return Path.home() / val[2:]
    if val.startswith("/"):
        return Path(val)
    return (base_dir / val).resolve()

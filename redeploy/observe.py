"""Observability — structured audit log and deploy reports (Phase 5).

``DeployAuditLog``
    Persists every deployment event to ``~/.config/redeploy/audit.jsonl``
    (newline-delimited JSON, one record per line).  Supports tail, filter
    and export.

``DeployReport``
    Human-readable post-deploy summary with step table and timing.
    Can render as plain text or YAML (for CI pipelines).

Usage::

    from redeploy.observe import DeployAuditLog, DeployReport
    from redeploy import Executor

    log = DeployAuditLog()
    plan = planner.run()
    executor = Executor(plan)
    ok = executor.run()
    entry = log.record(plan, executor.completed_steps, ok=ok)
    print(DeployReport(entry).text())
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ── AuditEntry ────────────────────────────────────────────────────────────────


class AuditEntry:
    """Single audit log entry — immutable snapshot of one deployment."""

    def __init__(self, data: dict) -> None:
        self._d = data

    # ── accessors ─────────────────────────────────────────────────────────────

    @property
    def ts(self) -> str:
        return self._d.get("ts", "")

    @property
    def host(self) -> str:
        return self._d.get("host", "")

    @property
    def app(self) -> str:
        return self._d.get("app", "")

    @property
    def from_strategy(self) -> str:
        return self._d.get("from_strategy", "")

    @property
    def to_strategy(self) -> str:
        return self._d.get("to_strategy", "")

    @property
    def ok(self) -> bool:
        return bool(self._d.get("ok", False))

    @property
    def elapsed_s(self) -> float:
        return float(self._d.get("elapsed_s", 0.0))

    @property
    def steps_total(self) -> int:
        return int(self._d.get("steps_total", 0))

    @property
    def steps_ok(self) -> int:
        return int(self._d.get("steps_ok", 0))

    @property
    def steps_failed(self) -> int:
        return int(self._d.get("steps_failed", 0))

    @property
    def pattern(self) -> Optional[str]:
        return self._d.get("pattern")

    @property
    def version(self) -> Optional[str]:
        return self._d.get("version")

    @property
    def dry_run(self) -> bool:
        return bool(self._d.get("dry_run", False))

    @property
    def steps(self) -> list[dict]:
        return list(self._d.get("steps", []))

    @property
    def error(self) -> Optional[str]:
        return self._d.get("error")

    def to_dict(self) -> dict:
        return dict(self._d)

    def __repr__(self) -> str:
        status = "ok" if self.ok else "FAIL"
        return (
            f"AuditEntry({self.ts} {self.host} {self.app} "
            f"{self.from_strategy}→{self.to_strategy} [{status}] "
            f"{self.steps_ok}/{self.steps_total} steps {self.elapsed_s:.1f}s)"
        )


# ── DeployAuditLog ────────────────────────────────────────────────────────────


class DeployAuditLog:
    """Persistent audit log — newline-delimited JSON at ``path``.

    Default path: ``~/.config/redeploy/audit.jsonl``
    Each line is one JSON object (AuditEntry dict).
    """

    DEFAULT_PATH = Path.home() / ".config" / "redeploy" / "audit.jsonl"

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or self.DEFAULT_PATH

    # ── write ─────────────────────────────────────────────────────────────────

    def record(
        self,
        plan,                            # MigrationPlan
        completed_steps: list,           # list[MigrationStep]
        *,
        ok: bool,
        elapsed_s: float = 0.0,
        dry_run: bool = False,
    ) -> AuditEntry:
        """Build and persist an AuditEntry from a finished plan + steps."""
        all_steps = list(plan.steps)
        failed = [s for s in all_steps if hasattr(s, "status") and
                  str(s.status).endswith("FAILED")]
        failed_id = failed[0].id if failed else None
        failed_err = getattr(failed[0], "error", None) if failed else None

        data: dict = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "host": plan.host,
            "app": plan.app,
            "from_strategy": plan.from_strategy.value,
            "to_strategy": plan.to_strategy.value,
            "ok": ok,
            "dry_run": dry_run,
            "elapsed_s": round(elapsed_s, 2),
            "steps_total": len(all_steps),
            "steps_ok": len(completed_steps),
            "steps_failed": 0 if ok else (len(all_steps) - len(completed_steps)),
            "pattern": getattr(plan, "pattern", None),
            "version": plan.app,   # best proxy; plan doesn't carry version directly
        }
        if not ok and failed_id:
            data["error"] = f"[{failed_id}] {failed_err or 'step failed'}"

        data["steps"] = [
            {
                "id": s.id,
                "action": s.action.value,
                "status": str(s.status).split(".")[-1].lower(),
                "result": getattr(s, "result", None),
                "error": getattr(s, "error", None),
            }
            for s in all_steps
        ]

        entry = AuditEntry(data)
        self._append(entry)
        return entry

    def _append(self, entry: AuditEntry) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    # ── read ──────────────────────────────────────────────────────────────────

    def load(self, limit: int = 100) -> list[AuditEntry]:
        """Return up to *limit* most-recent entries (newest last)."""
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        entries: list[AuditEntry] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(AuditEntry(json.loads(line)))
            except json.JSONDecodeError:
                continue
        return entries[-limit:]

    def tail(self, n: int = 10) -> list[AuditEntry]:
        """Return the *n* most-recent entries."""
        return self.load(limit=n)

    def filter(
        self,
        host: Optional[str] = None,
        app: Optional[str] = None,
        ok: Optional[bool] = None,
        since: Optional[datetime] = None,
    ) -> list[AuditEntry]:
        """Filter entries by host, app, ok status and/or timestamp."""
        entries = self.load(limit=10_000)
        result: list[AuditEntry] = []
        for e in entries:
            if host and host not in e.host:
                continue
            if app and app != e.app:
                continue
            if ok is not None and e.ok != ok:
                continue
            if since:
                try:
                    ts = datetime.fromisoformat(e.ts)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if ts < since:
                        continue
                except ValueError:
                    continue
            result.append(e)
        return result

    def clear(self) -> None:
        """Truncate the audit log (irreversible)."""
        if self.path.exists():
            self.path.write_text("", encoding="utf-8")


# ── DeployReport ──────────────────────────────────────────────────────────────


class DeployReport:
    """Human-readable post-deploy report from an AuditEntry.

    Usage::

        report = DeployReport(entry)
        print(report.text())      # plain text
        print(report.yaml())      # YAML (for CI)
    """

    _STATUS_ICON = {
        "done": "✓",
        "failed": "✗",
        "skipped": "⤼",
        "running": "▶",
        "pending": "·",
    }

    def __init__(self, entry: AuditEntry) -> None:
        self.entry = entry

    def text(self) -> str:
        e = self.entry
        result_label = "SUCCESS" if e.ok else "FAILED"
        dry = " [DRY RUN]" if e.dry_run else ""
        lines: list[str] = [
            "",
            f"┌─ Deploy report{dry} ──────────────────────────────",
            f"│  host     : {e.host}",
            f"│  app      : {e.app}",
            f"│  strategy : {e.from_strategy} → {e.to_strategy}",
        ]
        if e.pattern:
            lines.append(f"│  pattern  : {e.pattern}")
        lines += [
            f"│  result   : {result_label}",
            f"│  steps    : {e.steps_ok}/{e.steps_total} ok"
            + (f", {e.steps_failed} failed" if e.steps_failed else ""),
            f"│  elapsed  : {e.elapsed_s:.1f}s",
            f"│  at       : {e.ts}",
            "├─ Steps ─────────────────────────────────────────",
        ]
        for s in e.steps:
            icon = self._STATUS_ICON.get(s.get("status", ""), "?")
            err_suffix = ""
            if s.get("error"):
                err_suffix = f"  ← {s['error'][:60]}"
            lines.append(f"│  {icon} {s['id']:<28} {s.get('action', '')}{err_suffix}")
        if e.error:
            lines.append(f"│  ERROR: {e.error}")
        lines.append("└─────────────────────────────────────────────────")
        return "\n".join(lines)

    def yaml(self) -> str:
        import yaml as _yaml
        return _yaml.dump(self.entry.to_dict(),
                          default_flow_style=False, allow_unicode=True)

    def summary_line(self) -> str:
        """Single-line summary for CI log."""
        e = self.entry
        status = "ok" if e.ok else "FAIL"
        return (
            f"[{status}] {e.app} @ {e.host}: "
            f"{e.from_strategy}→{e.to_strategy} "
            f"{e.steps_ok}/{e.steps_total} steps in {e.elapsed_s:.1f}s"
        )

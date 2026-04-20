"""Persistent execution state — enables resuming an interrupted MigrationPlan.

State files live under ``.redeploy/state/<key>.yaml`` (relative to CWD by
default). The key is derived from the spec path + host so multiple plans can
checkpoint independently without colliding.

After every successful step the executor calls :meth:`ResumeState.mark_done`
which atomically rewrites the file. On the next run with ``--resume`` the
executor loads the file, marks the listed steps as ``SKIPPED`` and continues
from the first un-completed step.

When the plan completes successfully the state file is removed (no stale
checkpoints to confuse future runs).
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

import yaml
from pydantic import BaseModel, Field


DEFAULT_STATE_DIR = Path(".redeploy") / "state"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(value: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-._" else "_" for c in value)
    return safe.strip("_") or "spec"


def state_key(spec_path: str | os.PathLike[str], host: str) -> str:
    """Stable, filesystem-safe identifier for one (spec, host) checkpoint."""
    spec_str = str(spec_path)
    digest = hashlib.sha1(f"{spec_str}|{host}".encode()).hexdigest()[:8]
    return f"{_slug(Path(spec_str).stem)}-{_slug(host)}-{digest}"


def default_state_path(spec_path: str | os.PathLike[str], host: str,
                       base_dir: Optional[Path] = None) -> Path:
    base = Path(base_dir) if base_dir else DEFAULT_STATE_DIR
    return base / f"{state_key(spec_path, host)}.yaml"


class ResumeState(BaseModel):
    """Checkpoint for a single MigrationPlan execution."""

    spec_path: str = ""
    host: str = ""
    total_steps: int = 0
    completed_step_ids: list[str] = Field(default_factory=list)
    failed_step_id: Optional[str] = None
    failed_error: Optional[str] = None
    started_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)

    # Not persisted to disk — runtime helper.
    path: Optional[Path] = None

    model_config = {"arbitrary_types_allowed": True}

    # ── construction / IO ────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> "ResumeState":
        p = Path(path)
        with p.open() as f:
            data = yaml.safe_load(f) or {}
        data.pop("path", None)
        state = cls(**data)
        state.path = p
        return state

    @classmethod
    def load_or_new(cls, path: str | os.PathLike[str], *,
                    spec_path: str = "", host: str = "",
                    total_steps: int = 0) -> "ResumeState":
        p = Path(path)
        if p.exists():
            return cls.load(p)
        state = cls(spec_path=spec_path, host=host, total_steps=total_steps)
        state.path = p
        return state

    def save(self, path: Optional[str | os.PathLike[str]] = None) -> Path:
        target = Path(path) if path else self.path
        if target is None:
            raise ValueError("ResumeState.save: no path configured")
        target.parent.mkdir(parents=True, exist_ok=True)
        self.updated_at = _now_iso()
        payload = self.model_dump(exclude={"path"})
        # Atomic write: tmp file + rename keeps readers consistent.
        fd, tmp_name = tempfile.mkstemp(prefix=".state-", suffix=".yaml",
                                        dir=str(target.parent))
        try:
            with os.fdopen(fd, "w") as f:
                yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True)
            os.replace(tmp_name, target)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
        self.path = target
        return target

    def remove(self) -> None:
        if self.path and self.path.exists():
            try:
                self.path.unlink()
            except OSError:
                pass

    # ── mutators ─────────────────────────────────────────────────────────────

    def mark_done(self, step_id: str) -> None:
        if step_id not in self.completed_step_ids:
            self.completed_step_ids.append(step_id)
        self.failed_step_id = None
        self.failed_error = None
        self.save()

    def mark_failed(self, step_id: str, error: str) -> None:
        self.failed_step_id = step_id
        self.failed_error = error
        self.save()

    def reset(self) -> None:
        self.completed_step_ids = []
        self.failed_step_id = None
        self.failed_error = None
        self.started_at = _now_iso()
        self.save()

    # ── queries ──────────────────────────────────────────────────────────────

    def is_done(self, step_id: str) -> bool:
        return step_id in self.completed_step_ids

    @property
    def completed_count(self) -> int:
        return len(self.completed_step_ids)

    @property
    def remaining(self) -> int:
        return max(0, self.total_steps - self.completed_count)


def filter_resumable(step_ids: Iterable[str], state: ResumeState) -> list[str]:
    """Return ids that are NOT yet completed (preserves order)."""
    done = set(state.completed_step_ids)
    return [sid for sid in step_ids if sid not in done]

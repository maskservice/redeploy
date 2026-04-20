"""Checkpoint/Resume system for migration execution.

Allows resuming interrupted migrations from the last completed step.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from .models import MigrationPlan, MigrationStep, StepStatus


class CheckpointEntry(BaseModel):
    """Single step checkpoint entry."""
    step_id: str
    status: str  # "done", "failed", "skipped"
    result: Optional[str] = None
    error: Optional[str] = None
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MigrationCheckpoint(BaseModel):
    """Full checkpoint state for a migration."""
    spec_path: str  # Path to the migration spec file
    host: str
    app: str
    version: Optional[str] = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_steps: list[CheckpointEntry] = Field(default_factory=list)
    current_step_index: int = 0  # Index of next step to execute
    status: str = "running"  # "running", "completed", "failed", "rolled_back"
    
    @property
    def last_step_id(self) -> Optional[str]:
        """Get ID of last completed step."""
        if self.completed_steps:
            return self.completed_steps[-1].step_id
        return None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "spec_path": self.spec_path,
            "host": self.host,
            "app": self.app,
            "version": self.version,
            "started_at": self.started_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "current_step_index": self.current_step_index,
            "status": self.status,
            "completed_steps": [
                {
                    "step_id": e.step_id,
                    "status": e.status,
                    "result": e.result,
                    "error": e.error,
                    "completed_at": e.completed_at.isoformat(),
                }
                for e in self.completed_steps
            ],
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "MigrationCheckpoint":
        """Create checkpoint from dictionary."""
        return cls(
            spec_path=data["spec_path"],
            host=data["host"],
            app=data["app"],
            version=data.get("version"),
            started_at=datetime.fromisoformat(data["started_at"]),
            last_updated=datetime.fromisoformat(data["last_updated"]),
            current_step_index=data.get("current_step_index", 0),
            status=data.get("status", "running"),
            completed_steps=[
                CheckpointEntry(
                    step_id=e["step_id"],
                    status=e["status"],
                    result=e.get("result"),
                    error=e.get("error"),
                    completed_at=datetime.fromisoformat(e["completed_at"]),
                )
                for e in data.get("completed_steps", [])
            ],
        )


class CheckpointManager:
    """Manages checkpoint persistence and retrieval."""
    
    DEFAULT_FILENAME = ".redeploy-checkpoint.json"
    
    def __init__(self, project_dir: Path | str | None = None):
        self.project_dir = Path(project_dir) if project_dir else Path.cwd()
        self.checkpoint_path = self.project_dir / self.DEFAULT_FILENAME
    
    def save(self, checkpoint: MigrationCheckpoint) -> None:
        """Save checkpoint to disk."""
        checkpoint.last_updated = datetime.now(timezone.utc)
        self.checkpoint_path.write_text(
            json.dumps(checkpoint.to_dict(), indent=2, default=str),
            encoding="utf-8"
        )
    
    def load(self) -> Optional[MigrationCheckpoint]:
        """Load checkpoint from disk if exists."""
        if not self.checkpoint_path.exists():
            return None
        
        data = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        return MigrationCheckpoint.from_dict(data)
    
    def clear(self) -> None:
        """Remove checkpoint file."""
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()
    
    def exists(self) -> bool:
        """Check if checkpoint exists."""
        return self.checkpoint_path.exists()
    
    def update_step(
        self,
        step: MigrationStep,
        step_index: int,
        spec_path: str,
        host: str,
        app: str,
        version: Optional[str] = None,
    ) -> MigrationCheckpoint:
        """Update or create checkpoint with completed step."""
        checkpoint = self.load()
        
        if checkpoint is None:
            checkpoint = MigrationCheckpoint(
                spec_path=spec_path,
                host=host,
                app=app,
                version=version,
            )
        
        # Add completed step
        entry = CheckpointEntry(
            step_id=step.id,
            status=step.status.value,
            result=step.result,
            error=step.error,
        )
        checkpoint.completed_steps.append(entry)
        checkpoint.current_step_index = step_index + 1
        checkpoint.last_updated = datetime.now(timezone.utc)
        
        self.save(checkpoint)
        return checkpoint
    
    def mark_completed(self) -> None:
        """Mark migration as completed and clear checkpoint."""
        checkpoint = self.load()
        if checkpoint:
            checkpoint.status = "completed"
            checkpoint.last_updated = datetime.now(timezone.utc)
            self.save(checkpoint)
            # Optionally clear after some time
            # self.clear()
    
    def mark_failed(self, error: str) -> None:
        """Mark migration as failed."""
        checkpoint = self.load()
        if checkpoint:
            checkpoint.status = "failed"
            checkpoint.last_updated = datetime.now(timezone.utc)
            self.save(checkpoint)


def resume_plan_from_checkpoint(
    plan: MigrationPlan,
    checkpoint: MigrationCheckpoint,
) -> MigrationPlan:
    """Resume plan execution from checkpoint.
    
    Marks steps before checkpoint index as completed.
    """
    from copy import deepcopy
    
    # Create copy of plan to avoid modifying original
    resumed_plan = deepcopy(plan)
    
    # Mark completed steps from checkpoint
    completed_ids = {e.step_id for e in checkpoint.completed_steps if e.status == "done"}
    
    for i, step in enumerate(resumed_plan.steps):
        if step.id in completed_ids:
            step.status = StepStatus.DONE
            # Find result from checkpoint
            for entry in checkpoint.completed_steps:
                if entry.step_id == step.id:
                    step.result = entry.result
                    break
    
    return resumed_plan


def should_resume(checkpoint: Optional[MigrationCheckpoint], spec_path: str, host: str) -> bool:
    """Check if checkpoint matches current spec and is resumable."""
    if checkpoint is None:
        return False
    
    if checkpoint.status not in ("running", "failed"):
        return False
    
    if checkpoint.spec_path != str(spec_path):
        return False
    
    if checkpoint.host != host:
        return False
    
    return True


def format_resume_status(checkpoint: MigrationCheckpoint) -> str:
    """Format checkpoint status for display."""
    total = checkpoint.current_step_index
    completed = len([e for e in checkpoint.completed_steps if e.status == "done"])
    
    return (
        f"Checkpoint: {completed}/{total} steps completed "
        f"(last: {checkpoint.last_step_id or 'none'}, "
        f"status: {checkpoint.status})"
    )

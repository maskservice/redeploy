"""Step context for tracking execution state."""
from dataclasses import dataclass, field
from typing import Optional, Any, Dict, List
from datetime import datetime


@dataclass
class StepContext:
    """Tracks the execution of a single step."""
    name: str
    risk: str = "low"
    timeout: Optional[int] = None
    success: bool = False
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    outputs: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)

    def log(self, message: str) -> None:
        """Add a log message to this step."""
        self.logs.append(f"{datetime.now().isoformat()} | {message}")

    def set_output(self, key: str, value: Any) -> None:
        """Set an output value for this step."""
        self.outputs[key] = value

    def complete(self, success: bool = True, error: Optional[str] = None) -> None:
        """Mark the step as completed."""
        self.success = success
        self.error = error
        self.completed_at = datetime.now()

    @property
    def duration_seconds(self) -> float:
        """Calculate step duration."""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return (datetime.now() - self.started_at).total_seconds()

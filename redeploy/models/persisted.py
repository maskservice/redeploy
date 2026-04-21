"""PersistedModel mixin — YAML serialization for BaseModel subclasses."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel


class PersistedModel(BaseModel):
    """Mixin for models that can be persisted to/from YAML files."""

    def to_yaml(self) -> str:
        """Serialize model to YAML string."""
        return yaml.dump(
            self.model_dump(mode="json"),
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )

    @classmethod
    def load(cls, path: Path) -> Self:
        """Load model from YAML file."""
        raw = yaml.safe_load(path.read_text())
        return cls(**raw)

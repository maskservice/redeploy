"""VersionManifest Pydantic model for .redeploy/version.yaml.

Declares where version lives (sources) and how to manage it (git, changelog).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class SourceConfig(BaseModel):
    """Single source of version truth (one file)."""

    path: Path
    format: Literal["plain", "toml", "json", "yaml", "regex", "dockerfile"] = "plain"
    key: Optional[str] = None  # For TOML/JSON/YAML: dotted key path
    pattern: Optional[str] = None  # For regex: pattern with capture group
    value_pattern: Optional[str] = None  # Extract version from value (e.g., image tag)
    write_pattern: Optional[str] = None  # How to write back (e.g., "ghcr.io/app:v{version}")
    optional: bool = False  # If True, don't fail if not found

    @field_validator("key")
    @classmethod
    def key_required_for_structured(cls, v: Optional[str], info) -> Optional[str]:
        fmt = info.data.get("format")
        if fmt in ("toml", "json", "yaml") and not v:
            raise ValueError(f"'key' required for format='{fmt}'")
        return v

    @field_validator("pattern")
    @classmethod
    def pattern_required_for_regex(cls, v: Optional[str], info) -> Optional[str]:
        fmt = info.data.get("format")
        if fmt == "regex" and not v:
            raise ValueError("'pattern' required for format='regex'")
        return v


class GitConfig(BaseModel):
    """Git integration settings."""

    tag_format: str = "v{version}"
    tag_message: str = "Release {version}"
    commit_message: str = "chore(release): {version}"
    sign_tag: bool = False
    require_clean: bool = True


class ChangelogConfig(BaseModel):
    """Changelog generation settings."""

    path: Path = Path("CHANGELOG.md")
    format: Literal["keepachangelog", "commits", "custom"] = "keepachangelog"
    unreleased_header: str = "## [Unreleased]"


class CommitRules(BaseModel):
    """Conventional commits → bump type mapping."""

    breaking: str = "major"
    feat: str = "minor"
    fix: str = "patch"
    perf: str = "patch"
    refactor: str = "patch"
    docs: str = "none"
    chore: str = "none"
    test: str = "none"


class CommitsConfig(BaseModel):
    """Conventional commits analysis settings."""

    analyze: bool = False
    convention: Literal["conventional", "angular", "custom"] = "conventional"
    rules: CommitRules = Field(default_factory=CommitRules)


class VersionManifest(BaseModel):
    """Root manifest model for .redeploy/version.yaml."""

    version: str  # current version string
    scheme: Literal["semver", "calver", "integer", "custom"] = "semver"
    policy: Literal["synced", "independent"] = "synced"

    sources: list[SourceConfig] = Field(default_factory=list)
    git: GitConfig = Field(default_factory=GitConfig)
    changelog: Optional[ChangelogConfig] = None
    commits: CommitsConfig = Field(default_factory=CommitsConfig)

    @classmethod
    def load(cls, path: Path) -> "VersionManifest":
        """Load manifest from YAML file."""
        import yaml

        if not path.exists():
            raise FileNotFoundError(f"Version manifest not found: {path}")

        data = yaml.safe_load(path.read_text())
        # Handle both top-level version: and nested version: key
        if "version" in data and isinstance(data["version"], str):
            return cls.model_validate(data)
        # Handle nested structure: version: { version: "1.0.0", ... }
        if "version" in data and isinstance(data["version"], dict):
            return cls.model_validate(data["version"])
        return cls.model_validate(data)

    def save(self, path: Path) -> None:
        """Save manifest to YAML file."""
        import yaml

        data = self.model_dump(mode="json", exclude_none=True)
        # Use nested structure for clarity
        output = {"version": data}
        path.write_text(yaml.dump(output, default_flow_style=False, sort_keys=False))

    def format_version(self, version: str) -> str:
        """Format version string using manifest's tag_format."""
        return self.git.tag_format.format(version=version)

    def get_source_paths(self) -> list[Path]:
        """Return all source file paths."""
        return [s.path for s in self.sources]

"""Project manifest models — redeploy.yaml + environments."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field

from .enums import DeployStrategy


class EnvironmentConfig(BaseModel):
    """One named environment in redeploy.yaml."""
    host: Optional[str] = None
    strategy: Optional[str] = None
    app: Optional[str] = None
    domain: Optional[str] = None
    remote_dir: Optional[str] = None
    env_file: Optional[str] = None
    ssh_key: Optional[str] = None
    ssh_port: int = 22
    verify_url: Optional[str] = None
    spec: Optional[str] = None


class ProjectManifest(BaseModel):
    """Per-project redeploy.yaml — replaces repetitive Makefile variables."""
    spec: str = "migration.yaml"
    local_spec: str = "migration-local.yaml"
    host: Optional[str] = None
    app: str = "app"
    domain: Optional[str] = None
    ssh_key: Optional[str] = None
    ssh_port: int = 22
    remote_dir: Optional[str] = None
    env_file: str = ".env"
    environments: dict[str, EnvironmentConfig] = Field(default_factory=dict)

    @classmethod
    def find_and_load(cls, start: Path) -> Optional[ProjectManifest]:
        """Walk up from *start* looking for redeploy.css/less/yaml."""
        for d in [Path(start)] + list(Path(start).parents):
            for css_name in ("redeploy.css", "redeploy.less"):
                candidate = d / css_name
                if candidate.exists():
                    from ..dsl.loader import load_css
                    result = load_css(candidate)
                    if result.manifest:
                        return result.manifest
            candidate = d / "redeploy.yaml"
            if candidate.exists():
                with candidate.open() as f:
                    return cls(**yaml.safe_load(f))
        return None

    @classmethod
    def find_css(cls, start: Path) -> Optional[Path]:
        """Return path to redeploy.css/less if found, else None."""
        for d in [Path(start)] + list(Path(start).parents):
            for name in ("redeploy.css", "redeploy.less"):
                p = d / name
                if p.exists():
                    return p
        return None

    def env(self, name: str) -> Optional[EnvironmentConfig]:
        return self.environments.get(name)

    def resolve_env(self, name: str) -> EnvironmentConfig:
        base = EnvironmentConfig(
            host=self.host,
            app=self.app,
            domain=self.domain,
            remote_dir=self.remote_dir,
            env_file=self.env_file,
            ssh_key=self.ssh_key,
            ssh_port=self.ssh_port,
        )
        override = self.environments.get(name)
        if not override:
            return base
        return EnvironmentConfig(
            host=override.host or base.host,
            strategy=override.strategy,
            app=override.app or base.app,
            domain=override.domain or base.domain,
            remote_dir=override.remote_dir or base.remote_dir,
            env_file=override.env_file or base.env_file,
            ssh_key=override.ssh_key or base.ssh_key,
            ssh_port=override.ssh_port if override.ssh_port != 22 else base.ssh_port,
            verify_url=override.verify_url,
            spec=override.spec,
        )

    @classmethod
    def from_dotenv(cls, project_dir: Path) -> Optional[ProjectManifest]:
        """Read DEPLOY_* vars from .env file in project_dir as a fallback."""
        env_path = Path(project_dir) / ".env"
        if not env_path.exists():
            return None
        data: dict = {}
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip().upper()
            v = v.strip().strip('"').strip("'")
            if k == "DEPLOY_HOST":
                data["host"] = v
            elif k == "DEPLOY_APP":
                data["app"] = v
            elif k == "DEPLOY_DOMAIN":
                data["domain"] = v
            elif k == "DEPLOY_ENV_FILE":
                data["env_file"] = v
            elif k == "DEPLOY_SSH_KEY":
                data["ssh_key"] = v
        if not data:
            return None
        return cls(**data)

    def apply_to_spec(self, spec: Any, env_name: str = "") -> None:
        """Overlay manifest values onto a MigrationSpec."""
        from .spec import MigrationSpec
        assert isinstance(spec, MigrationSpec)
        cfg = self.resolve_env(env_name) if env_name else self
        host = cfg.host if isinstance(cfg, EnvironmentConfig) else self.host
        domain = cfg.domain if isinstance(cfg, EnvironmentConfig) else self.domain
        remote_dir = cfg.remote_dir if isinstance(cfg, EnvironmentConfig) else self.remote_dir
        env_file = cfg.env_file if isinstance(cfg, EnvironmentConfig) else self.env_file
        verify_url = cfg.verify_url if isinstance(cfg, EnvironmentConfig) else None
        strategy_str = cfg.strategy if isinstance(cfg, EnvironmentConfig) else None

        if host:
            spec.source.host = host
            spec.target.host = host
        if domain and not spec.target.domain:
            spec.target.domain = domain
        if remote_dir and not spec.target.remote_dir:
            spec.target.remote_dir = remote_dir
        if env_file and not spec.target.env_file:
            spec.target.env_file = env_file
        if verify_url and not spec.target.verify_url:
            spec.target.verify_url = verify_url
        if strategy_str:
            try:
                spec.target.strategy = DeployStrategy(strategy_str)
            except ValueError:
                pass

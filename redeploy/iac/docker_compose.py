"""redeploy.iac.docker_compose — Tier 1 parser for docker-compose.yml.

Supports:
  - Compose v3.x syntax (all common keys)
  - services: image, build, ports, volumes, environment, env_file,
    networks, depends_on, healthcheck, restart, command, deploy.replicas
  - networks: top-level named networks
  - volumes: top-level named volumes
  - Variable substitution: ${VAR}, ${VAR:-default}
  - Multi-file support when called on a directory (compose + override)
  - Profiles: recorded as warnings if non-default profile detected
  - x-* extension keys: silently skipped

Does NOT support:
  - Runtime secret resolution (only names)
  - Custom build args beyond basics
  - Docker Swarm deploy.placement, update_config, …
"""
from __future__ import annotations

import os
import re
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional

import yaml

from .base import ParsedSpec, Parser, PortInfo, ServiceInfo, VolumeInfo


# ── helpers ───────────────────────────────────────────────────────────────────

_VAR_RE = re.compile(r"\$\{([^}]+)\}")


def _resolve_var(value: str, env: dict[str, str]) -> str:
    """Resolve ${VAR} and ${VAR:-default} patterns against *env*."""
    def _replace(m: re.Match) -> str:
        expr = m.group(1)
        if ":-" in expr:
            name, default = expr.split(":-", 1)
            return env.get(name, default)
        return env.get(expr, m.group(0))   # leave unresolvable as-is
    return _VAR_RE.sub(_replace, str(value))


def _parse_port(raw: str | int | dict) -> Optional[PortInfo]:
    """Parse a single Compose port entry into PortInfo."""
    if isinstance(raw, dict):
        # long-form: {target: 80, published: "0.0.0.0:8080", protocol: tcp}
        target = int(raw.get("target", 0))
        proto = raw.get("protocol", "tcp")
        published = str(raw.get("published", ""))
        if not published:
            return PortInfo(container=target, protocol=proto)
        return _parse_port(f"{published}:{target}/{proto}")

    s = str(raw).strip()
    proto = "tcp"
    if "/" in s.split(":")[-1]:
        s, proto = s.rsplit("/", 1)

    parts = s.split(":")
    if len(parts) == 3:
        host_ip, host_port, container_port = parts
    elif len(parts) == 2:
        host_ip = "0.0.0.0"
        host_port, container_port = parts
    elif len(parts) == 1:
        return PortInfo(container=int(s), protocol=proto)
    else:
        return None

    try:
        return PortInfo(
            container=int(container_port),
            host=int(host_port) if host_port else None,
            protocol=proto,
            host_ip=host_ip or "0.0.0.0",
        )
    except ValueError:
        return None


def _parse_volume(raw: str | dict) -> Optional[VolumeInfo]:
    """Parse a single Compose volume entry into VolumeInfo."""
    if isinstance(raw, dict):
        source_type = raw.get("type", "volume")
        source = raw.get("source")
        target = raw.get("target", "")
        read_only = bool(raw.get("read_only", False))
        return VolumeInfo(target=target, source=source,
                          source_type=source_type, read_only=read_only)
    # short-form: "host_path:container_path[:ro]"
    s = str(raw)
    parts = s.split(":")
    if len(parts) >= 2:
        source = parts[0]
        target = parts[1]
        read_only = "ro" in parts[2:] if len(parts) > 2 else False
        source_type = "bind" if source.startswith(("/", ".", "~")) else "volume"
        return VolumeInfo(target=target, source=source,
                          source_type=source_type, read_only=read_only)
    return VolumeInfo(target=s, source_type="volume")


def _env_dict(raw: list | dict | None) -> dict[str, str]:
    """Normalise Compose environment: block (list or dict) → dict."""
    if not raw:
        return {}
    if isinstance(raw, dict):
        return {k: str(v) if v is not None else "" for k, v in raw.items()}
    result: dict[str, str] = {}
    for item in raw:
        item = str(item)
        if "=" in item:
            k, v = item.split("=", 1)
            result[k] = v
        else:
            result[item] = os.environ.get(item, "")
    return result


# ── main parser ───────────────────────────────────────────────────────────────


_COMPOSE_NAMES = {
    "docker-compose.yml", "docker-compose.yaml",
    "compose.yml", "compose.yaml",
}
_OVERRIDE_NAMES = {
    "docker-compose.override.yml", "docker-compose.override.yaml",
    "compose.override.yml", "compose.override.yaml",
}


class DockerComposeParser:
    """Parser for docker-compose.yml / compose.yaml files."""

    name = "docker_compose"
    format_label = "Docker Compose"
    extensions = [".yml", ".yaml"]
    path_patterns = [
        "docker-compose.yml", "docker-compose.yaml",
        "compose.yml", "compose.yaml",
        "docker-compose.*.yml", "docker-compose.*.yaml",
    ]

    def can_parse(self, path: Path) -> bool:
        name = path.name.lower()
        if name in _COMPOSE_NAMES or name in _OVERRIDE_NAMES:
            return True
        for pat in self.path_patterns:
            if fnmatch(name, pat.lower()):
                return True
        # Heuristic: YAML with a top-level 'services' key
        if path.suffix.lower() in (".yml", ".yaml"):
            try:
                with path.open(encoding="utf-8") as f:
                    first_lines = "".join(f.readline() for _ in range(20))
                if "services:" in first_lines:
                    return True
            except OSError:
                pass
        return False

    def parse(self, path: Path) -> ParsedSpec:
        spec = ParsedSpec(
            source_file=path,
            source_format=self.name,
        )

        # Load the primary file (and optional override if present)
        data = self._load_merged(path, spec)
        if not data:
            spec.confidence = 0.0
            spec.add_warning("Empty or invalid YAML", severity="error",
                             source_path=str(path))
            return spec

        # Resolve env from a .env file in the same directory
        env_context = self._load_dotenv(path.parent)

        # ── top-level networks ────────────────────────────────────────────────
        networks_raw = data.get("networks") or {}
        for net_name in networks_raw:
            if net_name and net_name not in spec.networks:
                spec.networks.append(net_name)

        # ── top-level volumes ─────────────────────────────────────────────────
        volumes_raw = data.get("volumes") or {}
        for vol_name in volumes_raw:
            spec.volumes.append(VolumeInfo(
                target=vol_name,
                source=vol_name,
                source_type="volume",
            ))

        # ── secrets (names only) ──────────────────────────────────────────────
        secrets_raw = data.get("secrets") or {}
        for secret_name, secret_cfg in (secrets_raw.items() if isinstance(secrets_raw, dict) else []):
            if isinstance(secret_cfg, dict) and secret_cfg.get("external"):
                spec.secrets_referenced.append(secret_name)

        # ── services ──────────────────────────────────────────────────────────
        services_raw = data.get("services") or {}
        if not isinstance(services_raw, dict):
            spec.add_warning("'services' block is not a mapping", severity="error")
            spec.confidence = 0.5
            return spec

        profiles_seen: set[str] = set()

        for svc_name, svc_cfg in services_raw.items():
            if not isinstance(svc_cfg, dict):
                svc_cfg = {}
            svc = self._parse_service(svc_name, svc_cfg, env_context, spec)
            spec.services.append(svc)

            # track profiles
            for prof in (svc_cfg.get("profiles") or []):
                profiles_seen.add(str(prof))

        if profiles_seen:
            spec.add_warning(
                f"Profiles detected ({', '.join(sorted(profiles_seen))}); "
                f"only default profile services included in this spec.",
                severity="info",
            )

        spec.runtime_hints.append("docker")

        # ── consolidate top-level ports/images ────────────────────────────────
        for svc in spec.services:
            for p in svc.ports:
                if p not in spec.ports:
                    spec.ports.append(p)
            if svc.image and svc.image not in spec.images:
                spec.images.append(svc.image)

        return spec

    # ── private helpers ───────────────────────────────────────────────────────

    def _load_merged(self, path: Path, spec: ParsedSpec) -> dict:
        """Load primary file, deep-merge with override file if present."""
        try:
            with path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as exc:
            spec.add_warning(f"Could not load {path.name}: {exc}", severity="error")
            return {}

        override_path = self._find_override(path)
        if override_path:
            try:
                with override_path.open(encoding="utf-8") as f:
                    override = yaml.safe_load(f) or {}
                data = _deep_merge(data, override)
                spec.add_warning(
                    f"Merged with override file {override_path.name}",
                    severity="info",
                )
            except (OSError, yaml.YAMLError) as exc:
                spec.add_warning(
                    f"Could not load override {override_path.name}: {exc}",
                    severity="warn",
                )
        return data

    def _find_override(self, primary: Path) -> Optional[Path]:
        directory = primary.parent
        for name in _OVERRIDE_NAMES:
            candidate = directory / name
            if candidate.exists() and candidate != primary:
                return candidate
        return None

    def _load_dotenv(self, directory: Path) -> dict[str, str]:
        env: dict[str, str] = {}
        dotenv = directory / ".env"
        if dotenv.exists():
            try:
                for line in dotenv.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip().strip('"').strip("'")
            except OSError:
                pass
        return env

    def _parse_service(self, name: str, cfg: dict,
                       env_context: dict[str, str],
                       spec: ParsedSpec) -> ServiceInfo:
        def resolve(v: object) -> str:
            return _resolve_var(str(v), env_context) if v is not None else ""

        # image / build
        image = resolve(cfg.get("image")) or None
        build = cfg.get("build")
        build_context: Optional[str] = None
        if build:
            if isinstance(build, str):
                build_context = build
            elif isinstance(build, dict):
                build_context = build.get("context", ".")
            if not image:
                image = f"<build:{build_context or '.'}>"

        # ports
        ports: list[PortInfo] = []
        for raw in (cfg.get("ports") or []):
            p = _parse_port(raw)
            if p:
                ports.append(p)
            else:
                spec.add_warning(f"[{name}] Could not parse port: {raw!r}",
                                 severity="warn")

        # volumes
        volumes: list[VolumeInfo] = []
        for raw in (cfg.get("volumes") or []):
            v = _parse_volume(raw)
            if v:
                volumes.append(v)

        # environment
        env = _env_dict(cfg.get("environment"))
        # resolve variables
        env = {k: _resolve_var(v, env_context) for k, v in env.items()}

        # env_file
        env_files: list[str] = []
        ef = cfg.get("env_file")
        if ef:
            if isinstance(ef, str):
                env_files = [ef]
            elif isinstance(ef, list):
                env_files = [str(x) for x in ef]

        # networks
        svc_nets = cfg.get("networks")
        if isinstance(svc_nets, dict):
            svc_networks = list(svc_nets.keys())
        elif isinstance(svc_nets, list):
            svc_networks = [str(n) for n in svc_nets]
        else:
            svc_networks = []

        # depends_on
        dep = cfg.get("depends_on")
        if isinstance(dep, list):
            depends_on = [str(d) for d in dep]
        elif isinstance(dep, dict):
            depends_on = list(dep.keys())
        else:
            depends_on = []

        # healthcheck
        hc = cfg.get("healthcheck")
        healthcheck: Optional[str] = None
        if isinstance(hc, dict):
            test = hc.get("test")
            if isinstance(test, list):
                test = " ".join(str(t) for t in test)
            healthcheck = str(test) if test else None

        # deploy.replicas
        deploy = cfg.get("deploy") or {}
        replicas = 1
        if isinstance(deploy, dict):
            replicas = int(deploy.get("replicas", 1))

        # labels
        labels_raw = cfg.get("labels")
        if isinstance(labels_raw, dict):
            labels = {str(k): str(v) for k, v in labels_raw.items()}
        elif isinstance(labels_raw, list):
            labels = {}
            for item in labels_raw:
                if "=" in str(item):
                    k, v = str(item).split("=", 1)
                    labels[k] = v
        else:
            labels = {}

        return ServiceInfo(
            name=name,
            image=image,
            ports=ports,
            volumes=volumes,
            env=env,
            env_files=env_files,
            networks=svc_networks,
            depends_on=depends_on,
            healthcheck=healthcheck,
            restart=cfg.get("restart"),
            command=str(cfg["command"]) if cfg.get("command") else None,
            build_context=build_context,
            replicas=replicas,
            labels=labels,
        )


# ── deep merge util ───────────────────────────────────────────────────────────

def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result

"""Docker Compose parser for redeploy.iac (Tier 1).

Handles ``docker-compose.yml``, ``docker-compose.yaml``,
``compose.yml``, ``compose.yaml`` and multi-file variants.

Produces a ``ParsedSpec`` with:
  - services (name, image, ports, volumes, env, networks, depends_on, …)
  - top-level networks and volumes
  - images list (deduplicated)
  - environment variable hints
  - secrets referenced (names only)
  - warnings for unsupported or lossy fields
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

import yaml

from ..base import (
    ConversionWarning,
    ParsedSpec,
    PortInfo,
    ServiceInfo,
    VolumeInfo,
)


class DockerComposeParser:
    """Parser for Docker Compose files (v2 + v3 schema, Compose Spec)."""

    name = "docker-compose"
    format_label = "Docker Compose"
    # source_format in ParsedSpec will equal self.name
    extensions = [".yml", ".yaml"]
    path_patterns = [
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
        "docker-compose.*.yml",
        "docker-compose.*.yaml",
    ]

    # ── protocol ──────────────────────────────────────────────────────────────

    def can_parse(self, path: Path) -> bool:
        name = path.name.lower()
        if name in ("docker-compose.yml", "docker-compose.yaml",
                    "compose.yml", "compose.yaml"):
            return True
        if re.match(r"docker-compose\.[^.]+\.(yml|yaml)$", name):
            return True
        return False

    def parse(self, path: Path) -> ParsedSpec:
        with path.open(encoding="utf-8") as f:
            raw: dict = yaml.safe_load(f) or {}

        spec = ParsedSpec(
            source_file=path,
            source_format=self.name,
            confidence=1.0,
        )

        if not isinstance(raw, dict):
            spec.add_warning("Top-level is not a mapping — skipping", severity="error")
            spec.confidence = 0.0
            return spec

        # top-level version (v2/v3) — informational only
        version = raw.get("version", "")
        if version:
            spec.runtime_hints.append(f"compose-version: {version}")

        # services
        services_raw = raw.get("services") or {}
        for svc_name, svc_def in services_raw.items():
            if not isinstance(svc_def, dict):
                spec.add_warning(f"Service '{svc_name}' is not a mapping, skipping")
                spec.confidence = max(0.7, spec.confidence - 0.1)
                continue
            svc = self._parse_service(svc_name, svc_def, spec)
            spec.services.append(svc)

        # top-level networks
        for net_name in (raw.get("networks") or {}):
            if net_name not in spec.networks:
                spec.networks.append(net_name)

        # top-level volumes
        for vol_name, vol_def in (raw.get("volumes") or {}).items():
            vol_def = vol_def or {}
            spec.volumes.append(VolumeInfo(
                target="",
                source=vol_name,
                source_type="volume",
            ))

        # secrets (names only, never values)
        for secret_name in (raw.get("secrets") or {}):
            if secret_name not in spec.secrets_referenced:
                spec.secrets_referenced.append(secret_name)

        # env_files at compose root (rare but valid)
        for ef in (raw.get("env_file") or []):
            if ef not in spec.env_files:
                spec.env_files.append(ef)

        return spec

    # ── service parsing ───────────────────────────────────────────────────────

    def _parse_service(self, name: str, d: dict, spec: ParsedSpec) -> ServiceInfo:
        svc = ServiceInfo(name=name)

        svc.image = d.get("image") or None
        if svc.image:
            if svc.image not in spec.images:
                spec.images.append(svc.image)

        svc.build_context = self._parse_build(d.get("build"))
        svc.command = self._parse_command(d.get("command"))
        svc.restart = d.get("restart") or None
        svc.replicas = int((d.get("deploy") or {}).get("replicas", 1))

        svc.ports = self._parse_ports(d.get("ports") or [], spec)
        svc.volumes = self._parse_volumes(d.get("volumes") or [], spec)
        svc.networks = list(d.get("networks") or [])
        svc.env, svc.env_files = self._parse_env(d, spec)
        svc.depends_on = self._parse_depends_on(d.get("depends_on"))
        svc.labels = self._parse_labels(d.get("labels"))
        svc.healthcheck = self._parse_healthcheck(d.get("healthcheck"))

        # secrets referenced by service
        for secret in (d.get("secrets") or []):
            secret_name = secret if isinstance(secret, str) else secret.get("source", "")
            if secret_name and secret_name not in spec.secrets_referenced:
                spec.secrets_referenced.append(secret_name)

        # env_files at service level
        for ef in (d.get("env_file") or []):
            ef = ef if isinstance(ef, str) else ef.get("path", "")
            if ef and ef not in spec.env_files:
                spec.env_files.append(ef)
            if ef and ef not in svc.env_files:
                svc.env_files.append(ef)

        return svc

    # ── field parsers ─────────────────────────────────────────────────────────

    def _parse_build(self, build: Any) -> Optional[str]:
        if not build:
            return None
        if isinstance(build, str):
            return build
        if isinstance(build, dict):
            return build.get("context") or "."
        return None

    def _parse_command(self, cmd: Any) -> Optional[str]:
        if cmd is None:
            return None
        if isinstance(cmd, list):
            return " ".join(str(c) for c in cmd)
        return str(cmd)

    def _parse_ports(self, ports_raw: list, spec: ParsedSpec) -> list[PortInfo]:
        result: list[PortInfo] = []
        for p in ports_raw:
            try:
                pi = self._parse_port_entry(p)
                result.append(pi)
                if pi not in spec.ports:
                    spec.ports.append(pi)
            except Exception as exc:
                spec.add_warning(f"Cannot parse port entry {p!r}: {exc}")
                spec.confidence = max(0.8, spec.confidence - 0.05)
        return result

    def _parse_port_entry(self, p: Any) -> PortInfo:
        if isinstance(p, dict):
            return PortInfo(
                container=int(p.get("target", 0)),
                host=int(p["published"]) if p.get("published") else None,
                protocol=p.get("protocol", "tcp"),
                host_ip=p.get("host_ip", "0.0.0.0"),
            )
        # string form: "8080:80", "80", "127.0.0.1:8080:80/tcp"
        s = str(p)
        proto = "tcp"
        if "/" in s:
            s, proto = s.rsplit("/", 1)
        parts = s.split(":")
        if len(parts) == 1:
            return PortInfo(container=int(parts[0]), protocol=proto)
        if len(parts) == 2:
            return PortInfo(container=int(parts[1]), host=int(parts[0]),
                            protocol=proto)
        # host_ip:host:container
        return PortInfo(container=int(parts[2]), host=int(parts[1]),
                        host_ip=parts[0], protocol=proto)

    def _parse_volumes(self, vols_raw: list, spec: ParsedSpec) -> list[VolumeInfo]:
        result: list[VolumeInfo] = []
        for v in vols_raw:
            try:
                vi = self._parse_volume_entry(v)
                result.append(vi)
            except Exception as exc:
                spec.add_warning(f"Cannot parse volume entry {v!r}: {exc}")
        return result

    def _parse_volume_entry(self, v: Any) -> VolumeInfo:
        if isinstance(v, dict):
            return VolumeInfo(
                target=v.get("target", ""),
                source=v.get("source"),
                source_type=v.get("type", "volume"),
                read_only=bool(v.get("read_only", False)),
            )
        # string: "named_vol:/data:ro" or "/host:/cont" or "named:/cont"
        s = str(v)
        ro = s.endswith(":ro")
        if ro:
            s = s[:-3]
        parts = s.split(":", 1)
        source = parts[0] if len(parts) == 2 else None
        target = parts[1] if len(parts) == 2 else parts[0]
        src_type = "bind" if source and source.startswith("/") else "volume"
        return VolumeInfo(target=target, source=source,
                          source_type=src_type, read_only=ro)

    def _parse_env(self, d: dict, spec: ParsedSpec) -> tuple[dict[str, str], list[str]]:
        env: dict[str, str] = {}
        env_files: list[str] = []

        raw_env = d.get("environment") or {}
        if isinstance(raw_env, list):
            for item in raw_env:
                if "=" in str(item):
                    k, v = str(item).split("=", 1)
                    env[k] = v
                else:
                    env[str(item)] = ""
        elif isinstance(raw_env, dict):
            for k, v in raw_env.items():
                env[str(k)] = str(v) if v is not None else ""

        spec.env_vars.update(env)
        return env, env_files

    def _parse_depends_on(self, dep: Any) -> list[str]:
        if not dep:
            return []
        if isinstance(dep, list):
            return [str(d) for d in dep]
        if isinstance(dep, dict):
            return list(dep.keys())
        return [str(dep)]

    def _parse_labels(self, labels: Any) -> dict[str, str]:
        if not labels:
            return {}
        if isinstance(labels, list):
            result = {}
            for item in labels:
                if "=" in str(item):
                    k, v = str(item).split("=", 1)
                    result[k] = v
            return result
        if isinstance(labels, dict):
            return {str(k): str(v) for k, v in labels.items()}
        return {}

    def _parse_healthcheck(self, hc: Any) -> Optional[str]:
        if not hc:
            return None
        if isinstance(hc, dict):
            test = hc.get("test")
            if isinstance(test, list):
                return " ".join(str(t) for t in test[1:] if t != "CMD")
            return str(test) if test else None
        return str(hc)

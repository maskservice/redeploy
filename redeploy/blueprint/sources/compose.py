"""Parse docker-compose YAML files into :class:`ServiceSpec` objects."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import yaml

from ...models import ServicePort, ServiceSpec, VolumeMount


def merge_compose_files(
    compose_files: list[Path],
    services: list[ServiceSpec],
    seen: set[str],
) -> None:
    """Parse each docker-compose file and merge specs into *services* / *seen*."""
    for cf in compose_files:
        _merge_compose(cf, services, seen)


def _merge_compose(path: Path, services: list[ServiceSpec], seen: set[str]) -> None:
    """Parse a single docker-compose YAML and merge service specs."""
    try:
        raw = yaml.safe_load(path.read_text())
    except Exception:
        return
    if not isinstance(raw, dict) or "services" not in raw:
        return

    for svc_name, svc_def in raw["services"].items():
        if not isinstance(svc_def, dict):
            continue

        existing = next((s for s in services if s.name == svc_name), None)
        image = svc_def.get("image", "")
        platform = svc_def.get("platform", "")
        ports = _parse_compose_ports(svc_def.get("ports", []))
        volumes = _parse_compose_volumes(svc_def.get("volumes", []))
        env = _parse_compose_env(svc_def.get("environment", {}))
        healthcheck = _parse_compose_healthcheck(svc_def.get("healthcheck", {}))
        depends = svc_def.get("depends_on", [])
        if isinstance(depends, dict):
            depends = list(depends.keys())
        command = svc_def.get("command", None)
        if isinstance(command, list):
            command = " ".join(str(c) for c in command)
        restart = svc_def.get("restart", "unless-stopped")
        privileged = bool(svc_def.get("privileged", False))

        if existing:
            if not existing.image and image:
                existing.image = image
            if not existing.platform and platform:
                existing.platform = platform
            if not existing.ports:
                existing.ports = ports
            if not existing.volumes:
                existing.volumes = volumes
            existing.env.update(env)
            if not existing.healthcheck and healthcheck:
                existing.healthcheck = healthcheck
            if not existing.depends_on:
                existing.depends_on = depends
            existing.source_ref = str(path)
        else:
            seen.add(svc_name)
            services.append(ServiceSpec(
                name=svc_name,
                image=image,
                platform=platform,
                ports=ports,
                volumes=volumes,
                env=env,
                command=command,
                healthcheck=healthcheck,
                depends_on=depends,
                restart=restart,
                privileged=privileged,
                source_ref=str(path),
            ))


def _parse_compose_ports(raw: list) -> list[ServicePort]:
    result = []
    for entry in raw:
        if isinstance(entry, int):
            result.append(ServicePort(host=entry, container=entry))
        elif isinstance(entry, str):
            m = re.match(r"(?:[\d.]+:)?(\d+):(\d+)(?:/(tcp|udp))?", entry)
            if m:
                result.append(ServicePort(
                    host=int(m.group(1)),
                    container=int(m.group(2)),
                    protocol=m.group(3) or "tcp",
                ))
        elif isinstance(entry, dict):
            result.append(ServicePort(
                host=int(entry.get("published", entry.get("target", 0))),
                container=int(entry.get("target", 0)),
                protocol=entry.get("protocol", "tcp"),
            ))
    return result


def _parse_compose_volumes(raw: list | dict) -> list[VolumeMount]:
    result = []
    items = raw if isinstance(raw, list) else [f"{k}:{v}" for k, v in raw.items()]
    for entry in items:
        if isinstance(entry, str) and ":" in entry:
            parts = entry.split(":")
            result.append(VolumeMount(
                host=parts[0],
                container=parts[1],
                read_only=len(parts) > 2 and "ro" in parts[2],
            ))
        elif isinstance(entry, dict):
            result.append(VolumeMount(
                host=entry.get("source", ""),
                container=entry.get("target", ""),
                read_only=entry.get("read_only", False),
            ))
    return result


def _parse_compose_env(raw: dict | list) -> dict[str, str]:
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items() if v is not None}
    result = {}
    for entry in raw:
        if isinstance(entry, str) and "=" in entry:
            k, _, v = entry.partition("=")
            result[k.strip()] = v.strip()
    return result


def _parse_compose_healthcheck(raw: dict) -> Optional[str]:
    if not raw:
        return None
    test = raw.get("test", [])
    if isinstance(test, list) and len(test) > 1:
        return " ".join(str(t) for t in test[1:])
    if isinstance(test, str):
        return test
    return None

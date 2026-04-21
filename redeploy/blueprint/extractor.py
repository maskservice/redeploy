"""Blueprint extractor — derive a DeviceBlueprint from multiple sources.

Sources (in order of priority):
1. Running InfraState (podman ps / docker inspect on live device)
2. DeviceMap hardware snapshot
3. docker-compose YAML files
4. markpact / migration YAML definitions

The extractor reconciles all available information into a single
DeviceBlueprint that is self-contained and portable.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import yaml

from ..models import (
    BlueprintSource,
    DeviceBlueprint,
    DeviceMap,
    HardwareRequirements,
    InfraState,
    ServicePort,
    ServiceSpec,
    VolumeMount,
)


def extract_blueprint(
    *,
    name: str,
    device_map: Optional[DeviceMap] = None,
    infra: Optional[InfraState] = None,
    compose_files: Optional[list[Path]] = None,
    migration_file: Optional[Path] = None,
    markpact_files: Optional[list[Path]] = None,
    version: str = "0.0.0",
    description: str = "",
    tags: Optional[list[str]] = None,
    detect_live: bool = False,
    host: Optional[str] = None,
) -> DeviceBlueprint:
    """Build a DeviceBlueprint by reconciling all available sources.

    Parameters
    ----------
    name:
        Human-readable blueprint name, e.g. ``"c2004-kiosk"``.
    device_map:
        Previously saved DeviceMap (hardware + infra snapshot).
    infra:
        InfraState if already probed (skips live detection).
    compose_files:
        Local docker-compose YAML files to parse service specs from.
    migration_file:
        Local migration.yaml to extract app version and strategy from.
    markpact_files:
        Local markdown files with markpact fenced blocks.
    detect_live:
        If True and *host* is given, probe the host via SSH for a fresh
        InfraState even if *device_map* already has one.
    host:
        SSH target used when ``detect_live=True``.
    """
    if detect_live and host and not infra:
        from ..detect import Detector
        infra = infra or Detector(host).run()

    # Prefer freshly probed infra, fall back to device_map.infra
    _infra: Optional[InfraState] = infra or (device_map.infra if device_map else None)
    _hw = device_map.hardware if device_map else None

    services: list[ServiceSpec] = []
    seen: set[str] = set()

    # ── 1. Live InfraState (most accurate) ────────────────────────────────────
    if _infra:
        for svcs in _infra.services.values():
            for svc in svcs:
                if svc.name in seen:
                    continue
                seen.add(svc.name)
                services.append(ServiceSpec(
                    name=svc.name,
                    image=getattr(svc, "image", ""),
                    platform="",                    # unknown at this point
                    source_ref="infra:live",
                ))

    # ── 2. docker-compose files ────────────────────────────────────────────────
    for cf in (compose_files or []):
        _merge_compose(cf, services, seen)

    # ── 3. migration.yaml ─────────────────────────────────────────────────────
    app_version = version
    deploy_strategy = "podman_quadlet"
    if migration_file and migration_file.exists():
        _meta = _parse_migration_meta(migration_file)
        app_version = _meta.get("version", version)
        deploy_strategy = _meta.get("strategy", deploy_strategy)

    # ── 4. Hardware requirements ───────────────────────────────────────────────
    hw_req = _build_hw_requirements(_hw)

    # ── 5. App URL ─────────────────────────────────────────────────────────────
    app_url = None
    if _infra and _infra.host:
        h = _infra.host.split("@")[-1]
        # Look for a port-80 / port-8100 style proxy
        for port in (80, 8100, 8080, 443):
            if port in (_infra.ports or {}):
                app_url = f"http://{h}:{port}" if port not in (80, 443) else f"http://{h}"
                break

    source = BlueprintSource(
        device_id=device_map.id if device_map else host,
        device_name=device_map.name if device_map else "",
        migration_file=str(migration_file) if migration_file else None,
        markpact_files=[str(p) for p in (markpact_files or [])],
        compose_files=[str(p) for p in (compose_files or [])],
    )

    return DeviceBlueprint(
        name=name,
        version=app_version,
        description=description,
        tags=tags or (device_map.tags if device_map else []),
        services=services,
        hardware=hw_req,
        app_url=app_url,
        deploy_strategy=deploy_strategy,
        source=source,
    )


# ── helpers ───────────────────────────────────────────────────────────────────

def _merge_compose(path: Path, services: list[ServiceSpec], seen: set[str]) -> None:
    """Parse a docker-compose YAML and merge service specs."""
    try:
        raw = yaml.safe_load(path.read_text())
    except Exception:
        return
    if not isinstance(raw, dict) or "services" not in raw:
        return

    for svc_name, svc_def in raw["services"].items():
        if not isinstance(svc_def, dict):
            continue

        # If already seen from InfraState, enrich rather than duplicate
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
            # "8080:80/tcp"
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


def _parse_migration_meta(path: Path) -> dict:
    try:
        raw = yaml.safe_load(path.read_text())
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    result = {}
    if "version" in raw:
        result["version"] = str(raw["version"])
    if "strategy" in raw:
        result["strategy"] = raw["strategy"]
    # Walk steps looking for deploy action to infer strategy
    for step in raw.get("steps", []):
        action = step.get("action", "")
        if "podman" in action or "quadlet" in action:
            result["strategy"] = "podman_quadlet"
            break
        if "docker" in action:
            result["strategy"] = "docker_compose"
            break
    return result


def _build_hw_requirements(hw) -> HardwareRequirements:
    if hw is None:
        return HardwareRequirements()

    display_type = None
    display_res = None
    features: list[str] = []

    # DRM / DSI
    for output in getattr(hw, "drm_outputs", []):
        if "DSI" in (output.connector or ""):
            display_type = "DSI"
            if output.modes:
                display_res = output.modes[0]

    if getattr(hw, "backlights", []):
        features.append("backlight")
    if getattr(hw, "i2c_buses", []):
        features.append("i2c")

    # Infer arch from board name
    board = getattr(hw, "board", "") or ""
    arch = "linux/arm64" if any(x in board.lower() for x in ("rpi", "raspberry", "aarch64", "pi")) else ""

    # Overlays → wayland / kiosk hints
    for overlay in getattr(hw, "dsi_overlays", []):
        if "dsi" in overlay.lower():
            features.append("wayland")

    return HardwareRequirements(
        arch=arch,
        display_type=display_type,
        display_resolution=display_res,
        i2c_required=bool(getattr(hw, "i2c_buses", [])),
        features=features,
    )

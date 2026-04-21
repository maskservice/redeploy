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

from pathlib import Path
from typing import Optional

from ..models import (
    BlueprintSource,
    DeviceBlueprint,
    DeviceMap,
    InfraState,
    ServiceSpec,
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

    from .sources.compose import merge_compose_files
    from .sources.hardware import build_hw_requirements
    from .sources.infra import extract_services_from_infra, infer_app_url
    from .sources.migration import parse_migration_meta

    # Prefer freshly probed infra, fall back to device_map.infra
    _infra: Optional[InfraState] = infra or (device_map.infra if device_map else None)
    _hw = device_map.hardware if device_map else None

    services: list[ServiceSpec] = []
    seen: set[str] = set()

    # ── 1. Live InfraState ────────────────────────────────────────────────────
    if _infra:
        services.extend(extract_services_from_infra(_infra, seen))

    # ── 2. docker-compose files ───────────────────────────────────────────────
    merge_compose_files(list(compose_files or []), services, seen)

    # ── 3. migration.yaml ─────────────────────────────────────────────────────
    app_version = version
    deploy_strategy = "podman_quadlet"
    if migration_file and migration_file.exists():
        meta = parse_migration_meta(migration_file)
        app_version = meta.get("version", version)
        deploy_strategy = meta.get("strategy", deploy_strategy)

    # ── 4. Hardware requirements ────────────────────────────────────────────
    hw_req = build_hw_requirements(_hw)

    # ── 5. App URL ────────────────────────────────────────────────────────────
    app_url = infer_app_url(_infra)

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

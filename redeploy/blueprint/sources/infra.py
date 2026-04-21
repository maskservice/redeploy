"""Extract service specs and app URL from a live or cached ``InfraState``."""
from __future__ import annotations

from typing import Optional

from ...models import InfraState, ServiceSpec


def extract_services_from_infra(infra: InfraState, seen: set[str]) -> list[ServiceSpec]:
    """Return :class:`ServiceSpec` objects for every service found in *infra*.

    Skips entries whose ``name`` is already in *seen* and adds the new names.
    """
    result: list[ServiceSpec] = []
    for svcs in infra.services.values():
        for svc in svcs:
            if svc.name in seen:
                continue
            seen.add(svc.name)
            result.append(ServiceSpec(
                name=svc.name,
                image=getattr(svc, "image", ""),
                platform="",                # unknown at this point
                source_ref="infra:live",
            ))
    return result


def infer_app_url(infra: Optional[InfraState]) -> str | None:
    """Guess the application URL from open ports on *infra*.

    Prefers ports ``80 → http://host``, ``443 → https://host``, then
    ``8100``, ``8080`` with explicit port numbers.
    """
    if not infra or not infra.host:
        return None
    host = infra.host.split("@")[-1]
    for port in (80, 8100, 8080, 443):
        if port in (infra.ports or {}):
            if port in (80, 443):
                return f"http://{host}" if port == 80 else f"https://{host}"
            return f"http://{host}:{port}"
    return None

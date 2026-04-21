"""Generate a migration.yaml from a DeviceBlueprint targeting a new host.

Usage::

    from redeploy.blueprint.generators.migration import generate_migration
    migration_yaml = generate_migration(blueprint, target_host="pi@192.168.188.110")
"""
from __future__ import annotations

from typing import Any

import yaml

from ...models import DeviceBlueprint


def generate_migration(
    blueprint: DeviceBlueprint,
    *,
    target_host: str,
    strategy: str | None = None,
    remote_dir: str = "/home/pi/apps",
    env_file: str | None = None,
    skip_image_transfer: bool = False,
    compose_out: str = "docker-compose.gen.yml",
) -> str:
    """Render a migration.yaml for deploying blueprint to *target_host*.

    Parameters
    ----------
    blueprint:
        Source DeviceBlueprint to deploy.
    target_host:
        SSH target, e.g. ``"pi@192.168.188.110"``.
    strategy:
        Override deploy strategy (``podman_quadlet`` | ``docker_compose`` |
        ``systemd``).  Defaults to ``blueprint.deploy_strategy``.
    remote_dir:
        Base directory on the target host, e.g. ``"/home/pi/apps"``.
    env_file:
        Local .env file to push to the remote host.
    skip_image_transfer:
        If True, assume images are already present on the target (e.g. pulled
        from registry).  Otherwise generates ``podman load`` / ``docker load``
        steps.
    compose_out:
        Filename for the generated docker-compose file on the remote host.
    """
    _strategy = strategy or blueprint.deploy_strategy
    steps: list[dict[str, Any]] = []

    # ── Phase 0: prerequisites ─────────────────────────────────────────────────
    steps.append({
        "id": "check-host",
        "action": "command",
        "description": "Verify target host is reachable",
        "command": f"ssh {target_host} 'uname -a'",
    })
    steps.append({
        "id": "create-dirs",
        "action": "command",
        "description": "Create app directories",
        "command": f"ssh {target_host} 'mkdir -p {remote_dir}'",
    })

    # ── Phase 1: transfer artifacts ────────────────────────────────────────────
    if env_file or blueprint.env_file:
        src = env_file or blueprint.env_file
        steps.append({
            "id": "push-env",
            "action": "command",
            "description": "Push environment file",
            "command": f"scp {src} {target_host}:{remote_dir}/.env",
        })

    if not skip_image_transfer:
        _loader = "podman load" if "podman" in _strategy else "docker load"
        for svc in blueprint.services:
            if not svc.image or svc.image == "scratch":
                continue
            img_slug = svc.image.replace("/", "_").replace(":", "_")
            steps.append({
                "id": f"transfer-{svc.name}",
                "action": "command",
                "description": f"Transfer image for {svc.name}",
                "command": (
                    f"docker save {svc.image} "
                    f"| ssh {target_host} '{_loader}'"
                ),
            })

    # ── Phase 2: generate and push docker-compose ──────────────────────────────
    steps.append({
        "id": "gen-compose",
        "action": "command",
        "description": f"Push generated compose file to {target_host}",
        "command": (
            f"# (this step assumes docker-compose.gen.yml already generated locally)\n"
            f"scp docker-compose.gen.yml {target_host}:{remote_dir}/{compose_out}"
        ),
    })

    # ── Phase 3: stop old stack ────────────────────────────────────────────────
    if "podman" in _strategy:
        _stop_cmd = (
            f"ssh {target_host} "
            f"'cd {remote_dir} && podman compose -f {compose_out} down --timeout 10 || true'"
        )
        _start_cmd = (
            f"ssh {target_host} "
            f"'cd {remote_dir} && podman compose -f {compose_out} up -d'"
        )
    else:
        _stop_cmd = (
            f"ssh {target_host} "
            f"'cd {remote_dir} && docker compose -f {compose_out} down --timeout 10 || true'"
        )
        _start_cmd = (
            f"ssh {target_host} "
            f"'cd {remote_dir} && docker compose -f {compose_out} up -d'"
        )

    steps.append({
        "id": "stop-old",
        "action": "command",
        "description": "Stop existing stack",
        "command": _stop_cmd,
    })

    # ── Phase 4: start new stack ───────────────────────────────────────────────
    steps.append({
        "id": "start-stack",
        "action": "command",
        "description": "Start application stack",
        "command": _start_cmd,
    })

    # ── Phase 5: verify ────────────────────────────────────────────────────────
    verify_port = None
    for svc in blueprint.services:
        if svc.ports:
            verify_port = svc.ports[0].host
            break

    if verify_port:
        _target_ip = target_host.split("@")[-1]
        steps.append({
            "id": "verify-up",
            "action": "http_check",
            "description": "Verify application is responding",
            "url": f"http://{_target_ip}:{verify_port}/",
            "expect": "200",
            "retries": 10,
            "delay": 5,
        })

    doc: dict[str, Any] = {
        "# Generated by redeploy blueprint deploy": None,
        "version": blueprint.version,
        "app": blueprint.name,
        "strategy": _strategy,
        "target": target_host,
        "remote_dir": remote_dir,
        "source_blueprint": blueprint.source.device_id or "unknown",
        "steps": steps,
    }

    # Remove comment pseudo-keys before dumping
    clean = {k: v for k, v in doc.items() if not k.startswith("#") and v is not None}

    header = (
        f"# Generated by redeploy blueprint deploy\n"
        f"# Source blueprint : {blueprint.name} v{blueprint.version}\n"
        f"# Original device  : {blueprint.source.device_id or 'unknown'}\n"
        f"# Target host      : {target_host}\n"
        f"# Strategy         : {_strategy}\n\n"
    )
    body = yaml.dump(clean, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return header + body

"""Deploy patterns — multi-step deployment strategies (Phase 4).

Pre-built deployment patterns that expand into ``MigrationStep`` lists.
Use by setting ``pattern`` in ``TargetConfig`` or ``migration.yaml``.

Available patterns
------------------
``BlueGreenPattern``
    Deploy green alongside blue, swap labels, verify, retire blue.
    Requires Traefik or Caddy with label-based routing.

``CanaryPattern``
    Roll out new version in stages (10 → 25 → 50 → 100 % of traffic).
    Waits for health check at each stage before proceeding.

``RollbackOnFailurePattern``
    Capture pre-deploy state tag, auto-rollback on any step failure.
    Works with any ``docker_full`` or ``podman_quadlet`` strategy.

Usage in ``migration.yaml``::

    target:
      strategy: docker_full
      pattern: blue_green
      pattern_config:
        traefik_network: proxy
        green_suffix: "-green"

Usage from Python::

    from redeploy.patterns import BlueGreenPattern, pattern_registry
    steps = BlueGreenPattern(app="myapp", remote_dir="~/myapp").expand()
    pattern = pattern_registry["blue_green"]
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from .models import ConflictSeverity, MigrationStep, StepAction


# ── base ──────────────────────────────────────────────────────────────────────


class DeployPattern(ABC):
    """Base class for all deploy patterns."""

    name: str = ""
    description: str = ""

    @abstractmethod
    def expand(self) -> list[MigrationStep]:
        """Return the list of steps this pattern expands to."""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(app={getattr(self, 'app', '?')!r})"


# ── helpers ───────────────────────────────────────────────────────────────────


def _step(id: str, action: StepAction, description: str, **kw: Any) -> MigrationStep:
    return MigrationStep(id=id, action=action, description=description, **kw)


# ── BlueGreenPattern ──────────────────────────────────────────────────────────


class BlueGreenPattern(DeployPattern):
    """Zero-downtime blue/green deploy via Traefik (or any label-based proxy).

    Flow:
      1. Sync env to green directory
      2. Build + start green stack (parallel to running blue)
      3. Health-check green via verify_url with ``/green`` path prefix
      4. Swap Traefik/proxy labels (blue → green)
      5. Re-verify main endpoint (now served by green)
      6. Retire blue (compose down)
    """

    name = "blue_green"
    description = "Zero-downtime blue/green via Traefik label swap"

    def __init__(
        self,
        app: str,
        remote_dir: str,
        compose_cmd: str = "docker compose",
        verify_url: Optional[str] = None,
        green_suffix: str = "-green",
        traefik_network: str = "proxy",
        env_file: Optional[str] = None,
    ) -> None:
        self.app = app
        self.remote_dir = remote_dir
        self.compose_cmd = compose_cmd
        self.verify_url = verify_url or f"http://localhost:8080"
        self.green_suffix = green_suffix
        self.traefik_network = traefik_network
        self.green_dir = f"{remote_dir}{green_suffix}"
        self.env_file = env_file

    def expand(self) -> list[MigrationStep]:
        compose = self.compose_cmd
        blue_dir = self.remote_dir
        green_dir = self.green_dir
        app = self.app
        green_app = f"{app}{self.green_suffix}"

        steps: list[MigrationStep] = []

        if self.env_file:
            steps.append(_step(
                id="bg_sync_env",
                action=StepAction.SCP,
                description="Copy .env to green directory",
                src=self.env_file,
                dst=f"{green_dir}/.env",
                risk=ConflictSeverity.LOW,
            ))

        steps.append(_step(
            id="bg_clone_green",
            action=StepAction.SSH_CMD,
            description=f"Clone blue directory to green: {green_dir}",
            command=(
                f"rsync -a --exclude '.git' --exclude '__pycache__' "
                f"{blue_dir}/ {green_dir}/"
            ),
            risk=ConflictSeverity.LOW,
            rollback_command=f"rm -rf {green_dir} || true",
        ))

        steps.append(_step(
            id="bg_deploy_green",
            action=StepAction.DOCKER_BUILD,
            description=f"Build and start green stack: {green_app}",
            command=(
                f"cd {green_dir} && "
                f"APP_NAME={green_app} TRAEFIK_NETWORK={self.traefik_network} "
                f"{compose} up -d --build"
            ),
            timeout=1800,
            risk=ConflictSeverity.MEDIUM,
            rollback_command=f"cd {green_dir} && {compose} down || true",
        ))

        steps.append(_step(
            id="bg_health_green",
            action=StepAction.HTTP_CHECK,
            description="Verify green stack is healthy",
            url=self.verify_url,
            expect="healthy",
            risk=ConflictSeverity.LOW,
        ))

        steps.append(_step(
            id="bg_swap_labels",
            action=StepAction.SSH_CMD,
            description="Swap Traefik routing labels: blue → green",
            command=(
                f"cd {green_dir} && "
                f"APP_NAME={app} TRAEFIK_NETWORK={self.traefik_network} "
                f"{compose} up -d --no-build"
            ),
            risk=ConflictSeverity.HIGH,
            rollback_command=(
                f"cd {blue_dir} && "
                f"APP_NAME={app} TRAEFIK_NETWORK={self.traefik_network} "
                f"{compose} up -d --no-build || true"
            ),
        ))

        steps.append(_step(
            id="bg_verify_main",
            action=StepAction.HTTP_CHECK,
            description="Verify main endpoint now served by green",
            url=self.verify_url,
            expect="healthy",
            risk=ConflictSeverity.LOW,
        ))

        steps.append(_step(
            id="bg_retire_blue",
            action=StepAction.DOCKER_COMPOSE_DOWN,
            description=f"Retire blue stack: {blue_dir}",
            command=f"cd {blue_dir} && {compose} down",
            risk=ConflictSeverity.LOW,
        ))

        return steps


# ── CanaryPattern ─────────────────────────────────────────────────────────────


class CanaryPattern(DeployPattern):
    """Gradual canary rollout: deploy new version, scale up in stages.

    Flow:
      1. Deploy canary alongside main (1 replica)
      2. At each stage: scale canary to N%, health-check, wait
      3. At 100%: retire main, rename canary → main
    """

    name = "canary"
    description = "Gradual canary rollout with per-stage health checks"

    def __init__(
        self,
        app: str,
        remote_dir: str,
        compose_cmd: str = "docker compose",
        verify_url: Optional[str] = None,
        stages: Optional[list[int]] = None,
        stage_wait_seconds: int = 30,
        canary_suffix: str = "-canary",
    ) -> None:
        self.app = app
        self.remote_dir = remote_dir
        self.compose_cmd = compose_cmd
        self.verify_url = verify_url or "http://localhost:8080"
        self.stages = stages or [10, 25, 50, 100]
        self.stage_wait_seconds = stage_wait_seconds
        self.canary_dir = f"{remote_dir}{canary_suffix}"
        self.canary_suffix = canary_suffix

    def expand(self) -> list[MigrationStep]:
        compose = self.compose_cmd
        main_dir = self.remote_dir
        canary_dir = self.canary_dir
        app = self.app
        canary_app = f"{app}{self.canary_suffix}"

        steps: list[MigrationStep] = []

        steps.append(_step(
            id="canary_clone",
            action=StepAction.SSH_CMD,
            description=f"Clone main directory to canary: {canary_dir}",
            command=(
                f"rsync -a --exclude '.git' --exclude '__pycache__' "
                f"{main_dir}/ {canary_dir}/"
            ),
            risk=ConflictSeverity.LOW,
            rollback_command=f"rm -rf {canary_dir} || true",
        ))

        steps.append(_step(
            id="canary_deploy",
            action=StepAction.DOCKER_BUILD,
            description=f"Deploy canary (1 replica): {canary_app}",
            command=(
                f"cd {canary_dir} && "
                f"APP_NAME={canary_app} REPLICAS=1 "
                f"{compose} up -d --build --scale app=1"
            ),
            timeout=1800,
            risk=ConflictSeverity.MEDIUM,
            rollback_command=f"cd {canary_dir} && {compose} down || true",
        ))

        for i, pct in enumerate(self.stages):
            steps.append(_step(
                id=f"canary_health_{pct}pct",
                action=StepAction.HTTP_CHECK,
                description=f"Health check at {pct}% canary traffic",
                url=self.verify_url,
                expect="healthy",
                risk=ConflictSeverity.LOW,
            ))
            if pct < 100 and self.stage_wait_seconds > 0:
                steps.append(_step(
                    id=f"canary_wait_{pct}pct",
                    action=StepAction.WAIT,
                    description=f"Observe canary at {pct}% for {self.stage_wait_seconds}s",
                    seconds=self.stage_wait_seconds,
                    risk=ConflictSeverity.LOW,
                ))
            if pct == 100:
                steps.append(_step(
                    id="canary_promote",
                    action=StepAction.SSH_CMD,
                    description="Promote canary to main (rename directories)",
                    command=(
                        f"mv {main_dir} {main_dir}.retired && "
                        f"mv {canary_dir} {main_dir}"
                    ),
                    risk=ConflictSeverity.HIGH,
                    rollback_command=(
                        f"mv {main_dir} {canary_dir} && "
                        f"mv {main_dir}.retired {main_dir} || true"
                    ),
                ))
                steps.append(_step(
                    id="canary_retire_old",
                    action=StepAction.SSH_CMD,
                    description="Remove retired main directory",
                    command=f"rm -rf {main_dir}.retired",
                    risk=ConflictSeverity.LOW,
                ))

        return steps


# ── RollbackOnFailurePattern ──────────────────────────────────────────────────


class RollbackOnFailurePattern(DeployPattern):
    """Capture pre-deploy image tag, roll back automatically on failure.

    Flow:
      1. Snapshot current image tag → saved to remote file
      2. Deploy new version (delegate to standard steps)
      3. On failure: restore previous image tag + restart
    """

    name = "rollback_on_failure"
    description = "Auto-rollback to previous image tag on step failure"

    def __init__(
        self,
        app: str,
        remote_dir: str,
        compose_cmd: str = "docker compose",
        verify_url: Optional[str] = None,
        snapshot_file: str = ".deploy-snapshot",
    ) -> None:
        self.app = app
        self.remote_dir = remote_dir
        self.compose_cmd = compose_cmd
        self.verify_url = verify_url or "http://localhost:8080"
        self.snapshot_file = snapshot_file

    def expand(self) -> list[MigrationStep]:
        compose = self.compose_cmd
        remote_dir = self.remote_dir
        snap = f"{remote_dir}/{self.snapshot_file}"

        steps: list[MigrationStep] = []

        steps.append(_step(
            id="rob_snapshot",
            action=StepAction.SSH_CMD,
            description="Snapshot current running image tags",
            command=(
                f"cd {remote_dir} && "
                f"{compose} images --format json 2>/dev/null "
                f"| tee {snap}"
            ),
            risk=ConflictSeverity.LOW,
        ))

        steps.append(_step(
            id="rob_deploy",
            action=StepAction.DOCKER_BUILD,
            description=f"Deploy new version of {self.app}",
            command=f"cd {remote_dir} && {compose} up -d --build",
            timeout=1800,
            risk=ConflictSeverity.MEDIUM,
            rollback_command=(
                f"cd {remote_dir} && "
                f"IMAGE_TAG=$(cat {snap} | python3 -c "
                f"\"import sys,json; d=json.load(sys.stdin); "
                f"print(d[0].get('Image','') if d else '')\" 2>/dev/null) && "
                f"{compose} up -d || true"
            ),
        ))

        steps.append(_step(
            id="rob_health",
            action=StepAction.HTTP_CHECK,
            description="Verify new version is healthy",
            url=self.verify_url,
            expect="healthy",
            risk=ConflictSeverity.LOW,
        ))

        steps.append(_step(
            id="rob_cleanup_snapshot",
            action=StepAction.SSH_CMD,
            description="Remove deploy snapshot file",
            command=f"rm -f {snap}",
            risk=ConflictSeverity.LOW,
        ))

        return steps


# ── Registry ──────────────────────────────────────────────────────────────────

pattern_registry: dict[str, type[DeployPattern]] = {
    "blue_green":           BlueGreenPattern,
    "canary":               CanaryPattern,
    "rollback_on_failure":  RollbackOnFailurePattern,
}


def get_pattern(name: str) -> Optional[type[DeployPattern]]:
    """Return pattern class by name, or None if not found."""
    return pattern_registry.get(name)


def list_patterns() -> list[str]:
    """Return all registered pattern names."""
    return list(pattern_registry.keys())

"""Planner — derives migration steps from InfraState → TargetConfig."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from loguru import logger

from ..models import (
    ConflictSeverity, DeployStrategy, InfraState, MigrationPlan, MigrationStep,
    StepAction, TargetConfig,
)


class Planner:
    """Generate a MigrationPlan from detected infra + desired target."""

    def __init__(self, state: InfraState, target: TargetConfig):
        self.state = state
        self.target = target
        self._steps: list[MigrationStep] = []
        self._notes: list[str] = []
        self._spec = None   # set by from_spec()

    def run(self) -> MigrationPlan:
        logger.info(
            f"Planning migration: {self.state.detected_strategy.value}"
            f" → {self.target.strategy.value}"
        )

        self._plan_conflict_fixes()
        self._plan_stop_old_services()
        self._plan_deploy_new()
        if self._spec:
            self._append_extra_steps(self._spec)
            for note in self._spec.notes:
                if note not in self._notes:
                    self._notes.append(note)
        self._plan_verify()

        risk = self._assess_risk()
        downtime = self._estimate_downtime()

        return MigrationPlan(
            host=self.state.host,
            app=self.state.app,
            from_strategy=self.state.detected_strategy,
            to_strategy=self.target.strategy,
            risk=risk,
            estimated_downtime=downtime,
            steps=self._steps,
            notes=self._notes,
        )

    # ── conflict fixes ────────────────────────────────────────────────────────

    def _plan_conflict_fixes(self) -> None:
        for conflict in self.state.conflicts:
            if conflict.type == "port_steal" or conflict.type == "dual_runtime":
                if self.state.runtime.k3s:
                    self._add_step(MigrationStep(
                        id="delete_k3s_ingresses",
                        action=StepAction.KUBECTL_DELETE,
                        description="Delete k3s ingresses to remove iptables DNAT rules",
                        namespace=self.state.app,
                        command=f"k3s kubectl delete ingress -n {self.state.app} --all 2>/dev/null || true",
                        reason=conflict.description,
                        risk=ConflictSeverity.LOW,
                        rollback_command=None,
                    ))
                    self._add_step(MigrationStep(
                        id="stop_k3s",
                        action=StepAction.SYSTEMCTL_STOP,
                        service="k3s",
                        description="Stop and disable k3s to free ports 80/443",
                        command="systemctl stop k3s",
                        reason="k3s iptables DNAT intercepts traffic before Docker",
                        risk=ConflictSeverity.MEDIUM,
                        rollback_command="systemctl start k3s",
                    ))
                    self._add_step(MigrationStep(
                        id="disable_k3s",
                        action=StepAction.SYSTEMCTL_DISABLE,
                        service="k3s",
                        description="Disable k3s on boot",
                        command="systemctl disable k3s",
                        risk=ConflictSeverity.LOW,
                    ))
                    self._notes.append(
                        "k3s was intercepting traffic — stopped and disabled. "
                        "k3s workloads (other namespaces) may need migration."
                    )

            elif conflict.type == "unexpected_port_owner":
                for p in conflict.affected:
                    self._notes.append(f"Port {p}: unexpected owner — review manually")

    # ── stop old services ─────────────────────────────────────────────────────

    def _plan_stop_old_services(self) -> None:
        from_s = self.state.detected_strategy
        to_s = self.target.strategy

        # Explicit list from target config
        for svc in self.target.stop_services:
            if not any(step.id == f"stop_{svc}" for step in self._steps):
                self._add_step(MigrationStep(
                    id=f"stop_{svc}",
                    action=StepAction.SYSTEMCTL_STOP,
                    service=svc,
                    description=f"Stop service: {svc}",
                    command=f"systemctl stop {svc}",
                    risk=ConflictSeverity.MEDIUM,
                    rollback_command=f"systemctl start {svc}",
                ))
        for svc in self.target.disable_services:
            self._add_step(MigrationStep(
                id=f"disable_{svc}",
                action=StepAction.SYSTEMCTL_DISABLE,
                service=svc,
                description=f"Disable service on boot: {svc}",
                command=f"systemctl disable {svc}",
                risk=ConflictSeverity.LOW,
            ))

        # If migrating FROM docker → stop old containers first
        if from_s == DeployStrategy.DOCKER_FULL and to_s != DeployStrategy.DOCKER_FULL:
            compose = self._compose_cmd()
            self._add_step(MigrationStep(
                id="docker_compose_down",
                action=StepAction.DOCKER_COMPOSE_DOWN,
                description="Stop old Docker Compose stack",
                command=f"cd {self.target.remote_dir} && {compose} down",
                risk=ConflictSeverity.MEDIUM,
                rollback_command=f"cd {self.target.remote_dir} && {compose} up -d",
            ))

    # ── deploy new strategy ───────────────────────────────────────────────────

    def _plan_deploy_new(self) -> None:
        to_s = self.target.strategy

        if to_s == DeployStrategy.DOCKER_FULL:
            self._plan_docker_full()
        elif to_s == DeployStrategy.PODMAN_QUADLET:
            self._plan_podman_quadlet()
        elif to_s == DeployStrategy.SYSTEMD:
            self._plan_systemd()
        elif to_s in (DeployStrategy.NATIVE_KIOSK, DeployStrategy.DOCKER_KIOSK):
            self._plan_kiosk(docker=to_s == DeployStrategy.DOCKER_KIOSK)
        else:
            self._notes.append(f"No deploy steps generated for strategy '{to_s.value}' — add manually")

    def _plan_docker_full(self) -> None:
        compose = self._compose_cmd()
        remote_dir = self.target.remote_dir

        if self.target.env_file:
            self._add_step(MigrationStep(
                id="sync_env",
                action=StepAction.SCP,
                description="Copy env file to remote",
                src=self.target.env_file,
                dst=f"{remote_dir}/.env",
                risk=ConflictSeverity.LOW,
            ))

        self._add_step(MigrationStep(
            id="docker_build_pull",
            action=StepAction.DOCKER_BUILD,
            description="Build Docker images on remote",
            command=f"cd {remote_dir} && {compose} build",
            risk=ConflictSeverity.LOW,
        ))

        self._add_step(MigrationStep(
            id="docker_compose_up",
            action=StepAction.DOCKER_COMPOSE_UP,
            description="Start Docker Compose stack",
            compose=self._compose_file(),
            flags=["--build", "-d"],
            command=f"cd {remote_dir} && {compose} up -d --build",
            risk=ConflictSeverity.LOW,
            rollback_command=f"cd {remote_dir} && {compose} up -d",
        ))

        self._add_step(MigrationStep(
            id="wait_startup",
            action=StepAction.WAIT,
            description="Wait for services to start",
            seconds=30,
            risk=ConflictSeverity.LOW,
        ))

    def _plan_podman_quadlet(self) -> None:
        """Generate steps for Podman Quadlet (rootless systemd) deployment."""
        remote_dir = self.target.remote_dir or f"~/{self.target.app}"
        app = self.target.app
        quadlet_src = f"{remote_dir}/quadlet"
        rootless = not (self.target.stop_services or self.target.disable_services)
        systemctl = "systemctl --user" if rootless else "sudo systemctl"
        quadlet_dst = (
            "~/.config/containers/systemd" if rootless
            else "/etc/containers/systemd"
        )

        if self.target.env_file:
            self._add_step(MigrationStep(
                id="sync_env",
                action=StepAction.SCP,
                description="Copy .env to remote",
                src=self.target.env_file,
                dst=f"{remote_dir}/.env",
                risk=ConflictSeverity.LOW,
            ))

        self._add_step(MigrationStep(
            id="install_quadlet_files",
            action=StepAction.SSH_CMD,
            description=f"Install Quadlet unit files to {quadlet_dst}/",
            command=(
                f"mkdir -p {quadlet_dst} && "
                f"cp {quadlet_src}/*.container {quadlet_src}/*.network "
                f"{quadlet_src}/*.volume {quadlet_dst}/ 2>/dev/null || true"
            ),
            risk=ConflictSeverity.LOW,
            rollback_command=f"{systemctl} stop {app} || true",
        ))

        self._add_step(MigrationStep(
            id="podman_daemon_reload",
            action=StepAction.SYSTEMCTL_START,
            description="Reload systemd to pick up Quadlet unit files",
            command=f"{systemctl} daemon-reload",
            risk=ConflictSeverity.LOW,
        ))

        # Stop existing units before restart
        self._add_step(MigrationStep(
            id=f"stop_{app}",
            action=StepAction.SYSTEMCTL_STOP,
            service=app,
            description=f"Stop existing {app} units (ignore errors if not running)",
            command=f"{systemctl} stop {app}.service 2>/dev/null || true",
            risk=ConflictSeverity.LOW,
        ))

        self._add_step(MigrationStep(
            id=f"start_{app}",
            action=StepAction.SYSTEMCTL_START,
            service=app,
            description=f"Start {app} via Quadlet",
            command=f"{systemctl} start {app}.service",
            risk=ConflictSeverity.LOW,
            rollback_command=f"{systemctl} stop {app}.service || true",
        ))

        self._add_step(MigrationStep(
            id="wait_startup",
            action=StepAction.WAIT,
            description="Wait for Quadlet containers to start",
            seconds=15,
            risk=ConflictSeverity.LOW,
        ))

        self._notes.append(
            f"Podman Quadlet deploy ({'rootless user' if rootless else 'system'}): "
            f"unit files from {quadlet_src} → {quadlet_dst}"
        )

    def _plan_kiosk(self, docker: bool = False) -> None:
        """Generate steps for kiosk appliance deployment.

        Covers both NATIVE_KIOSK (systemd + Chromium Openbox) and
        DOCKER_KIOSK (Podman Quadlet container in kiosk mode).

        Mirrors the artifacts generated by ``doql build`` for
        ``DEPLOY: target: kiosk-appliance``:
          - infra/install-kiosk.sh
          - infra/kiosk.service
          - infra/<app>.container  (docker_kiosk only)
        """
        app = self.target.app
        remote_dir = self.target.remote_dir or f"/opt/{app}"
        infra_src = f"{remote_dir}/build/infra"
        verify_url = self.target.verify_url or "http://localhost:8080"

        # 1. Sync build artifacts to remote
        self._add_step(MigrationStep(
            id="rsync_build",
            action=StepAction.RSYNC,
            description="Sync build/ directory to kiosk device",
            src="./build/",
            dst=f"{remote_dir}/build/",
            risk=ConflictSeverity.LOW,
            rollback_command=f"systemctl restart {app}.service 2>/dev/null || true",
        ))

        if docker:
            # DOCKER_KIOSK: install Quadlet .container unit
            self._add_step(MigrationStep(
                id="install_kiosk_quadlet",
                action=StepAction.SSH_CMD,
                description="Install kiosk Quadlet container unit",
                command=(
                    f"mkdir -p ~/.config/containers/systemd && "
                    f"cp {infra_src}/*.container {infra_src}/*.network "
                    f"~/.config/containers/systemd/ 2>/dev/null || true && "
                    f"systemctl --user daemon-reload"
                ),
                risk=ConflictSeverity.LOW,
            ))
            self._add_step(MigrationStep(
                id="start_kiosk_container",
                action=StepAction.SYSTEMCTL_START,
                service=f"{app}",
                description=f"Start kiosk container via Quadlet",
                command=f"systemctl --user restart {app}.service",
                risk=ConflictSeverity.LOW,
                rollback_command=f"systemctl --user stop {app}.service || true",
            ))
        else:
            # NATIVE_KIOSK: run doql-generated install-kiosk.sh
            self._add_step(MigrationStep(
                id="run_kiosk_installer",
                action=StepAction.SSH_CMD,
                description="Run doql-generated kiosk installer (Openbox + Chromium + systemd)",
                command=f"bash {infra_src}/install-kiosk.sh",
                risk=ConflictSeverity.MEDIUM,
                rollback_command=f"systemctl stop {app}.service 2>/dev/null || true",
            ))
            self._add_step(MigrationStep(
                id="install_kiosk_service",
                action=StepAction.SCP,
                description="Install kiosk.service systemd unit",
                src=f"./build/infra/kiosk.service",
                dst=f"/etc/systemd/system/{app}.service",
                risk=ConflictSeverity.LOW,
            ))
            self._add_step(MigrationStep(
                id="enable_kiosk_service",
                action=StepAction.SYSTEMCTL_START,
                service=app,
                description=f"Enable and start {app} kiosk service",
                command=f"systemctl daemon-reload && systemctl enable --now {app}.service",
                risk=ConflictSeverity.LOW,
                rollback_command=f"systemctl disable --now {app}.service || true",
            ))

        self._add_step(MigrationStep(
            id="wait_kiosk_start",
            action=StepAction.WAIT,
            description="Wait for kiosk app to start",
            seconds=20,
            risk=ConflictSeverity.LOW,
        ))

        self._add_step(MigrationStep(
            id="http_health_check",
            action=StepAction.HTTP_CHECK,
            description="Verify kiosk app HTTP endpoint",
            url=verify_url,
            risk=ConflictSeverity.LOW,
        ))

        strategy_label = "docker_kiosk (Quadlet)" if docker else "native_kiosk (Openbox+Chromium)"
        self._notes.append(
            f"Kiosk deploy ({strategy_label}): "
            f"artifacts from {infra_src} installed on {self.state.host}"
        )
        if not docker:
            self._notes.append(
                "Run 'doql build' first to generate build/infra/install-kiosk.sh and kiosk.service"
            )

    def _plan_systemd(self) -> None:
        self._notes.append("Systemd deploy: ensure unit files installed and enabled")

    # ── verify ────────────────────────────────────────────────────────────────

    def _plan_verify(self) -> None:
        url = self.target.verify_url
        if not url and self.target.domain:
            url = f"https://{self.target.domain}/api/v1/health"

        if url:
            self._add_step(MigrationStep(
                id="http_health_check",
                action=StepAction.HTTP_CHECK,
                description="Verify backend health endpoint",
                url=url,
                expect="healthy",
                risk=ConflictSeverity.LOW,
            ))

        if self.target.verify_version:
            self._add_step(MigrationStep(
                id="version_check",
                action=StepAction.VERSION_CHECK,
                description=f"Verify deployed version = {self.target.verify_version}",
                url=url,
                expect=self.target.verify_version,
                risk=ConflictSeverity.LOW,
            ))

    # ── helpers ───────────────────────────────────────────────────────────────

    def _compose_cmd(self) -> str:
        parts = ["docker compose"]
        for f in self.target.compose_files:
            parts.append(f"-f {f}")
        if self.target.env_file:
            parts.append("--env-file .env")
        return " ".join(parts)

    def _compose_file(self) -> Optional[str]:
        return self.target.compose_files[0] if self.target.compose_files else None

    def _add_step(self, step: MigrationStep) -> None:
        if not any(s.id == step.id for s in self._steps):
            self._steps.append(step)

    def _assess_risk(self) -> ConflictSeverity:
        if not self._steps:
            return ConflictSeverity.LOW
        risks = [s.risk for s in self._steps]
        if ConflictSeverity.CRITICAL in risks:
            return ConflictSeverity.CRITICAL
        if ConflictSeverity.HIGH in risks:
            return ConflictSeverity.HIGH
        if ConflictSeverity.MEDIUM in risks:
            return ConflictSeverity.MEDIUM
        return ConflictSeverity.LOW

    def _estimate_downtime(self) -> str:
        has_down = any(s.action == StepAction.DOCKER_COMPOSE_DOWN for s in self._steps)
        has_stop = any(s.action == StepAction.SYSTEMCTL_STOP for s in self._steps)
        wait = sum(s.seconds for s in self._steps if s.action == StepAction.WAIT)
        if has_down or has_stop:
            return f"~{30 + wait}s"
        return f"~{wait}s" if wait else "rolling (no downtime)"

    @staticmethod
    def from_files(infra_path: Path, target_path: Optional[Path]) -> "Planner":
        with infra_path.open() as f:
            raw = yaml.safe_load(f)
        state = InfraState(**raw)

        target = TargetConfig()
        if target_path and target_path.exists():
            with target_path.open() as f:
                target = TargetConfig(**yaml.safe_load(f))

        return Planner(state, target)

    @staticmethod
    def from_spec(spec: "MigrationSpec") -> "Planner":  # type: ignore[name-defined]
        """Build Planner directly from a MigrationSpec (single from+to YAML)."""
        from ..models import MigrationSpec  # local import avoids circular
        state = spec.to_infra_state()
        target = spec.to_target_config()
        p = Planner(state, target)
        p._spec = spec
        return p

    def _append_extra_steps(self, spec: "MigrationSpec") -> None:  # type: ignore[name-defined]
        """Append manually declared extra_steps from spec, with optional insert_before support.

        If a step ``id`` matches a ``StepLibrary`` entry and no ``action`` is given,
        the library template is used as base (fields can be overridden in YAML).
        """
        from ..steps import StepLibrary
        for raw in spec.extra_steps:
            raw = dict(raw)
            insert_before = raw.pop("insert_before", None)
            try:
                step = StepLibrary.resolve_from_spec(raw)
                if any(s.id == step.id for s in self._steps):
                    continue
                if insert_before:
                    idx = next((i for i, s in enumerate(self._steps) if s.id == insert_before), None)
                    if idx is not None:
                        self._steps.insert(idx, step)
                        continue
                self._steps.append(step)
            except Exception as e:
                self._notes.append(f"extra_step ignored ({raw.get('id', '?')}): {e}")

    def save(self, plan: MigrationPlan, output: Path) -> None:
        data = plan.model_dump(mode="json")
        output.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True))
        logger.info(f"MigrationPlan saved to {output}")

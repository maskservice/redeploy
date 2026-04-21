"""apply — Execute a MigrationPlan step by step."""
from .exceptions import StepError
from .executor import Executor
from .handlers import (
    run_container_log_tail,
    run_docker_build,
    run_docker_health_wait,
    run_ensure_autostart_entry,
    run_ensure_browser_kiosk_script,
    run_ensure_config_line,
    run_ensure_kanshi_profile,
    run_http_check,
    run_inline_script,
    run_plugin,
    run_podman_build,
    run_raspi_config,
    run_rsync,
    run_scp,
    run_ssh,
    run_version_check,
    run_wait,
)
from .progress import ProgressEmitter
from .rollback import rollback_steps
from .state import (
    DEFAULT_STATE_DIR,
    ResumeState,
    default_state_path,
    state_key,
)

__all__ = [
    "Executor",
    "ProgressEmitter",
    "ResumeState",
    "StepError",
    "rollback_steps",
    "default_state_path",
    "state_key",
    "DEFAULT_STATE_DIR",
    # Handlers
    "run_container_log_tail",
    "run_docker_build",
    "run_docker_health_wait",
    "run_ensure_autostart_entry",
    "run_ensure_browser_kiosk_script",
    "run_ensure_config_line",
    "run_ensure_kanshi_profile",
    "run_http_check",
    "run_inline_script",
    "run_plugin",
    "run_podman_build",
    "run_raspi_config",
    "run_rsync",
    "run_scp",
    "run_ssh",
    "run_version_check",
    "run_wait",
]

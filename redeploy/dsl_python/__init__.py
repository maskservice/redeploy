"""redeploy Python-native DSL — imperative deployment definitions.

This module provides a Python-native alternative to YAML migration specs.
Instead of writing complex YAML with shell strings, define deployments
in pure Python with full IDE support, type hints, and testability.

Example migration.py:
    from redeploy.dsl_python import migration, step, ssh, rsync, docker

    @migration(name="c2004 rpi5 deploy", version="1.0.22")
    def deploy():
        with step("restart_rpi5", risk="high", timeout=120):
            ssh("pi@192.168.188.108", "sudo shutdown -r now")
            wait(seconds=90)
            ssh_available("pi@192.168.188.108", timeout=60)

        with step("rsync_code", risk="low"):
            rsync(
                src="/home/tom/c2004/",
                dst="pi@192.168.188.108:~/c2004",
                exclude=[".git", ".venv", "__pycache__"]
            )

        with step("docker_deploy", risk="low"):
            docker.compose_up(
                host="pi@192.168.188.108",
                project_dir="~/c2004",
                files=["docker-compose.yml"],
                env_file=".env",
                build=True,
                wait_healthy=True
            )

Run with:
    $ redeploy run migration.py

Benefits over YAML:
- Full Python power (loops, conditionals, variables)
- Type hints and IDE autocomplete
- Unit testable with pytest
- Reusable step definitions via imports
- Debuggable with breakpoints
"""

from .decorators import migration, step
from .steps import (
    ssh,
    ssh_available,
    rsync,
    scp,
    wait,
    http_expect,
    version_check,
)
from .docker_steps import docker
from .context import StepContext
from .exceptions import StepError, TimeoutError, VerificationError

__all__ = [
    # Decorators
    "migration",
    "step",
    # Actions
    "ssh",
    "ssh_available",
    "rsync",
    "scp",
    "wait",
    "http_expect",
    "version_check",
    "docker",
    # Context & Exceptions
    "StepContext",
    "StepError",
    "TimeoutError",
    "VerificationError",
]

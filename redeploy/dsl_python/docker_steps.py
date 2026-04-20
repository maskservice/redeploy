"""Docker deployment steps for Python-native DSL."""
import subprocess
import time
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from .exceptions import StepError, TimeoutError


@dataclass
class DockerComposeResult:
    """Result of docker compose command."""
    success: bool
    stdout: str
    stderr: str
    services: Dict[str, Any] = None


class DockerDSL:
    """Docker-related DSL actions."""

    def compose_up(
        self,
        host: Optional[str] = None,
        project_dir: str = "~/c2004",
        files: Optional[List[str]] = None,
        env_file: Optional[str] = None,
        build: bool = True,
        wait_healthy: bool = True,
        timeout: int = 300,
    ) -> DockerComposeResult:
        """Run docker compose up on a remote or local host.

        Args:
            host: SSH host (None for local)
            project_dir: Project directory on host
            files: Compose files to use
            env_file: Environment file
            build: Build images before starting
            wait_healthy: Wait for services to be healthy
            timeout: Timeout in seconds

        Returns:
            DockerComposeResult

        Example:
            >>> docker.compose_up(
            ...     host="pi@192.168.188.108",
            ...     project_dir="~/c2004",
            ...     files=["docker-compose.yml"],
            ...     env_file=".env",
            ...     build=True,
            ...     wait_healthy=True
            ... )
        """
        # Build base command
        cmd_parts = ["docker compose"]

        if files:
            for f in files:
                cmd_parts.append(f"-f {f}")

        if env_file:
            cmd_parts.append(f"--env-file {env_file}")

        cmd_parts.append("up -d")

        if build:
            cmd_parts.append("--build")

        full_cmd = " ".join(cmd_parts)

        # Execute via SSH or locally
        if host:
            ssh_cmd = f"cd {project_dir} && {full_cmd}"
            return self._run_ssh(host, ssh_cmd, timeout)
        else:
            return self._run_local(full_cmd, cwd=project_dir, timeout=timeout)

    def compose_down(
        self,
        host: Optional[str] = None,
        project_dir: str = "~/c2004",
        files: Optional[List[str]] = None,
        timeout: int = 60,
    ) -> DockerComposeResult:
        """Run docker compose down."""
        cmd_parts = ["docker compose"]

        if files:
            for f in files:
                cmd_parts.append(f"-f {f}")

        cmd_parts.append("down")
        full_cmd = " ".join(cmd_parts)

        if host:
            ssh_cmd = f"cd {project_dir} && {full_cmd}"
            return self._run_ssh(host, ssh_cmd, timeout)
        else:
            return self._run_local(full_cmd, cwd=project_dir, timeout=timeout)

    def wait_healthy(
        self,
        host: Optional[str] = None,
        project: str = "c2004",
        timeout: int = 120,
        interval: int = 5,
    ) -> bool:
        """Wait for all services to be healthy.

        Args:
            host: SSH host
            project: Project name
            timeout: Maximum wait time
            interval: Check interval

        Returns:
            True when all healthy
        """
        start = time.time()
        attempts = 0

        while time.time() - start < timeout:
            attempts += 1
            cmd = f"docker compose ps --format json 2>/dev/null || docker compose ps"

            if host:
                result = self._run_ssh(host, f"cd ~/{project} && {cmd}", timeout=30)
            else:
                result = self._run_local(cmd, cwd=f"~/{project}", timeout=30)

            # Check if all services are running/healthy
            if result.success and ("healthy" in result.stdout.lower() or "running" in result.stdout.lower()):
                # Simple check - could be more sophisticated with JSON parsing
                unhealthy = result.stdout.count("unhealthy") + result.stdout.count("exited")
                if unhealthy == 0:
                    print(f"    All services healthy after {int(time.time() - start)}s")
                    return True

            time.sleep(interval)
            print(f"    Attempt {attempts}: Waiting for healthy services...")

        raise TimeoutError("docker.wait_healthy", timeout)

    def logs(
        self,
        host: Optional[str] = None,
        project_dir: str = "~/c2004",
        services: Optional[List[str]] = None,
        tail: int = 50,
    ) -> str:
        """Get container logs."""
        cmd = f"docker compose logs --tail={tail}"
        if services:
            cmd += " " + " ".join(services)

        if host:
            return self._run_ssh(host, f"cd {project_dir} && {cmd}", timeout=30).stdout
        else:
            return self._run_local(cmd, cwd=project_dir, timeout=30).stdout

    def _run_ssh(self, host: str, command: str, timeout: int) -> DockerComposeResult:
        """Run command via SSH."""
        import subprocess

        ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", host, command]

        try:
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return DockerComposeResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError("docker", timeout)

    def _run_local(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 60
    ) -> DockerComposeResult:
        """Run command locally."""
        import subprocess

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd
            )
            return DockerComposeResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError("docker", timeout)


# Singleton instance for easy import
docker = DockerDSL()

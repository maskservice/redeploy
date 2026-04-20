"""Imperative step actions for Python-native DSL."""
import subprocess
import time
import urllib.request
import urllib.error
from typing import List, Optional, Union
from pathlib import Path
from .exceptions import StepError, TimeoutError, VerificationError, ConnectionError


def ssh(host: str, command: str, timeout: int = 60, check: bool = True) -> str:
    """Execute a command on a remote host via SSH.

    Args:
        host: SSH host (e.g., "pi@192.168.188.108")
        command: Command to execute
        timeout: Timeout in seconds
        check: Raise error on non-zero exit

    Returns:
        Command output (stdout)

    Raises:
        StepError: If command fails
        TimeoutError: If command times out

    Example:
        >>> ssh("pi@192.168.188.108", "sudo shutdown -r now")
        'rpi5-restart-scheduled'
    """
    cmd = ["ssh", "-o", "StrictHostKeyChecking=no", host, command]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if check and result.returncode != 0:
            raise StepError(
                step_name="ssh",
                message=f"SSH command failed: {result.stderr}",
                output=result.stdout
            )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        raise TimeoutError("ssh", timeout)


def ssh_available(host: str, timeout: int = 60, interval: int = 5) -> bool:
    """Wait for SSH to become available on a host.

    Args:
        host: SSH host to check
        timeout: Maximum time to wait
        interval: Seconds between checks

    Returns:
        True if SSH becomes available

    Raises:
        TimeoutError: If SSH doesn't become available in time

    Example:
        >>> ssh_available("pi@192.168.188.108", timeout=120)
        True
    """
    start = time.time()
    attempts = 0

    while time.time() - start < timeout:
        attempts += 1
        try:
            # Try to connect via SSH with a simple command
            result = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=5", host, "echo ready"],
                capture_output=True,
                timeout=10
            )
            if result.returncode == 0 and "ready" in result.stdout:
                print(f"    SSH available after {int(time.time() - start)}s ({attempts} attempts)")
                return True
        except subprocess.TimeoutExpired:
            pass

        time.sleep(interval)
        print(f"    Attempt {attempts}: SSH not ready, waiting...")

    raise TimeoutError("ssh_available", timeout)


def rsync(
    src: str,
    dst: str,
    exclude: Optional[List[str]] = None,
    delete: bool = False,
    timeout: int = 300,
) -> str:
    """Synchronize files using rsync.

    Args:
        src: Source path (local or remote)
        dst: Destination path (local or remote)
        exclude: List of patterns to exclude
        delete: Delete extraneous files from dest
        timeout: Timeout in seconds

    Returns:
        rsync output

    Example:
        >>> rsync(
        ...     src="/home/tom/c2004/",
        ...     dst="pi@192.168.188.108:~/c2004",
        ...     exclude=[".git", ".venv", "__pycache__"]
        ... )
    """
    cmd = ["rsync", "-avz", "--progress"]

    if delete:
        cmd.append("--delete")

    if exclude:
        for pattern in exclude:
            cmd.extend(["--exclude", pattern])

    cmd.extend([src, dst])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if result.returncode != 0:
            raise StepError(
                step_name="rsync",
                message=f"rsync failed: {result.stderr}",
                output=result.stdout
            )
        return result.stdout
    except subprocess.TimeoutExpired:
        raise TimeoutError("rsync", timeout)


def scp(src: str, dst: str, timeout: int = 60) -> str:
    """Copy files using SCP.

    Args:
        src: Source file
        dst: Destination
        timeout: Timeout in seconds

    Returns:
        SCP output
    """
    cmd = ["scp", "-o", "StrictHostKeyChecking=no", src, dst]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if result.returncode != 0:
            raise StepError(
                step_name="scp",
                message=f"scp failed: {result.stderr}",
                output=result.stdout
            )
        return result.stdout
    except subprocess.TimeoutExpired:
        raise TimeoutError("scp", timeout)


def wait(seconds: int, message: Optional[str] = None) -> None:
    """Wait for specified seconds.

    Args:
        seconds: Time to wait
        message: Optional message to display

    Example:
        >>> wait(90, "Waiting for RPi5 to restart...")
    """
    if message:
        print(f"    {message}")
    time.sleep(seconds)


def http_expect(
    url: str,
    expect: str,
    timeout: int = 30,
    retries: int = 3,
    method: str = "GET"
) -> bool:
    """Verify HTTP endpoint returns expected content.

    Args:
        url: URL to check
        expect: Expected string in response
        timeout: Request timeout
        retries: Number of retries
        method: HTTP method

    Returns:
        True if expectation met

    Raises:
        VerificationError: If expectation not met

    Example:
        >>> http_expect(
        ...     "http://192.168.188.108:8101/api/v3/health",
        ...     "healthy"
        ... )
        True
    """
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                content = response.read().decode('utf-8')
                if expect in content:
                    return True
                raise VerificationError(
                    check_type="http_expect",
                    expected=expect,
                    actual=content[:200]
                )
        except urllib.error.URLError as e:
            if attempt < retries - 1:
                time.sleep(2)
                continue
            raise VerificationError(
                check_type="http_expect",
                expected=expect,
                actual=f"URL error: {e}"
            )

    return False


def version_check(
    manifest_path: Optional[str] = None,
    expect: str = "@manifest",
    host: Optional[str] = None,
    url: Optional[str] = None,
) -> bool:
    """Verify deployed version matches expectation.

    Args:
        manifest_path: Path to version manifest
        expect: Expected version (or "@manifest" to read from manifest)
        host: SSH host to check (runs `cat VERSION`)
        url: HTTP endpoint returning version

    Returns:
        True if version matches

    Raises:
        VerificationError: If version mismatch
    """
    if expect == "@manifest":
        from ..version import VersionManifest
        m = VersionManifest.load(Path(manifest_path or ".redeploy/version.yaml"))
        expected_version = m.version
    else:
        expected_version = expect

    if host:
        actual = ssh(host, "cat VERSION 2>/dev/null || echo 'unknown'")
    elif url:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            actual = response.read().decode('utf-8').strip()
    else:
        raise StepError(
            step_name="version_check",
            message="Must specify host or url for version check",
            output=""
        )

    if expected_version not in actual and actual not in expected_version:
        raise VerificationError(
            check_type="version_check",
            expected=expected_version,
            actual=actual
        )

    return True

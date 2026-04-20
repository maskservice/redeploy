"""SSH remote execution — unified helper used by redeploy, deploy, fleet.

Replaces both:
  - deploy/core/remote.py  (RemoteExecutor — device-aware, rich SSH options)
  - redeploy/detect/remote.py  (RemoteProbe — simple string-host)

Both are kept for backwards compatibility as thin wrappers around SshClient.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from loguru import logger


# ── Result ────────────────────────────────────────────────────────────────────

@dataclass
class SshResult:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    # deploy compat aliases
    @property
    def success(self) -> bool:
        return self.ok

    @property
    def out(self) -> str:
        return self.stdout.strip()


# ── Core client ───────────────────────────────────────────────────────────────

class SshClient:
    """Execute commands on a remote host via SSH (or locally).

    Args:
        host:     ``user@ip`` string, or ``"local"`` / ``"localhost"``
        port:     SSH port (default 22)
        key:      path to private key; auto-detected if None
        ssh_id:   label for log messages (device id, hostname, …)
    """

    def __init__(
        self,
        host: str,
        port: int = 22,
        key: Optional[str] = None,
        ssh_id: str = "",
    ):
        self.host = host
        self.port = port
        self._key_explicit = key          # None = auto-detect lazily
        self.ssh_id = ssh_id or host

        self.is_local = host in ("local", "localhost", "127.0.0.1")

    @property
    def key(self) -> Optional[str]:
        """Resolved SSH key path (auto-detected if not set explicitly)."""
        return self._key_explicit or self._detect_ssh_key()

    @key.setter
    def key(self, v: Optional[str]) -> None:
        self._key_explicit = v

    # ── public API ────────────────────────────────────────────────────────────

    def run(self, cmd: str, timeout: int = 60) -> SshResult:
        """Execute *cmd* on the remote host (or locally)."""
        if self.is_local:
            return self._run_local(cmd, timeout)
        full_cmd = ["ssh"] + self._ssh_opts() + [self.host, cmd]
        logger.debug(f"[{self.ssh_id}] SSH: {cmd[:120]}")
        try:
            p = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
            if p.returncode != 0:
                logger.debug(f"[{self.ssh_id}] exit={p.returncode}: {p.stderr[:200]}")
            return SshResult(p.returncode, p.stdout, p.stderr)
        except subprocess.TimeoutExpired:
            return SshResult(124, "", "Command timed out")
        except Exception as e:
            return SshResult(1, "", str(e))

    def rsync(
        self,
        local_path: str,
        remote_path: str,
        exclude: Optional[list[str]] = None,
        delete: bool = False,
        timeout: int = 300,
    ) -> SshResult:
        """rsync *local_path* to ``host:remote_path``."""
        if self.is_local:
            dst = remote_path
            cmd = ["rsync", "-az", "--progress"]
        else:
            dst = f"{self.host}:{remote_path}"
            cmd = ["rsync", "-az", "--progress",
                   "-e", f"ssh {' '.join(self._ssh_opts())}"]
        if delete:
            cmd.append("--delete")
        for ex in (exclude or []):
            cmd.extend(["--exclude", ex])
        cmd.extend([local_path, dst])
        logger.info(f"[{self.ssh_id}] rsync {local_path} → {remote_path}")
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return SshResult(p.returncode, p.stdout, p.stderr)
        except subprocess.TimeoutExpired:
            return SshResult(124, "", f"rsync timed out after {timeout}s")
        except Exception as e:
            return SshResult(1, "", str(e))

    def scp(self, local_path: str, remote_path: str, timeout: int = 120) -> SshResult:
        """Copy single file to remote host."""
        if self.is_local:
            cmd = ["cp", local_path, remote_path]
        else:
            opts = self._scp_opts()
            cmd = ["scp"] + opts + [local_path, f"{self.host}:{remote_path}"]
        logger.info(f"[{self.ssh_id}] scp {local_path} → {remote_path}")
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if p.returncode != 0:
                logger.warning(f"[{self.ssh_id}] scp failed: {p.stderr[:200]}")
            return SshResult(p.returncode, p.stdout, p.stderr)
        except Exception as e:
            return SshResult(1, "", str(e))

    def is_reachable(self, timeout: int = 10) -> bool:
        """Return True if SSH connection succeeds."""
        if self.is_local:
            return True
        r = self.run("echo ok", timeout=timeout)
        return r.ok and "ok" in r.out

    def is_ssh_ready(self) -> bool:
        """Check if SSH is available (backwards compat alias for deploy/)."""
        result = self.run("echo ok", timeout=10)
        return result.success and "ok" in result.stdout

    def ping(self) -> bool:
        """ICMP ping, fallback to SSH echo."""
        ip = self.host.split("@")[-1] if "@" in self.host else self.host
        try:
            p = subprocess.run(
                ["ping", "-c", "1", "-W", "3", ip],
                capture_output=True, timeout=5,
            )
            if p.returncode == 0:
                return True
        except Exception:
            pass
        return self.is_reachable()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _run_local(self, cmd: str, timeout: int) -> SshResult:
        try:
            p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return SshResult(p.returncode, p.stdout, p.stderr)
        except subprocess.TimeoutExpired:
            return SshResult(124, "", "Command timed out")
        except Exception as e:
            return SshResult(1, "", str(e))

    def _ssh_opts(self) -> list[str]:
        opts = [
            "-o", "ConnectTimeout=10",
            "-o", "StrictHostKeyChecking=no",
            "-o", "BatchMode=yes",
            "-p", str(self.port),
        ]
        if self.key:
            opts.extend(["-i", self.key])
        return opts

    def _scp_opts(self) -> list[str]:
        opts = [
            "-o", "ConnectTimeout=10",
            "-o", "StrictHostKeyChecking=no",
            "-o", "BatchMode=yes",
            "-P", str(self.port),
        ]
        if self.key:
            opts.extend(["-i", self.key])
        return opts

    @staticmethod
    def _detect_ssh_key() -> Optional[str]:
        """Alias for backwards compatibility with deploy/ tests."""
        return SshClient._detect_key()

    @staticmethod
    def _detect_key() -> Optional[str]:
        import os
        env_key = os.environ.get("SSH_KEY_PATH")
        if env_key and Path(env_key).is_file():
            return env_key
        home = Path.home()
        candidates = [
            home / ".ssh/id_ed25519",
            home / ".ssh/id_rsa",
            Path("/root/.ssh/id_ed25519"),
            Path("/root/.ssh/id_rsa"),
        ]
        for c in candidates:
            try:
                if c.is_file():
                    return str(c)
            except PermissionError:
                continue
        return None


# ── Backwards-compat wrappers ─────────────────────────────────────────────────

class RemoteProbe(SshClient):
    """Thin wrapper kept for redeploy.detect compatibility.

    ``RemoteProbe(host)``  →  ``SshClient(host)``
    """

    def __init__(self, host: str):
        super().__init__(host=host, ssh_id=host)

    @property
    def is_local(self) -> bool:  # type: ignore[override]
        return self.host in ("local", "localhost", "127.0.0.1")

    @is_local.setter
    def is_local(self, v: bool) -> None:
        pass  # controlled by host value only


class RemoteExecutor(SshClient):
    """Thin wrapper kept for deploy.core compatibility.

    ``RemoteExecutor(device)``  →  ``SshClient(host, port, key, id)``
    """

    def __init__(self, device):  # device: DeviceConfig (no circular import)
        super().__init__(
            host=device.ssh_host,
            port=device.ssh_port,
            key=device.ssh_key,    # None → lazy auto-detect via _detect_ssh_key
            ssh_id=device.id,
        )
        self.device = device

    @property
    def ssh_target(self) -> str:
        return self.device.ssh_host

    @property
    def ssh_opts(self) -> list[str]:
        return self._ssh_opts()

    @property
    def scp_opts(self) -> list[str]:
        return self._scp_opts()

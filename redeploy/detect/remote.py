"""SSH remote executor for detect probes."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class RunResult:
    stdout: str
    stderr: str
    returncode: int

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def out(self) -> str:
        return self.stdout.strip()


class RemoteProbe:
    """Execute shell commands over SSH (or locally)."""

    def __init__(self, host: str):
        self.host = host
        self.is_local = (host == "local" or host == "localhost")

    def run(self, cmd: str, timeout: int = 30) -> RunResult:
        if self.is_local:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=timeout
            )
        else:
            result = subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no",
                 "-o", "ConnectTimeout=10",
                 "-o", "BatchMode=yes",
                 self.host, cmd],
                capture_output=True, text=True, timeout=timeout,
            )
        return RunResult(
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
        )

    def is_reachable(self) -> bool:
        if self.is_local:
            return True
        r = self.run("echo ok", timeout=10)
        return r.ok and "ok" in r.out

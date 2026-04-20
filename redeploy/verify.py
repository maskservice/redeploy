"""Declarative verification helpers — moved from deploy/strategies/_verify.py.

Provides a VerifyContext that both deploy strategies and redeploy apply steps use.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from loguru import logger


@dataclass
class VerifyContext:
    """Accumulates check results during verification."""
    device_id: str
    checks: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def check(self, remote, name: str, cmd: str,
              expect: str = "", critical: bool = True) -> bool:
        """Run a single remote check command and record the result.

        *remote* is any object with ``.run(cmd) -> result`` (SshClient family).
        """
        r = remote.run(cmd, timeout=15)
        val = r.stdout.strip() if r.success else ""
        ok = (expect in val) if expect else r.success
        status = "PASS" if ok else "FAIL"
        self.checks.append(f"  [{status}] {name}")
        if not ok and critical:
            detail = val[:100] or (r.stderr[:100] if r else "no response")
            self.errors.append(f"{name}: {detail}")
        logger.debug(f"[{self.device_id}] verify {name}: {status}")
        return ok

    def add_pass(self, name: str) -> None:
        self.checks.append(f"  [PASS] {name}")

    def add_fail(self, name: str, detail: str = "") -> None:
        self.checks.append(f"  [FAIL] {name}")
        if detail:
            self.errors.append(f"{name}: {detail}")

    def add_warn(self, msg: str) -> None:
        self.checks.append(f"  [WARN] {msg}")

    def add_info(self, msg: str) -> None:
        self.checks.append(f"  [INFO] {msg}")

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if "[PASS]" in c)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if "[FAIL]" in c)

    @property
    def warned(self) -> int:
        return sum(1 for c in self.checks if "[WARN]" in c)

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.warned

    @property
    def ok(self) -> bool:
        return self.failed == 0

    def summary(self) -> str:
        msg = f"Verify: {self.passed}/{self.total} passed"
        if self.failed:
            msg += f", {self.failed} FAILED"
        if self.warned:
            msg += f", {self.warned} warnings"
        if not self.ok:
            msg += f" — errors: {'; '.join(self.errors[:3])}"
        return msg


def verify_data_integrity(ctx: VerifyContext, local_counts: dict, remote_counts: dict) -> None:
    """Compare local vs remote SQLite row counts and record results in *ctx*."""
    for table, local_n in local_counts.items():
        if isinstance(local_n, dict):
            local_n = local_n.get("local", 0)
        remote_n = remote_counts.get(table, 0)
        if remote_n == 0:
            ctx.add_fail(f"data {table}", f"remote is empty, local has {local_n}")
        elif local_n != remote_n:
            ctx.add_fail(f"data {table}", f"local={local_n} != remote={remote_n}")
        else:
            ctx.add_pass(f"data {table}: {local_n} == {remote_n}")

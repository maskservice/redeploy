"""SSH remote executor for detect probes — thin re-export from redeploy.ssh."""
from redeploy.ssh import RemoteProbe, SshResult as RunResult  # noqa: F401

__all__ = ["RemoteProbe", "RunResult"]

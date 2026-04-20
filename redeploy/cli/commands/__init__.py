"""CLI commands package."""
# Commands are registered in cli/__init__.py

from . import audit
from . import detect
from . import devices
from . import diagnose
from . import diff
from . import exec_
from . import export
from . import import_
from . import init
from . import inspect
from . import patterns
from . import plan_apply
from . import plugin
from . import probe
from . import state
from . import status
from . import target
from . import version
from . import workflow

__all__ = [
    "audit",
    "detect",
    "devices",
    "diagnose",
    "diff",
    "exec_",
    "export",
    "import_",
    "init",
    "inspect",
    "patterns",
    "plan_apply",
    "plugin",
    "probe",
    "state",
    "status",
    "target",
    "version",
    "workflow",
]

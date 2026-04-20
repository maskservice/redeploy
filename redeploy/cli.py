"""redeploy CLI — detect | plan | apply | migrate.

This module is a backward-compatible wrapper around the refactored cli package.
All functionality has been moved to redeploy/cli/ for better maintainability.
"""
from __future__ import annotations

# Re-export everything from the new cli package for backward compatibility
from .cli import cli, _setup_logging, _resolve_device
from .cli.core import (
    load_spec_or_exit,
    find_manifest_path,
    resolve_device,
    load_spec_with_manifest,
    overlay_device_onto_spec,
    run_detect_for_spec,
    run_detect_workflow,
)
from .cli.display import (
    print_plan_table,
    print_infrastructure_summary,
    print_docker_services,
    print_k3s_pods,
    print_conflicts,
    print_inspect_app_metadata,
    print_inspect_environments,
    print_inspect_templates,
    print_inspect_workflows,
    print_inspect_devices,
    print_inspect_raw_nodes_summary,
    print_workflow_summary_table,
    print_workflow_host_details,
    generate_workflow_output_css,
    generate_workflow_output_yaml,
    print_import_spec,
)
from .cli.commands.detect import detect
from .cli.commands.diagnose import diagnose
from .cli.commands.inspect import inspect
from .cli.commands.workflow import workflow_cmd
from .cli.commands.export import export_cmd
from .cli.commands.plugin import plugin_cmd
from .cli.commands.exec_ import exec_cmd, exec_multi_cmd
from .cli.commands.plan_apply import plan, apply, migrate, run
from .cli.commands.state import state_cmd
from .cli.commands.init import init
from .cli.commands.status import status
from .cli.commands.devices import devices, scan, device_add, device_rm
from .cli.commands.target import target
from .cli.commands.probe import probe
from .cli.commands.import_ import import_cmd
from .cli.commands.diff import diff
from .cli.commands.audit import audit
from .cli.commands.patterns import patterns
from .cli.commands.version import version_cmd

__all__ = ["cli", "_resolve_device"]


# Backward compatibility: re-export old function names
from .cli.display import print_infrastructure_summary as _print_infrastructure_summary
from .cli.display import print_docker_services as _print_docker_services
from .cli.display import print_k3s_pods as _print_k3s_pods
from .cli.display import print_conflicts as _print_conflicts
from .cli.display import print_plan_table as _print_plan_table

# Backward compatibility: more display functions
from .cli.display import (
    print_inspect_app_metadata as _print_inspect_app_metadata,
    print_inspect_environments as _print_inspect_environments,
    print_inspect_templates as _print_inspect_templates,
    print_inspect_workflows as _print_inspect_workflows,
    print_inspect_devices as _print_inspect_devices,
    print_inspect_raw_nodes_summary as _print_inspect_raw_nodes_summary,
    print_workflow_summary_table as _print_workflow_summary_table,
    print_workflow_host_details as _print_workflow_host_details,
    generate_workflow_output_css as _generate_workflow_output_css,
    generate_workflow_output_yaml as _generate_workflow_output_yaml,
    print_import_spec as _print_import_spec,
)
from .cli.core import (
    run_detect_workflow as _run_detect_workflow,
    load_spec_or_exit as _load_spec_or_exit,
    resolve_device as _resolve_device,
    load_spec_with_manifest as _load_spec_with_manifest,
    overlay_device_onto_spec as _overlay_device_onto_spec,
    run_detect_for_spec as _run_detect_for_spec,
    find_manifest_path as _find_manifest_path,
)
# End of backward compatibility exports

# All CLI functionality moved to redeploy/cli/ package
# This file maintained for backward compatibility

"""Blueprint subsystem — extract, generate and apply DeviceBlueprints.

Public API::

    from redeploy.blueprint import extract_blueprint, generate_twin, generate_migration
"""
from .extractor import extract_blueprint
from .generators.docker_compose import generate_twin
from .generators.migration import generate_migration

__all__ = ["extract_blueprint", "generate_twin", "generate_migration"]

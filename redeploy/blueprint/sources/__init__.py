"""Blueprint source adapters — extract partial blueprints from multiple inputs.

Each module in this package exposes a narrow, single-responsibility function
that reads one kind of source (live infra, docker-compose, migration.yaml,
DeviceMap hardware, …) and returns structured data for the orchestrator in
:mod:`redeploy.blueprint.extractor` to merge into a ``DeviceBlueprint``.
"""
from __future__ import annotations

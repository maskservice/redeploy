"""Shared JMESPath query runner for CLI commands.

All ``--query`` flags across ``hardware``, ``device-map``, and ``blueprint``
dispatch through :func:`execute_query` so that error handling, formatting,
and output are consistent.
"""
from __future__ import annotations

import json as _json
import sys
from typing import Any

import click
import jmespath
import yaml


def execute_query(obj: Any, query_expr: str, output_fmt: str, echo: click.utils.LazyFile | None = None) -> None:
    """Run a JMESPath *query_expr* against *obj* and echo the result.

    *obj* must have a ``model_dump(mode="json")`` method (Pydantic model).
    *echo* defaults to ``click.echo``; override for ``rich.console.Console``
    via ``console.print``.
    """
    _echo = click.echo if echo is None else echo

    data = obj.model_dump(mode="json")

    try:
        result = jmespath.search(query_expr, data)
    except jmespath.exceptions.JMESPathError as exc:
        _echo(f"[red]✗ JMESPath error:[/red] {exc}")
        sys.exit(1)

    if result is None:
        _echo("[dim]No match found for query[/dim]")
        return

    if output_fmt == "json":
        _echo(_json.dumps(result, indent=2, default=str))
    else:
        _echo(yaml.safe_dump(result, sort_keys=False, default_flow_style=False))

"""Tests for redeploy.cli.query — shared JMESPath query runner."""
from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock

import jmespath
import pytest
import yaml

from redeploy.cli.query import execute_query


class _FakeModel:
    """Minimal stand-in for a Pydantic model."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def model_dump(self, **_: Any) -> dict[str, Any]:
        return self._data


# ── execute_query ─────────────────────────────────────────────────────────────


class TestExecuteQuery:
    def test_basic_dict_result(self, capsys):
        obj = _FakeModel({"name": "pi5", "cpus": 4})
        execute_query(obj, "name", "json")
        captured = capsys.readouterr()
        assert "pi5" in captured.out

    def test_json_format(self, capsys):
        obj = _FakeModel({"a": 1, "b": [2, 3]})
        execute_query(obj, "b", "json")
        captured = capsys.readouterr()
        assert captured.out.strip() == "[\n  2,\n  3\n]"

    def test_yaml_format(self, capsys):
        obj = _FakeModel({"a": 1, "b": [2, 3]})
        execute_query(obj, "b", "yaml")
        captured = capsys.readouterr()
        parsed = yaml.safe_load(captured.out)
        assert parsed == [2, 3]

    def test_no_match_message(self, capsys):
        obj = _FakeModel({"a": 1})
        execute_query(obj, "missing", "json")
        captured = capsys.readouterr()
        assert "No match found" in captured.out

    def test_jmespath_expression(self, capsys):
        obj = _FakeModel({"items": [{"name": "x"}, {"name": "y"}]})
        execute_query(obj, "items[*].name", "json")
        captured = capsys.readouterr()
        assert "x" in captured.out
        assert "y" in captured.out

    def test_jmespath_error_exits(self, capsys):
        obj = _FakeModel({"a": 1})
        with pytest.raises(SystemExit) as exc_info:
            execute_query(obj, "invalid[", "json")
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "JMESPath error" in captured.out

    def test_custom_echo(self):
        echoed: list[str] = []
        execute_query(_FakeModel({"a": 1}), "a", "json", echo=echoed.append)
        assert len(echoed) == 1
        assert "1" in echoed[0]

    def test_json_with_non_serializable_default(self, capsys):
        obj = _FakeModel({"value": object()})  # not JSON-serialisable
        execute_query(obj, "value", "json")
        captured = capsys.readouterr()
        assert "<object" in captured.out or "object" in captured.out

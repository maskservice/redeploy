from __future__ import annotations

from pathlib import Path

from redeploy.iac.base import ParserRegistry
from redeploy.iac.registry import _load_local_parsers


def test_load_local_parsers_from_project_dir(tmp_path: Path, monkeypatch):
    parser_dir = tmp_path / "redeploy_iac_parsers"
    parser_dir.mkdir(parents=True)
    plugin = parser_dir / "demo_parser.py"
    plugin.write_text(
        """
from pathlib import Path
from redeploy.iac.base import ParsedSpec

class DemoParser:
    name = "demo"
    format_label = "Demo"
    extensions = [".demo"]
    path_patterns = ["*.demo"]

    def can_parse(self, path: Path) -> bool:
        return path.suffix == ".demo"

    def parse(self, path: Path) -> ParsedSpec:
        return ParsedSpec(source_file=path, source_format=self.name, confidence=1.0)

PARSERS = [DemoParser]
""".strip()
    )

    monkeypatch.chdir(tmp_path)
    registry = ParserRegistry()
    loaded = _load_local_parsers(registry)
    assert loaded >= 1
    assert "demo" in registry.registered

    demo_file = tmp_path / "x.demo"
    demo_file.write_text("ok")
    parsed = registry.parse(demo_file)
    assert parsed.source_format == "demo"


def test_load_local_parsers_from_user_dir(tmp_path: Path, monkeypatch):
    fake_home = tmp_path / "home"
    user_plugin_dir = fake_home / ".redeploy" / "iac_parsers"
    user_plugin_dir.mkdir(parents=True)
    plugin = user_plugin_dir / "user_parser.py"
    plugin.write_text(
        """
from pathlib import Path
from redeploy.iac.base import ParsedSpec

class UserParser:
    name = "user_parser"
    format_label = "User Parser"
    extensions = [".user"]
    path_patterns = ["*.user"]

    def can_parse(self, path: Path) -> bool:
        return path.suffix == ".user"

    def parse(self, path: Path) -> ParsedSpec:
        return ParsedSpec(source_file=path, source_format=self.name, confidence=1.0)

def get_parsers():
    return [UserParser]
""".strip()
    )

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.chdir(tmp_path)

    registry = ParserRegistry()
    loaded = _load_local_parsers(registry)
    assert loaded >= 1
    assert "user_parser" in registry.registered

from __future__ import annotations

import textwrap

import pytest

from redeploy.spec_loader import UnsupportedSpecFormatError, load_migration_spec


def _migration_yaml() -> str:
    return textwrap.dedent("""\
        name: loader test
        source:
          strategy: docker_full
          host: local
          app: myapp
          version: "1.0.0"
        target:
          strategy: docker_full
          host: local
          app: myapp
          version: "1.0.1"
          remote_dir: ~/myapp
    """)


def test_load_migration_spec_reads_yaml(tmp_path):
    spec_path = tmp_path / "migration.yaml"
    spec_path.write_text(_migration_yaml(), encoding="utf-8")

    spec = load_migration_spec(spec_path)

    assert spec.name == "loader test"
    assert spec.target.version == "1.0.1"


def test_load_migration_spec_rejects_markdown_for_now(tmp_path):
    spec_path = tmp_path / "migration.md"
    spec_path.write_text("# prototype\n", encoding="utf-8")

    with pytest.raises(UnsupportedSpecFormatError) as exc_info:
        load_migration_spec(spec_path)

    assert "markdown/markpact specs are not implemented yet" in str(exc_info.value)

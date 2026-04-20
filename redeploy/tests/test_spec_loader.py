from __future__ import annotations

import textwrap

import pytest

from redeploy.spec_loader import SpecLoaderError, load_migration_spec


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


def _migration_markdown() -> str:
    return textwrap.dedent(
        """\
# Markdown migration

```yaml markpact:config
name: loader markdown test
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
```

```yaml markpact:steps
extra_steps:
  - id: wait_startup
    seconds: 5
```
"""
    )


def test_load_migration_spec_reads_yaml(tmp_path):
    spec_path = tmp_path / "migration.yaml"
    spec_path.write_text(_migration_yaml(), encoding="utf-8")

    spec = load_migration_spec(spec_path)

    assert spec.name == "loader test"
    assert spec.target.version == "1.0.1"


def test_load_migration_spec_reads_supported_markdown(tmp_path):
    spec_path = tmp_path / "migration.md"
    spec_path.write_text(_migration_markdown(), encoding="utf-8")

    spec = load_migration_spec(spec_path)

    assert spec.name == "loader markdown test"
    assert spec.extra_steps[0]["id"] == "wait_startup"


def test_load_migration_spec_rejects_unsupported_markdown_block(tmp_path):
    spec_path = tmp_path / "migration.md"
    spec_path.write_text(
        textwrap.dedent("""\
            # Markdown migration

            ```yaml markpact:config
            name: broken markdown test
            source:
              strategy: docker_full
              host: local
              app: myapp
            target:
              strategy: docker_full
              host: local
              app: myapp
              remote_dir: ~/myapp
            ```

            ```python markpact:python
            print("unsupported")
            ```
        """),
        encoding="utf-8",
    )

    with pytest.raises(SpecLoaderError) as exc_info:
        load_migration_spec(spec_path)

    assert "unsupported block kind 'markpact:python'" in str(exc_info.value)

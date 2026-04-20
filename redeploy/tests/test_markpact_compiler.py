from __future__ import annotations

import textwrap

import pytest

from redeploy.markpact import MarkpactCompileError, compile_markpact_document, parse_markpact_text


def test_compile_markpact_document_yaml_subset_to_spec():
    document = parse_markpact_text(
        textwrap.dedent("""\
            # Demo

            ```markpact:config yaml
            name: compiler test
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

            ```markpact:steps yaml
            extra_steps:
              - id: sync_env
                src: .env
                dst: ~/myapp/.env
            ```
        """),
        path="demo.md",
    )

    spec = compile_markpact_document(document)

    assert spec.name == "compiler test"
    assert spec.target.version == "1.0.1"
    assert spec.extra_steps[0]["id"] == "sync_env"


def test_compile_markpact_document_supports_toml_config_and_steps():
    document = parse_markpact_text(
        textwrap.dedent("""\
            # Demo

            ```toml markpact:config
            name = "toml compiler test"
            [source]
            strategy = "docker_full"
            host = "local"
            app = "myapp"
            version = "1.0.0"
            [target]
            strategy = "docker_full"
            host = "local"
            app = "myapp"
            version = "1.0.1"
            remote_dir = "~/myapp"
            ```

            ```markpact:steps toml
            [[extra_steps]]
            id = "wait_startup"
            seconds = 5
            ```
        """),
        path="demo.md",
    )

    spec = compile_markpact_document(document)

    assert spec.name == "toml compiler test"
    assert spec.extra_steps[0]["id"] == "wait_startup"
    assert spec.extra_steps[0]["seconds"] == 5


def test_compile_markpact_document_rejects_unsupported_block_kind():
    document = parse_markpact_text(
        textwrap.dedent("""\
            # Demo

            ```markpact:config yaml
            name: compiler test
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

            ```markpact:python
            print("unsupported")
            ```
        """),
        path="demo.md",
    )

    with pytest.raises(MarkpactCompileError) as exc_info:
        compile_markpact_document(document)

    assert "unsupported block kind 'markpact:python'" in str(exc_info.value)


def test_compile_markpact_document_rejects_unsupported_step_keys():
    document = parse_markpact_text(
        textwrap.dedent("""\
            # Demo

            ```markpact:config yaml
            name: compiler test
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

            ```markpact:steps yaml
            extra_steps:
              - id: install_docker
                action: ssh_cmd
                command: echo ok
                when: docker_not_running
            ```
        """),
        path="demo.md",
    )

    with pytest.raises(MarkpactCompileError) as exc_info:
        compile_markpact_document(document)

    assert "unsupported step keys" in str(exc_info.value)
    assert "when" in str(exc_info.value)

"""Tests for redeploy.dsl — RedeployDSLParser, DSLNode, load_css_text, loaders."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from redeploy.dsl import RedeployDSLParser, DSLNode
from redeploy.dsl.loader import (
    load_css_text,
    manifest_to_css,
    templates_to_css,
    WorkflowDef,
)


# ── helpers ───────────────────────────────────────────────────────────────────


def parse(text: str) -> list[DSLNode]:
    return RedeployDSLParser().parse(textwrap.dedent(text))


# ── DSLNode ────────────────────────────────────────────────────────────────────


class TestDSLNode:
    def test_name_from_name_attr(self):
        n = DSLNode(selector_type="environment", attrs={"name": "prod"})
        assert n.name == "prod"

    def test_name_from_id_attr(self):
        n = DSLNode(selector_type="template", attrs={"id": "rpi-kiosk"})
        assert n.name == "rpi-kiosk"

    def test_get_default(self):
        n = DSLNode(selector_type="app", props={"key": "val"})
        assert n.get("missing", "default") == "default"

    def test_get_existing(self):
        n = DSLNode(selector_type="app", props={"host": "root@10.0.0.1"})
        assert n.get("host") == "root@10.0.0.1"

    def test_repr(self):
        n = DSLNode(selector_type="environment", attrs={"name": "prod"})
        r = repr(n)
        assert "environment" in r
        assert "prod" in r


# ── RedeployDSLParser — at-rules ───────────────────────────────────────────────


class TestAtRules:
    def test_app_at_rule(self):
        nodes = parse("@app c2004;")
        assert len(nodes) == 1
        n = nodes[0]
        assert n.selector_type == "@app"
        assert n.props["value"] == "c2004"

    def test_multiple_at_rules(self):
        nodes = parse("""
            @app myapp;
            @version 1.2.3;
            @spec migration.yaml;
        """)
        types = [n.selector_type for n in nodes]
        assert "@app" in types
        assert "@version" in types
        assert "@spec" in types

    def test_at_rules_dict(self):
        parser = RedeployDSLParser()
        parser.parse("@app myapp;\n@version 2.0.0;")
        assert parser.at_rules["app"] == "myapp"
        assert parser.at_rules["version"] == "2.0.0"


# ── RedeployDSLParser — blocks ─────────────────────────────────────────────────


class TestBlocks:
    def test_environment_block(self):
        nodes = parse("""
            environment[name="prod"] {
              host: root@10.0.0.1;
              strategy: docker_full;
            }
        """)
        assert len(nodes) == 1
        n = nodes[0]
        assert n.selector_type == "environment"
        assert n.attrs["name"] == "prod"
        assert n.props["host"] == "root@10.0.0.1"
        assert n.props["strategy"] == "docker_full"

    def test_template_block(self):
        nodes = parse("""
            template[id="rpi-kiosk"] {
              name: Raspberry Pi Kiosk;
              strategy: native_kiosk;
              environment: kiosk;
            }
        """)
        n = nodes[0]
        assert n.selector_type == "template"
        assert n.attrs["id"] == "rpi-kiosk"
        assert n.props["strategy"] == "native_kiosk"
        assert n.props["name"] == "Raspberry Pi Kiosk"

    def test_workflow_block(self):
        nodes = parse("""
            workflow[name="deploy:prod"] {
              trigger: manual;
              step-1: redeploy run --env prod --detect;
              step-2: redeploy run --env prod;
            }
        """)
        n = nodes[0]
        assert n.selector_type == "workflow"
        assert n.name == "deploy:prod"
        assert n.props["trigger"] == "manual"
        assert "step-1" in n.props
        assert "step-2" in n.props

    def test_app_block(self):
        nodes = parse("""
            app {
              name: myapp;
              domain: myapp.example.com;
            }
        """)
        n = nodes[0]
        assert n.selector_type == "app"
        assert n.props["name"] == "myapp"

    def test_empty_block(self):
        nodes = parse("environment[name=\"dev\"] {}")
        assert len(nodes) == 1
        assert nodes[0].props == {}

    def test_multiple_blocks(self):
        nodes = parse("""
            environment[name="prod"] {
              host: root@10.0.0.1;
            }
            environment[name="dev"] {
              host: root@192.168.1.10;
            }
        """)
        assert len(nodes) == 2
        names = [n.name for n in nodes]
        assert "prod" in names
        assert "dev" in names


# ── Comments ───────────────────────────────────────────────────────────────────


class TestComments:
    def test_line_comment_before_block_becomes_doc(self):
        nodes = parse("""
            // Production environment
            environment[name="prod"] {
              host: root@10.0.0.1;
            }
        """)
        assert "Production environment" in nodes[0].doc

    def test_block_comment_stripped(self):
        nodes = parse("""
            /* This is a block comment */
            @app myapp;
        """)
        at = [n for n in nodes if n.selector_type == "@app"]
        assert len(at) == 1

    def test_inline_comment_in_body_ignored(self):
        nodes = parse("""
            environment[name="prod"] {
              host: root@10.0.0.1;  // SSH host
              strategy: docker_full;
            }
        """)
        assert nodes[0].props["host"] == "root@10.0.0.1"
        assert "comment" not in nodes[0].props


# ── nodes_of_type ──────────────────────────────────────────────────────────────


def test_nodes_of_type():
    parser = RedeployDSLParser()
    parser.parse("""
        environment[name="prod"] {
          host: root@a;
        }
        environment[name="dev"] {
          host: root@b;
        }
        template[id="rpi"] {
          strategy: native_kiosk;
        }
    """)
    envs = parser.nodes_of_type("environment")
    assert len(envs) == 2
    tmpl = parser.nodes_of_type("template")
    assert len(tmpl) == 1


# ── load_css_text ─────────────────────────────────────────────────────────────


class TestLoadCssText:
    CSS = textwrap.dedent("""
        @app c2004;
        @spec migration.yaml;

        environment[name="prod"] {
          host: root@87.106.87.183;
          strategy: docker_full;
          domain: c2004.example.com;
          verify_url: https://c2004.example.com/health;
        }

        environment[name="dev"] {
          host: local;
          strategy: docker_full;
        }

        template[id="rpi-kiosk"] {
          name: Raspberry Pi Kiosk;
          strategy: native_kiosk;
          environment: kiosk;
          score[is_arm]: 2.0;
          score[chromium]: 2.0;
          note: Requires openbox;
        }

        workflow[name="deploy:prod"] {
          trigger: manual;
          step-1: redeploy run --env prod --detect;
          step-2: redeploy run --env prod;
        }
    """)

    def test_manifest_app(self):
        result = load_css_text(self.CSS)
        assert result.manifest is not None
        assert result.manifest.app == "c2004"

    def test_manifest_environments(self):
        result = load_css_text(self.CSS)
        envs = result.manifest.environments
        assert "prod" in envs
        assert "dev" in envs
        assert envs["prod"].host == "root@87.106.87.183"
        assert envs["prod"].strategy == "docker_full"
        assert envs["prod"].domain == "c2004.example.com"

    def test_templates(self):
        result = load_css_text(self.CSS)
        assert len(result.templates) == 1
        t = result.templates[0]
        assert t.id == "rpi-kiosk"
        assert t.strategy.value == "native_kiosk"
        assert "Requires openbox" in t.notes

    def test_workflows(self):
        result = load_css_text(self.CSS)
        assert len(result.workflows) == 1
        wf = result.workflows[0]
        assert wf.name == "deploy:prod"
        assert wf.trigger == "manual"
        assert len(wf.steps) == 2
        assert "redeploy run --env prod --detect" in wf.steps[0].command

    def test_workflow_as_shell(self):
        result = load_css_text(self.CSS)
        sh = result.workflows[0].as_shell()
        assert "#!/bin/bash" in sh
        assert "deploy:prod" in sh
        assert "redeploy run" in sh

    def test_no_manifest_when_empty(self):
        result = load_css_text("""
            template[id="rpi"] { strategy: native_kiosk; }
        """)
        assert result.manifest is None

    def test_raw_nodes(self):
        result = load_css_text(self.CSS)
        types = {n.selector_type for n in result.raw_nodes}
        assert "environment" in types
        assert "template" in types
        assert "workflow" in types


# ── manifest_to_css ────────────────────────────────────────────────────────────


def test_manifest_to_css_roundtrip():
    css = textwrap.dedent("""
        @app testapp;
        @spec migration.yaml;

        environment[name="prod"] {
          host: root@10.0.0.1;
          strategy: docker_full;
        }
    """)
    result = load_css_text(css)
    exported = manifest_to_css(result.manifest)
    assert "@app testapp" in exported
    assert 'environment[name="prod"]' in exported
    assert "root@10.0.0.1" in exported


# ── templates_to_css ───────────────────────────────────────────────────────────


def test_templates_to_css():
    css = textwrap.dedent("""
        template[id="rpi-kiosk"] {
          strategy: native_kiosk;
          environment: kiosk;
          note: Needs openbox;
        }
    """)
    result = load_css_text(css)
    exported = templates_to_css(result.templates)
    assert 'template[id="rpi-kiosk"]' in exported
    assert "native_kiosk" in exported
    assert "Needs openbox" in exported


# ── load_css (file) ───────────────────────────────────────────────────────────


def test_load_css_file(tmp_path):
    from redeploy.dsl import load_css
    css_file = tmp_path / "redeploy.css"
    css_file.write_text(textwrap.dedent("""
        @app filetest;
        environment[name="prod"] {
          host: root@1.2.3.4;
          strategy: docker_full;
        }
    """))
    result = load_css(css_file)
    assert result.manifest.app == "filetest"
    assert result.source_file == css_file

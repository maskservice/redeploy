"""CSS-like DSL parser for ``redeploy.css`` / ``redeploy.less``.

Grammar (informal)::

    file        = (at_rule | block | comment)*
    at_rule     = "@" ident value ";"
    block       = selector "{" declaration* "}"
    selector    = ident ( "[" attr_sel "]" )*
                | ident ">" ident                  # child selector
    attr_sel    = ident "=" quoted_str
    declaration = property ":" value ";"
               |  property ":" multi_value ";"     # value spanning multiple tokens

    comment     = "//" ... newline
               |  "/*" ... "*/"

Supported selectors:
    app                           — global app metadata
    environment[name="prod"]      — named deployment environment
    template[id="rpi-kiosk"]      — detection template
    workflow[name="deploy:prod"]  — named deployment workflow
    device[name="rpi5"]           — device hint for auto-probe
    detect[stage="N"]             — workflow stage override

Transparency design:
    Every block has an optional ``description:`` property — shown by
    ``redeploy inspect`` and visible to LLMs reading the file.
    Comments before blocks are captured as ``doc`` on the node.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── AST node ─────────────────────────────────────────────────────────────────

@dataclass
class DSLNode:
    """One parsed block from the CSS-like file.

    selector_type: "app" | "environment" | "template" | "workflow" | "device" | "detect" | ...
    attrs:         dict from [key="value"] attribute selectors
    props:         dict of property → value (strings)
    doc:           leading comment text (stripped)
    children:      for nested blocks (future — e.g. workflow steps)
    """
    selector_type: str
    attrs: dict[str, str] = field(default_factory=dict)
    props: dict[str, str] = field(default_factory=dict)
    doc: str = ""
    children: list["DSLNode"] = field(default_factory=list)
    line: int = 0

    @property
    def name(self) -> str:
        return self.attrs.get("name", self.attrs.get("id", ""))

    def get(self, key: str, default: str = "") -> str:
        return self.props.get(key, default)

    def __repr__(self) -> str:
        attrs = "".join(f'[{k}="{v}"]' for k, v in self.attrs.items())
        return f"<DSLNode {self.selector_type}{attrs} props={list(self.props.keys())}>"


# ── Tokeniser ─────────────────────────────────────────────────────────────────

_SELECTOR_RE = re.compile(
    r"""
    (?P<type>[a-zA-Z_][a-zA-Z0-9_-]*)      # selector type  e.g. environment
    (?P<attrs>(?:\[[^\]]+\])*)              # optional [key="val"] parts
    \s*\{                                   # opening brace
    """,
    re.VERBOSE,
)

_ATTR_RE = re.compile(r'\[([a-zA-Z_][a-zA-Z0-9_-]*)=?"?([^"\]]*)"?\]')

_ATRULE_RE = re.compile(
    r"""
    @(?P<name>[a-zA-Z_][a-zA-Z0-9_-]*)   # @directive
    \s+(?P<value>.+?);                     # value ending with ;
    """,
    re.VERBOSE,
)

_PROP_RE = re.compile(
    r"""
    (?P<key>[a-zA-Z_][a-zA-Z0-9_\-]*)    # property name
    \s*:\s*                                # colon separator
    (?P<value>[^;{]+?)                     # value (lazy, no ; or {)
    \s*;                                   # semicolon terminator
    """,
    re.VERBOSE,
)


def _strip_comments(text: str) -> str:
    """Remove /* … */ block comments (preserving line count via newlines)."""
    def replace(m: re.Match) -> str:
        return "\n" * m.group(0).count("\n")
    return re.sub(r"/\*.*?\*/", replace, text, flags=re.DOTALL)


# ── Parser ────────────────────────────────────────────────────────────────────

class RedeployDSLParser:
    """Parse a ``redeploy.css`` or ``redeploy.less`` file into a list of DSLNode objects.

    Usage::

        parser = RedeployDSLParser()
        nodes = parser.parse(Path("redeploy.css").read_text())
        for node in nodes:
            print(node.selector_type, node.name, node.props)

    At-rules (``@app c2004``, ``@version 1.0``) become a single
    ``DSLNode(selector_type="@", attrs={"name": directive}, props={"value": val})``.

    Line comments (``//``) are captured as ``doc`` on the *following* block.
    """

    def __init__(self) -> None:
        self._nodes: list[DSLNode] = []
        self._at_rules: dict[str, str] = {}
        self._pending_doc: str = ""

    def parse(self, source: str) -> list[DSLNode]:
        self._nodes = []
        self._at_rules = {}
        self._pending_doc = ""

        # Strip block comments first
        source = _strip_comments(source)

        i = 0
        lines = source.split("\n")
        line_no = 0

        while line_no < len(lines):
            raw = lines[line_no]
            stripped = raw.strip()

            # Line comment → accumulate as doc for next block
            if stripped.startswith("//"):
                doc_text = stripped[2:].strip()
                self._pending_doc = (self._pending_doc + "\n" + doc_text).strip()
                line_no += 1
                continue

            # At-rule: @app c2004;
            m = _ATRULE_RE.match(stripped)
            if m:
                name, value = m.group("name"), m.group("value").strip()
                self._at_rules[name] = value
                node = DSLNode(
                    selector_type="@" + name,
                    props={"value": value},
                    doc=self._pending_doc,
                    line=line_no + 1,
                )
                self._nodes.append(node)
                self._pending_doc = ""
                line_no += 1
                continue

            # Selector + opening brace — may span to next lines
            m = _SELECTOR_RE.match(stripped)
            if m:
                sel_type = m.group("type")
                attrs_str = m.group("attrs")
                attrs = dict(_ATTR_RE.findall(attrs_str))

                # Collect body until matching closing brace
                body_lines, line_no = self._collect_body(lines, line_no)
                body = "\n".join(body_lines)
                props = self._parse_props(body)

                node = DSLNode(
                    selector_type=sel_type,
                    attrs=attrs,
                    props=props,
                    doc=self._pending_doc,
                    line=line_no,
                )
                self._nodes.append(node)
                self._pending_doc = ""
                continue

            # Empty / unrecognised line
            if stripped:
                pass  # silently skip unknown lines
            line_no += 1

        return self._nodes

    # ── helpers ───────────────────────────────────────────────────────────────

    def _collect_body(
        self, lines: list[str], start: int
    ) -> tuple[list[str], int]:
        """Return (body_lines, next_line_index) after consuming the { … } block."""
        depth = 0
        body: list[str] = []
        i = start
        while i < len(lines):
            line = lines[i]
            depth += line.count("{") - line.count("}")
            if depth <= 0 and i > start:
                i += 1
                break
            if i > start:
                body.append(line)
            else:
                # First line: everything after the opening brace
                after_brace = line.split("{", 1)[-1].rstrip("}")
                body.append(after_brace)
            i += 1
        return body, i

    def _parse_props(self, body: str) -> dict[str, str]:
        """Extract key: value; pairs from a block body string."""
        props: dict[str, str] = {}
        # Strip line comments inside body
        body = re.sub(r"//[^\n]*", "", body)
        for m in _PROP_RE.finditer(body):
            key = m.group("key").strip()
            value = m.group("value").strip().strip('"').strip("'")
            # Multi-value: step-1, step-2 etc — accumulate as list
            if key in props:
                existing = props[key]
                if not isinstance(existing, list):
                    props[key] = [existing, value]  # type: ignore[assignment]
                else:
                    existing.append(value)           # type: ignore[union-attr]
            else:
                props[key] = value
        return props

    @property
    def at_rules(self) -> dict[str, str]:
        return self._at_rules

    def nodes_of_type(self, sel_type: str) -> list[DSLNode]:
        return [n for n in self._nodes if n.selector_type == sel_type]

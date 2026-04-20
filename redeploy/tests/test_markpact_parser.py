from __future__ import annotations

import textwrap

import pytest

from redeploy.markpact import MarkpactParseError, parse_markpact_text


def test_parse_markpact_text_extracts_blocks_and_lines():
    document = parse_markpact_text(
        textwrap.dedent("""\
            # Demo

            ```markpact:config yaml
            name: parser test
            ```

            ```toml markpact:steps
            [[extra_steps]]
            id = "wait_startup"
            seconds = 5
            ```
        """),
        path="demo.md",
    )

    assert len(document.blocks) == 2
    assert document.blocks[0].kind == "config"
    assert document.blocks[0].format == "yaml"
    assert document.blocks[0].start_line == 3
    assert document.blocks[1].kind == "steps"
    assert document.blocks[1].format == "toml"
    assert document.blocks[1].start_line == 7


def test_parse_markpact_text_requires_markpact_blocks():
    with pytest.raises(MarkpactParseError) as exc_info:
        parse_markpact_text("# No fenced blocks\n", path="demo.md")

    assert "No markpact blocks found" in str(exc_info.value)

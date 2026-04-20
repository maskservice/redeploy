from __future__ import annotations

import textwrap

import pytest

from redeploy.markpact import (
    MarkpactParseError,
    extract_script_by_ref,
    parse_markpact_text,
)


def test_parse_markpact_text_extracts_blocks_and_lines():
    document = parse_markpact_text(
        textwrap.dedent("""\
            # Demo

            ```yaml markpact:config
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


def test_extract_script_by_ref_markpact_ref():
    """Test extracting script from codeblock with markpact:ref."""
    md = textwrap.dedent("""\
        # Demo

        ```bash markpact:ref my-test-script
        #!/bin/bash
        echo "hello from ref"
        exit 0
        ```
    """)
    script = extract_script_by_ref(md, "my-test-script", language="bash")
    assert script is not None
    assert "#!/bin/bash" in script
    assert "hello from ref" in script


def test_extract_script_by_ref_not_found():
    """Test that missing ref returns None."""
    md = textwrap.dedent("""\
        ```bash markpact:ref other-script
        echo "other"
        ```
    """)
    script = extract_script_by_ref(md, "missing-script", language="bash")
    assert script is None


def test_parse_markpact_text_with_ref_id():
    """Test that parser extracts ref_id from markpact:ref."""
    document = parse_markpact_text(
        textwrap.dedent("""\
            # Demo

            ```bash markpact:ref my-script-id
            #!/bin/bash
            echo "test"
            ```
        """),
        path="demo.md",
    )

    assert len(document.blocks) == 1
    assert document.blocks[0].kind == "ref"
    assert document.blocks[0].ref_id == "my-script-id"
    assert "#!/bin/bash" in document.blocks[0].content

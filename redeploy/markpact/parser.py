from __future__ import annotations

from pathlib import Path

from markdown_it import MarkdownIt

from .models import MarkpactBlock, MarkpactDocument


class MarkpactParseError(ValueError):
    """Raised when a markdown markpact document cannot be parsed."""


def parse_markpact_file(path: str | Path) -> MarkpactDocument:
    file_path = Path(path)
    return parse_markpact_text(file_path.read_text(encoding="utf-8"), path=file_path)


def parse_markpact_text(text: str, *, path: str | Path = "migration.md") -> MarkpactDocument:
    source_path = Path(path)
    parser = MarkdownIt("commonmark")
    tokens = parser.parse(text)
    blocks: list[MarkpactBlock] = []

    for token in tokens:
        if token.type != "fence":
            continue
        parsed = _parse_markpact_fence_info(token.info)
        if parsed is None:
            continue

        kind, format_name, ref_id = parsed
        start_line = (token.map[0] + 1) if token.map else 1
        end_line = token.map[1] if token.map else start_line
        blocks.append(MarkpactBlock(
            kind=kind,
            format=format_name,
            content=token.content,
            start_line=start_line,
            end_line=end_line,
            ref_id=ref_id,
        ))

    if not blocks:
        raise MarkpactParseError(
            f"No markpact blocks found in {source_path}. Expected fenced blocks like ```yaml markpact:config."
        )

    return MarkpactDocument(path=source_path, blocks=blocks)


def _parse_markpact_fence_info(info: str) -> tuple[str, str | None, str | None] | None:
    """Parse fence info, returns (kind, format_name, ref_id) or None.

    Supports:
    - ```yaml markpact:steps
    - ```bash markpact:ref kiosk-browser-configuration-script
    """
    tokens = [part for part in info.strip().split() if part]
    if not tokens:
        return None

    kind: str | None = None
    format_name: str | None = None
    ref_id: str | None = None
    prev_was_markpact_ref = False

    for token in tokens:
        if token.startswith("markpact:"):
            kind_part = token.split(":", 1)[1].strip().lower()
            if kind_part.startswith("ref"):
                kind = "ref"
                # Check if ref id is in the same token: markpact:ref:my-id
                if ":" in kind_part:
                    ref_id = kind_part.split(":", 1)[1].strip()
                else:
                    prev_was_markpact_ref = True
            else:
                kind = kind_part
            continue
        if prev_was_markpact_ref:
            # This token is the ref id after markpact:ref
            ref_id = token
            prev_was_markpact_ref = False
            continue
        if format_name is None and "=" not in token:
            format_name = token.lower()

    if not kind:
        return None

    if format_name is None and kind in {"config", "steps", "rollback"}:
        format_name = "yaml"

    return kind, format_name, ref_id


def parse_markpact_file_with_refs(path: str | Path) -> tuple[MarkpactDocument, dict[str, str]]:
    """Parse markpact file and extract all referenced scripts.
    
    Returns:
        (document, refs) where refs is dict of ref_id -> script_content
    """
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    doc = parse_markpact_text(text, path=file_path)
    
    # Extract all refs
    refs: dict[str, str] = {}
    parser = MarkdownIt("commonmark")
    tokens = parser.parse(text)
    
    for token in tokens:
        if token.type != "fence":
            continue
        parsed = _parse_markpact_fence_info(token.info)
        if parsed is None:
            continue
        kind, format_name, ref_id = parsed
        if kind == "ref" and ref_id:
            refs[ref_id] = token.content
    
    return doc, refs


def extract_script_by_ref(text: str, ref_id: str, language: str = "bash") -> str | None:
    """Extract script from codeblock marked with markpact:ref <ref_id>.
    
    Example markdown:
        ```bash markpact:ref my-script-id
        #!/bin/bash
        echo "hello"
        ```
    
    Args:
        text: Full markdown content
        ref_id: The reference ID to find
        language: Expected codeblock language
    
    Returns:
        Script content or None if not found
    """
    import re
    
    lines = text.splitlines()
    in_target_block = False
    script_lines: list[str] = []
    
    for line in lines:
        # Check for opening fence with markpact:ref
        fence_match = re.match(rf'^```{language}\s+markpact:ref\s+{re.escape(ref_id)}\s*$', line, re.IGNORECASE)
        if fence_match:
            in_target_block = True
            script_lines = []
            continue
        
        # Also try generic pattern for any language
        if not in_target_block:
            generic_match = re.match(r'^```(\w+)\s+markpact:ref\s+(\S+)\s*$', line, re.IGNORECASE)
            if generic_match:
                lang, ref = generic_match.groups()
                if ref == ref_id and lang.lower() == language.lower():
                    in_target_block = True
                    script_lines = []
                    continue
        
        # Check for closing fence
        if in_target_block and line.strip() == "```":
            return "\n".join(script_lines)
        
        # Collect lines if inside target block
        if in_target_block:
            script_lines.append(line)
    
    # Handle unclosed block at end of file
    if in_target_block and script_lines:
        return "\n".join(script_lines)
    
    return None


def extract_script_from_markdown(
    text: str,
    section_id: str,
    language: str = "bash"
) -> str | None:
    """Extract script content from a markdown code block by section heading.
    
    Args:
        text: Full markdown content
        section_id: Section heading to find (e.g., "kiosk-browser-configuration-script")
        language: Code block language to extract (default: "bash")
    
    Returns:
        Script content or None if not found
    
    Example:
        ## Kiosk Browser Configuration Script
        ```bash
        #!/bin/bash
        echo "hello"
        ```
        
        extract_script_from_markdown(text, "kiosk-browser-configuration-script")
        # Returns: "#!/bin/bash\necho \"hello\"\n"
    """
    import re
    
    # Normalize section_id for comparison
    normalized_id = section_id.lower().replace("-", " ").replace("_", " ")
    
    lines = text.splitlines()
    in_target_section = False
    code_block_lang = None
    script_lines: list[str] = []
    
    for line in lines:
        # Check for heading that matches section_id
        heading_match = re.match(r'^#{1,6}\s+(.+)$', line, re.IGNORECASE)
        if heading_match:
            heading_text = heading_match.group(1).strip().lower()
            # Check if heading matches (exact or normalized)
            if heading_text == normalized_id or heading_text == section_id.lower():
                in_target_section = True
                script_lines = []
                continue
            elif in_target_section:
                # We found another heading after our target section
                break
        
        # Look for code block start in target section
        if in_target_section:
            fence_match = re.match(r'^```(\w+)?\s*$', line)
            if fence_match:
                if code_block_lang is None:
                    # Opening fence
                    code_block_lang = fence_match.group(1) or ""
                    if code_block_lang.lower() == language.lower():
                        script_lines = []
                else:
                    # Closing fence - check if we captured our target language
                    if code_block_lang.lower() == language.lower() and script_lines:
                        return "\n".join(script_lines)
                    code_block_lang = None
                continue
            
            # Collect lines if we're inside our target code block
            if code_block_lang and code_block_lang.lower() == language.lower():
                script_lines.append(line)
    
    # Check if we have script at end of file (no closing fence)
    if code_block_lang and code_block_lang.lower() == language.lower() and script_lines:
        return "\n".join(script_lines)
    
    return None

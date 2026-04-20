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

        kind, format_name = parsed
        start_line = (token.map[0] + 1) if token.map else 1
        end_line = token.map[1] if token.map else start_line
        blocks.append(MarkpactBlock(
            kind=kind,
            format=format_name,
            content=token.content,
            start_line=start_line,
            end_line=end_line,
        ))

    if not blocks:
        raise MarkpactParseError(
            f"No markpact blocks found in {source_path}. Expected fenced blocks like ```yaml markpact:config."
        )

    return MarkpactDocument(path=source_path, blocks=blocks)


def _parse_markpact_fence_info(info: str) -> tuple[str, str | None] | None:
    tokens = [part for part in info.strip().split() if part]
    if not tokens:
        return None

    kind: str | None = None
    format_name: str | None = None

    for token in tokens:
        if token.startswith("markpact:"):
            kind = token.split(":", 1)[1].strip().lower()
            continue
        if format_name is None and "=" not in token:
            format_name = token.lower()

    if not kind:
        return None

    if format_name is None and kind in {"config", "steps", "rollback"}:
        format_name = "yaml"

    return kind, format_name


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

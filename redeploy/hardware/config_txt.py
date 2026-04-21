"""Idempotent config.txt editing with section awareness."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ConfigEdit:
    """Result of a config.txt edit operation."""
    changed: bool
    old_content: str
    new_content: str
    diff_summary: str  # for reporting


def ensure_line(
    content: str,
    line: str,
    *,
    section: str = "all",
    replaces_pattern: str | None = None,
) -> ConfigEdit:
    """
    Ensure `line` is present in [section] of config.txt.
    If `replaces_pattern` is provided, replace existing line matching the regex.
    Idempotent: identical line → no-op (changed=False).
    """
    lines = content.splitlines(keepends=False)
    section_marker = f"[{section}]"
    in_section = section == "all"  # [all] is default (no marker also OK)
    section_start = -1
    section_end = len(lines)

    for i, current in enumerate(lines):
        stripped = current.strip()
        if stripped == section_marker:
            in_section = True
            section_start = i
            continue
        if in_section and stripped.startswith("[") and stripped.endswith("]"):
            section_end = i
            break

    # Search for line to replace/duplicate within section
    search_range = range(section_start + 1, section_end) if section_start >= 0 else range(section_end)
    pattern = re.compile(replaces_pattern) if replaces_pattern else None

    for i in search_range:
        current_stripped = lines[i].strip()
        if current_stripped == line.strip():
            return ConfigEdit(False, content, content, f"no-op: {line} already present")
        if pattern and pattern.match(current_stripped):
            lines[i] = line
            new = "\n".join(lines) + "\n"
            return ConfigEdit(True, content, new, f"replaced: {current_stripped} → {line}")

    # Insert — if section exists, at its end; if not, add section
    if section_start >= 0:
        lines.insert(section_end, line)
    elif section != "all":
        lines.extend(["", section_marker, line])
    else:
        lines.append(line)

    new = "\n".join(lines) + "\n"
    return ConfigEdit(True, content, new, f"added: {line}")


def ensure_lines(content: str, lines: list[str], *, section: str = "all") -> ConfigEdit:
    """Apply multiple lines in one pass — important because each `ensure_line` re-parses."""
    current_content = content
    all_changes = []
    changed = False

    for line in lines:
        edit = ensure_line(current_content, line, section=section)
        if edit.changed:
            changed = True
            all_changes.append(edit.diff_summary)
            current_content = edit.new_content

    return ConfigEdit(
        changed,
        content,
        current_content,
        "; ".join(all_changes) if all_changes else "no changes",
    )

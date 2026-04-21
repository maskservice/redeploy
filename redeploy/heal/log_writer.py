"""REPAIR_LOG.md writing utilities."""
from __future__ import annotations

import datetime
from pathlib import Path


_LOG_HEADER = "# Repair Log\n\nAuto-repairs by ``redeploy run --heal``.\n\n"


def write_repair_log(
    spec_path: Path,
    version: str,
    repairs: list[dict],
) -> None:
    """Append an entry to *REPAIR_LOG.md* adjacent to the spec file.

    Parameters
    ----------
    spec_path:
        Path to the spec that was healed.
    version:
        Current project version (written into the log heading).
    repairs:
        List of repair dicts produced by :class:`HealRunner`.
    """
    log_path = spec_path.parent / "REPAIR_LOG.md"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"## {version} -- {now}\n"]
    if repairs:
        lines.append("### LLM repairs\n")
        for r in repairs:
            lines.append(f"- **`{r['step']}`**: {r.get('summary', 'fixed')}\n")
            if r.get("diag_hint"):
                lines.append(f"  - hint: `{r['diag_hint'][:120]}`\n")
    else:
        lines.append("Deployment completed without repairs.\n")
    lines.append("\n")
    entry = "".join(lines)

    if log_path.exists():
        existing = log_path.read_text()
        if "# " in existing:
            idx = existing.index("\n", existing.index("# ")) + 1
            content = existing[:idx] + "\n" + entry + existing[idx:]
        else:
            content = entry + existing
    else:
        content = _LOG_HEADER + entry

    log_path.write_text(content)

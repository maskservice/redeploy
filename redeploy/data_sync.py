"""SQLite data-sync helpers — moved from deploy/strategies/_data_sync.py.

Used by deploy strategies and redeploy apply steps.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Sequence

DBSyncSpec = tuple[str, Sequence[str]]


def collect_sqlite_counts(app_root: Path, db_specs: Sequence[DBSyncSpec]) -> dict[str, int]:
    """Collect row counts for the given SQLite tables under *app_root*.

    Returns a flat mapping of ``{table_name: row_count}``. Missing databases or
    tables are skipped quietly so deploy verification can continue with partial data.
    """
    counts: dict[str, int] = {}
    for rel_path, tables in db_specs:
        local_db = app_root / rel_path
        if not local_db.exists():
            continue
        try:
            conn = sqlite3.connect(str(local_db), timeout=5)
        except Exception:
            continue
        try:
            for table in tables:
                try:
                    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                    if row:
                        counts[table] = int(row[0])
                except Exception:
                    continue
        finally:
            conn.close()
    return counts


def rsync_timeout_for_path(path: Path, minimum: int = 300, base: int = 60, per_mb: int = 2) -> int:
    """Compute a conservative rsync timeout based on file size (seconds)."""
    size_mb = path.stat().st_size / (1024 * 1024)
    return max(minimum, int(base + size_mb * per_mb))

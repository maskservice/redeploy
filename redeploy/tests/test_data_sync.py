"""Tests for data_sync.py — collect_sqlite_counts and rsync_timeout_for_path."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from redeploy.data_sync import collect_sqlite_counts, rsync_timeout_for_path


# ── collect_sqlite_counts ─────────────────────────────────────────────────────


class TestCollectSqliteCounts:
    def _db(self, tmp_path: Path, name: str, tables: dict[str, int]) -> Path:
        """Create a SQLite DB at tmp_path/name with given tables and row counts."""
        db_path = tmp_path / name
        conn = sqlite3.connect(str(db_path))
        for table, count in tables.items():
            conn.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)")
            for i in range(count):
                conn.execute(f"INSERT INTO {table} VALUES ({i})")
        conn.commit()
        conn.close()
        return db_path

    def test_basic_counts(self, tmp_path):
        self._db(tmp_path, "app.db", {"users": 5, "orders": 3})
        result = collect_sqlite_counts(tmp_path, [("app.db", ["users", "orders"])])
        assert result["users"] == 5
        assert result["orders"] == 3

    def test_missing_db_skipped(self, tmp_path):
        result = collect_sqlite_counts(tmp_path, [("nonexistent.db", ["users"])])
        assert result == {}

    def test_missing_table_skipped(self, tmp_path):
        self._db(tmp_path, "app.db", {"users": 2})
        result = collect_sqlite_counts(tmp_path, [("app.db", ["users", "missing_table"])])
        assert result["users"] == 2
        assert "missing_table" not in result

    def test_empty_table(self, tmp_path):
        self._db(tmp_path, "app.db", {"empty": 0})
        result = collect_sqlite_counts(tmp_path, [("app.db", ["empty"])])
        assert result["empty"] == 0

    def test_multiple_dbs(self, tmp_path):
        self._db(tmp_path, "a.db", {"alpha": 10})
        self._db(tmp_path, "b.db", {"beta": 20})
        result = collect_sqlite_counts(tmp_path, [
            ("a.db", ["alpha"]),
            ("b.db", ["beta"]),
        ])
        assert result["alpha"] == 10
        assert result["beta"] == 20

    def test_empty_specs(self, tmp_path):
        result = collect_sqlite_counts(tmp_path, [])
        assert result == {}

    def test_large_row_count(self, tmp_path):
        db_path = tmp_path / "big.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE logs (id INTEGER PRIMARY KEY)")
        conn.executemany("INSERT INTO logs VALUES (?)", [(i,) for i in range(1000)])
        conn.commit()
        conn.close()
        result = collect_sqlite_counts(tmp_path, [("big.db", ["logs"])])
        assert result["logs"] == 1000


# ── rsync_timeout_for_path ────────────────────────────────────────────────────


class TestRsyncTimeoutForPath:
    def _file(self, tmp_path: Path, size_bytes: int) -> Path:
        f = tmp_path / "data.db"
        f.write_bytes(b"\x00" * size_bytes)
        return f

    def test_minimum_respected(self, tmp_path):
        f = self._file(tmp_path, 1)   # 1 byte → well below minimum
        t = rsync_timeout_for_path(f, minimum=300)
        assert t == 300

    def test_scales_with_size(self, tmp_path):
        small = self._file(tmp_path, 1 * 1024 * 1024)    # 1 MB
        tmp2 = tmp_path / "sub"
        tmp2.mkdir()
        large_f = tmp2 / "data.db"
        large_f.write_bytes(b"\x00" * (100 * 1024 * 1024))   # 100 MB

        t_small = rsync_timeout_for_path(small, minimum=0, base=0, per_mb=2)
        t_large = rsync_timeout_for_path(large_f, minimum=0, base=0, per_mb=2)
        assert t_large > t_small

    def test_custom_minimum(self, tmp_path):
        f = self._file(tmp_path, 1)
        t = rsync_timeout_for_path(f, minimum=60)
        assert t == 60

    def test_custom_per_mb(self, tmp_path):
        f = self._file(tmp_path, 10 * 1024 * 1024)   # 10 MB
        t = rsync_timeout_for_path(f, minimum=0, base=0, per_mb=5)
        assert t == 50   # 10 MB * 5 s/MB

    def test_base_added(self, tmp_path):
        f = self._file(tmp_path, 0)
        t = rsync_timeout_for_path(f, minimum=0, base=30, per_mb=0)
        assert t == 30

    def test_returns_int(self, tmp_path):
        f = self._file(tmp_path, 1234567)
        t = rsync_timeout_for_path(f)
        assert isinstance(t, int)

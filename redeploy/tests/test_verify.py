"""Tests for verify.py — VerifyContext and verify_data_integrity."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from redeploy.verify import VerifyContext, verify_data_integrity


# ── helpers ───────────────────────────────────────────────────────────────────


def _remote(ok: bool = True, stdout: str = "", stderr: str = ""):
    r = MagicMock()
    r.success = ok
    r.stdout = stdout
    r.stderr = stderr
    remote = MagicMock()
    remote.run.return_value = r
    return remote


# ── VerifyContext.check ────────────────────────────────────────────────────────


class TestVerifyContextCheck:
    def test_pass_without_expect(self):
        ctx = VerifyContext(device_id="dev1")
        ctx.check(_remote(ok=True, stdout="anything"), "test_cmd", "echo ok")
        assert ctx.passed == 1
        assert ctx.failed == 0

    def test_pass_with_expect_found(self):
        ctx = VerifyContext(device_id="dev1")
        ctx.check(_remote(ok=True, stdout="version: 1.0.20"), "ver", "cat version", expect="1.0.20")
        assert ctx.passed == 1

    def test_fail_expect_not_found(self):
        ctx = VerifyContext(device_id="dev1")
        ctx.check(_remote(ok=True, stdout="version: 1.0.19"), "ver", "cat version", expect="1.0.20")
        assert ctx.failed == 1
        assert ctx.errors

    def test_fail_remote_error(self):
        ctx = VerifyContext(device_id="dev1")
        ctx.check(_remote(ok=False, stderr="connection refused"), "cmd", "echo", critical=True)
        assert ctx.failed == 1
        assert ctx.errors

    def test_non_critical_fail_not_in_errors(self):
        ctx = VerifyContext(device_id="dev1")
        ctx.check(_remote(ok=False), "opt", "cmd", critical=False)
        assert ctx.failed == 1
        assert ctx.errors == []

    def test_check_returns_true_on_pass(self):
        ctx = VerifyContext(device_id="dev1")
        result = ctx.check(_remote(ok=True, stdout="ok"), "t", "echo ok")
        assert result is True

    def test_check_returns_false_on_fail(self):
        ctx = VerifyContext(device_id="dev1")
        result = ctx.check(_remote(ok=False), "t", "false")
        assert result is False

    def test_checks_list_has_pass_marker(self):
        ctx = VerifyContext(device_id="dev1")
        ctx.check(_remote(ok=True, stdout="hi"), "my_check", "echo hi")
        assert any("[PASS]" in c for c in ctx.checks)

    def test_checks_list_has_fail_marker(self):
        ctx = VerifyContext(device_id="dev1")
        ctx.check(_remote(ok=False), "my_check", "false")
        assert any("[FAIL]" in c for c in ctx.checks)


# ── VerifyContext add_* ────────────────────────────────────────────────────────


class TestVerifyContextManual:
    def test_add_pass(self):
        ctx = VerifyContext(device_id="dev1")
        ctx.add_pass("manual_pass")
        assert ctx.passed == 1
        assert ctx.ok

    def test_add_fail(self):
        ctx = VerifyContext(device_id="dev1")
        ctx.add_fail("manual_fail", "detail here")
        assert ctx.failed == 1
        assert not ctx.ok
        assert "manual_fail" in ctx.errors[0]

    def test_add_fail_no_detail(self):
        ctx = VerifyContext(device_id="dev1")
        ctx.add_fail("f")
        assert ctx.failed == 1
        assert ctx.errors == []

    def test_add_warn(self):
        ctx = VerifyContext(device_id="dev1")
        ctx.add_warn("something unusual")
        assert ctx.warned == 1
        assert ctx.ok   # warn doesn't fail

    def test_add_info(self):
        ctx = VerifyContext(device_id="dev1")
        ctx.add_info("informational message")
        assert ctx.total == 0   # info not counted as pass/fail/warn
        assert ctx.ok

    def test_mixed_results(self):
        ctx = VerifyContext(device_id="dev1")
        ctx.add_pass("p1")
        ctx.add_pass("p2")
        ctx.add_fail("f1", "err")
        ctx.add_warn("w1")
        assert ctx.passed == 2
        assert ctx.failed == 1
        assert ctx.warned == 1
        assert ctx.total == 4
        assert not ctx.ok


# ── VerifyContext.ok and summary ───────────────────────────────────────────────


class TestVerifyContextSummary:
    def test_ok_true_when_no_failures(self):
        ctx = VerifyContext(device_id="dev1")
        ctx.add_pass("a")
        ctx.add_pass("b")
        assert ctx.ok

    def test_ok_false_when_has_failure(self):
        ctx = VerifyContext(device_id="dev1")
        ctx.add_pass("a")
        ctx.add_fail("b", "boom")
        assert not ctx.ok

    def test_summary_all_pass(self):
        ctx = VerifyContext(device_id="dev1")
        ctx.add_pass("x")
        ctx.add_pass("y")
        s = ctx.summary()
        assert "2/2" in s
        assert "FAILED" not in s

    def test_summary_with_failures(self):
        ctx = VerifyContext(device_id="dev1")
        ctx.add_pass("x")
        ctx.add_fail("y", "kaboom")
        s = ctx.summary()
        assert "FAILED" in s
        assert "kaboom" in s

    def test_summary_with_warnings(self):
        ctx = VerifyContext(device_id="dev1")
        ctx.add_pass("x")
        ctx.add_warn("slow disk")
        s = ctx.summary()
        assert "warning" in s.lower()

    def test_empty_context_summary(self):
        ctx = VerifyContext(device_id="dev1")
        s = ctx.summary()
        assert "0/0" in s


# ── verify_data_integrity ──────────────────────────────────────────────────────


class TestVerifyDataIntegrity:
    def test_matching_counts_pass(self):
        ctx = VerifyContext(device_id="dev1")
        verify_data_integrity(ctx, {"users": 100, "orders": 50}, {"users": 100, "orders": 50})
        assert ctx.ok
        assert ctx.passed == 2

    def test_mismatch_fails(self):
        ctx = VerifyContext(device_id="dev1")
        verify_data_integrity(ctx, {"users": 100}, {"users": 99})
        assert not ctx.ok
        assert ctx.failed == 1
        assert "local=100" in ctx.errors[0] or "99" in ctx.errors[0]

    def test_remote_empty_fails(self):
        ctx = VerifyContext(device_id="dev1")
        verify_data_integrity(ctx, {"users": 50}, {"users": 0})
        assert not ctx.ok
        assert "empty" in ctx.errors[0].lower()

    def test_missing_remote_table_fails(self):
        ctx = VerifyContext(device_id="dev1")
        verify_data_integrity(ctx, {"users": 10}, {})
        assert not ctx.ok

    def test_empty_local_counts(self):
        ctx = VerifyContext(device_id="dev1")
        verify_data_integrity(ctx, {}, {"users": 10})
        assert ctx.ok   # nothing to check

    def test_dict_local_count_uses_local_key(self):
        ctx = VerifyContext(device_id="dev1")
        # local_counts[table] can be {"local": N, "remote": M}
        verify_data_integrity(ctx, {"users": {"local": 42}}, {"users": 42})
        assert ctx.ok

    def test_multiple_tables_partial_fail(self):
        ctx = VerifyContext(device_id="dev1")
        verify_data_integrity(
            ctx,
            {"users": 100, "orders": 50, "logs": 200},
            {"users": 100, "orders": 49, "logs": 200},
        )
        assert ctx.passed == 2
        assert ctx.failed == 1

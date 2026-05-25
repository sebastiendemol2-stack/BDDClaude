"""Tests for the M8 duplicate-check script (acceptance gate)."""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "svc")

import tenant_duplicate_check as dc  # noqa: E402


class FakeResp:
    def __init__(self, payload, status=200):
        self.status_code = status
        self._payload = payload
        self.text = ""

    def raise_for_status(self):
        if self.status_code >= 400 and self.status_code != 404:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


# ---------- arg parsing ----------

def test_parse_argv_default():
    assert dc._parse_argv([]) == {"json": False, "strict": False}


def test_parse_argv_flags():
    assert dc._parse_argv(["--json", "--strict"]) == {"json": True, "strict": True}


def test_parse_argv_rejects_unknown():
    with pytest.raises(SystemExit):
        dc._parse_argv(["--bogus"])


def test_parse_argv_help_exits_zero():
    with pytest.raises(SystemExit) as exc:
        dc._parse_argv(["--help"])
    assert exc.value.code == 0


# ---------- analyze ----------

def test_analyze_passes_on_clean_rows():
    rows = [
        {"tenant_id": "t1", "slug": "alpha"},
        {"tenant_id": "t1", "slug": "beta"},
        {"tenant_id": "t2", "slug": "alpha"},  # same value, different tenant -> OK
    ]
    out = dc.analyze(rows, "slug")
    assert out["total_rows"] == 3
    assert out["null_tenant_id"] == 0
    assert out["unique_pairs"] == 3
    assert out["duplicate_pairs"] == 0


def test_analyze_detects_composite_duplicates():
    rows = [
        {"tenant_id": "t1", "slug": "alpha"},
        {"tenant_id": "t1", "slug": "alpha"},  # duplicate composite
        {"tenant_id": "t2", "slug": "alpha"},  # different tenant -> OK
    ]
    out = dc.analyze(rows, "slug")
    assert out["duplicate_pairs"] == 1
    assert out["duplicate_samples"][0] == {"tenant_id": "t1", "value": "alpha", "count": 2}


def test_analyze_counts_null_tenant_rows_without_treating_them_as_duplicates():
    rows = [
        {"tenant_id": None, "slug": "alpha"},
        {"tenant_id": None, "slug": "alpha"},
        {"tenant_id": "t1", "slug": "alpha"},
    ]
    out = dc.analyze(rows, "slug")
    assert out["null_tenant_id"] == 2
    assert out["duplicate_pairs"] == 0  # the t1/alpha pair is unique


# ---------- fetch_column ----------

def test_fetch_column_returns_empty_on_404_table_missing(monkeypatch):
    monkeypatch.setattr(dc.httpx, "get", lambda *a, **kw: FakeResp([], status=404))
    assert dc.fetch_column("https://x", "k", "missing_table", "slug") == []


def test_fetch_column_paginates_until_short_batch(monkeypatch):
    calls = {"n": 0}
    pages = [
        [{"tenant_id": "t1", "slug": f"x{i}"} for i in range(1000)],
        [{"tenant_id": "t1", "slug": "x1000"}],  # short -> last page
    ]

    def fake_get(url, headers=None, timeout=None):
        idx = calls["n"]
        calls["n"] += 1
        return FakeResp(pages[idx])

    monkeypatch.setattr(dc.httpx, "get", fake_get)
    rows = dc.fetch_column("https://x", "k", "vault_entries", "obsidian_path")
    assert len(rows) == 1001
    assert calls["n"] == 2


# ---------- run_checks ----------

def test_run_checks_ok_when_no_duplicates_and_no_null(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")
    monkeypatch.setattr(dc, "fetch_column", lambda *a, **kw: [
        {"tenant_id": "t1", a[3]: "v1"},
    ])
    report = dc.run_checks()
    assert report["ok"] is True
    assert all(c["passed"] for c in report["checks"])


def test_run_checks_fails_when_null_tenant_present(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")
    # Inject one null-tenant row only on vault_entries.
    def fake_fetch(url, key, table, column):
        if table == "vault_entries":
            return [{"tenant_id": None, "obsidian_path": "wiki/x.md"}]
        return [{"tenant_id": "t1", column: "v1"}]
    monkeypatch.setattr(dc, "fetch_column", fake_fetch)
    report = dc.run_checks()
    assert report["ok"] is False
    failed = [c for c in report["checks"] if not c["passed"]]
    assert len(failed) == 1
    assert failed[0]["table"] == "vault_entries"
    assert failed[0]["null_tenant_id"] == 1


def test_run_checks_fails_when_composite_duplicate_present(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")
    def fake_fetch(url, key, table, column):
        if table == "vault_sections":
            return [
                {"tenant_id": "t1", "slug": "projets"},
                {"tenant_id": "t1", "slug": "projets"},  # duplicate
            ]
        return [{"tenant_id": "t1", column: "v1"}]
    monkeypatch.setattr(dc, "fetch_column", fake_fetch)
    report = dc.run_checks()
    assert report["ok"] is False


# ---------- formatting ----------

def test_format_text_marks_pass_and_ready_when_clean():
    report = {
        "ok": True,
        "checks": [
            {"table": "vault_entries", "column": "obsidian_path", "passed": True,
             "total_rows": 5, "null_tenant_id": 0, "null_value": 0,
             "unique_pairs": 5, "duplicate_pairs": 0, "duplicate_samples": []},
        ],
    }
    text = dc.format_text(report)
    assert "[PASS]" in text
    assert "READY" in text


def test_format_text_marks_fail_and_blocked_when_dirty():
    report = {
        "ok": False,
        "checks": [
            {"table": "vault_entries", "column": "obsidian_path", "passed": False,
             "total_rows": 3, "null_tenant_id": 2, "null_value": 0,
             "unique_pairs": 1, "duplicate_pairs": 0, "duplicate_samples": []},
        ],
    }
    text = dc.format_text(report)
    assert "[FAIL]" in text
    assert "BLOCKED" in text
    assert "2 row(s) with NULL tenant_id" in text


# ---------- security: no user-editable metadata ----------

def test_module_never_reads_user_editable_metadata():
    src = Path(dc.__file__).read_text(encoding="utf-8")
    assert "user_metadata" not in src
    assert "raw_user_meta_data" not in src
    assert "auth.role()" not in src

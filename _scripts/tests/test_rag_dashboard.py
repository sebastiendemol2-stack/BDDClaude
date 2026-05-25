import os
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from rag_dashboard import _stats, _recent, _anomalies


def _make_entry(ts: str, query: str, top_k: int, latency: float,
                fallback: bool = False, results: list | None = None) -> dict:
    return {
        "timestamp": ts,
        "query": query,
        "top_k": top_k,
        "latency_ms": latency,
        "fallback": fallback,
        "results": results or [],
    }


# -- _stats -------------------------------------------------------------------

def test_stats_empty():
    assert _stats([]) == {"status": "no data", "entries": 0}


def test_stats_basic():
    entries = [
        _make_entry("2026-05-20T10:00:00", "hello", 2, 10.0),
        _make_entry("2026-05-20T11:00:00", "world", 3, 20.0, fallback=True),
    ]
    stats = _stats(entries)
    assert stats["status"] == "ok"
    assert stats["entries"] == 2
    assert stats["fallback_ratio"] == 0.5
    assert stats["avg_latency_ms"] == 15.0
    assert stats["max_latency_ms"] == 20.0


def test_stats_top_sources():
    entries = [
        _make_entry("2026-05-20T10:00:00", "q", 2, 5.0, results=[
            {"path": "wiki/a.md", "score": 0.9},
            {"path": "wiki/b.md", "score": 0.8},
        ]),
        _make_entry("2026-05-20T11:00:00", "q", 1, 5.0, results=[
            {"path": "wiki/a.md", "score": 0.95},
        ]),
    ]
    stats = _stats(entries)
    assert ("wiki/a.md", 2) in stats["top_sources"]
    assert ("wiki/b.md", 1) in stats["top_sources"]


def test_stats_queries_per_day():
    entries = [
        _make_entry("2026-05-20T10:00:00", "q1", 1, 5.0),
        _make_entry("2026-05-20T11:00:00", "q2", 1, 5.0),
        _make_entry("2026-05-21T10:00:00", "q3", 1, 5.0),
    ]
    stats = _stats(entries)
    assert stats["queries_per_day"] == {"2026-05-20": 2, "2026-05-21": 1}


def test_stats_no_latency():
    entries = [{"timestamp": "2026-05-20T10:00:00", "query": "q", "top_k": 1,
                "fallback": False, "results": []}]
    stats = _stats(entries)
    assert stats["avg_latency_ms"] == 0
    assert stats["max_latency_ms"] == 0


# -- _recent ------------------------------------------------------------------

def test_recent_returns_most_recent_first():
    entries = [
        _make_entry("2026-05-20T10:00:00", "old", 1, 5.0),
        _make_entry("2026-05-20T11:00:00", "recent", 1, 5.0),
    ]
    recent = _recent(entries, n=5)
    assert len(recent) == 2
    assert recent[0]["query"] == "recent"


def test_recent_limits():
    entries = [_make_entry(f"2026-05-20T{i:02d}:00:00", f"q{i}", 1, 5.0)
               for i in range(20)]
    recent = _recent(entries, n=3)
    assert len(recent) == 3


def test_recent_empty():
    assert _recent([], n=5) == []


# -- _anomalies ---------------------------------------------------------------

def test_anomalies_empty():
    assert _anomalies([]) == []


def test_anomalies_high_latency():
    entries = [
        _make_entry("2026-05-20T10:00:00", "normal1", 1, 30.0,
                    results=[{"path": "a.md", "score": 0.9}]),
        _make_entry("2026-05-20T10:01:00", "normal2", 1, 30.0,
                    results=[{"path": "b.md", "score": 0.8}]),
        _make_entry("2026-05-20T10:02:00", "slow", 1, 1000.0,
                    results=[{"path": "c.md", "score": 0.7}]),
    ]
    anoms = _anomalies(entries)
    assert len(anoms) == 1
    assert anoms[0]["query"] == "slow"


def test_anomalies_empty_results():
    entries = [
        _make_entry("2026-05-20T10:00:00", "normal", 1, 10.0,
                    results=[{"path": "a.md", "score": 0.9}]),
        _make_entry("2026-05-20T10:01:00", "empty", 0, 5.0, results=[]),
    ]
    anoms = _anomalies(entries)
    assert any("empty" in a["query"] for a in anoms)


def test_anomalies_no_latency_data():
    entries = [{"timestamp": "2026-05-20T10:00:00", "query": "q", "top_k": 0,
                "fallback": False, "results": []}]
    result = _anomalies(entries)
    assert isinstance(result, list)


# ============================================================
# M8 — Tenant filter on dashboard
# ============================================================

from rag_dashboard import (
    filter_by_tenant,
    _entry_tenant,
    DEFAULT_TENANT_SLUG,
    ALL_TENANTS_SENTINEL,
)


def _tenant_entry(tenant: str | None, ts: str = "2026-05-25T10:00:00"):
    e = _make_entry(ts, "q", 1, 10.0)
    if tenant is not None:
        e["tenant_slug"] = tenant
    return e


def test_entry_tenant_defaults_to_personal_when_missing():
    """Pre-M8 log entries had no tenant_slug -- they must be attributed to personal."""
    e = {"timestamp": "2026-05-20T10:00:00", "query": "q"}
    assert _entry_tenant(e) == DEFAULT_TENANT_SLUG == "personal"


def test_filter_by_tenant_keeps_only_matching_slug():
    entries = [
        _tenant_entry("alpha"),
        _tenant_entry("beta"),
        _tenant_entry("personal"),
    ]
    assert len(filter_by_tenant(entries, "alpha")) == 1
    assert len(filter_by_tenant(entries, "beta")) == 1
    assert len(filter_by_tenant(entries, "personal")) == 1


def test_filter_by_tenant_treats_missing_field_as_personal():
    entries = [
        _tenant_entry(None),       # legacy entry
        _tenant_entry("personal"),
        _tenant_entry("alpha"),
    ]
    assert len(filter_by_tenant(entries, "personal")) == 2
    assert len(filter_by_tenant(entries, "alpha")) == 1


def test_filter_by_tenant_all_sentinel_returns_everything():
    entries = [_tenant_entry("a"), _tenant_entry("b"), _tenant_entry(None)]
    assert filter_by_tenant(entries, ALL_TENANTS_SENTINEL) == entries


def test_dashboard_never_reads_user_editable_metadata():
    """Tenant selection must come from env / CLI, never from user_metadata."""
    from pathlib import Path
    src = Path(__file__).parents[1].joinpath("rag_dashboard.py").read_text(encoding="utf-8")
    assert "user_metadata" not in src
    assert "raw_user_meta_data" not in src
    assert "auth.role()" not in src

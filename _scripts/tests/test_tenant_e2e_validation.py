"""Static + parser tests for the E2E validation script. The integration scenario
itself requires a live Supabase project and is invoked manually."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "svc")

import tenant_e2e_validation as e2e  # noqa: E402


def test_parse_argv_defaults():
    opts = e2e._parse_argv([])
    assert opts["keep"] is False
    assert opts["source_slug"] == e2e.SOURCE_SLUG_DEFAULT
    assert opts["target_slug"] == e2e.TARGET_SLUG_DEFAULT


def test_parse_argv_keep_flag():
    assert e2e._parse_argv(["--keep"])["keep"] is True


def test_parse_argv_custom_slugs():
    opts = e2e._parse_argv(["--source-slug", "a", "--target-slug", "b"])
    assert opts["source_slug"] == "a"
    assert opts["target_slug"] == "b"


def test_parse_argv_refuses_personal_slug():
    """Safety rail: this script wipes test tenants. It must never touch the personal one."""
    with pytest.raises(SystemExit, match="personal"):
        e2e._parse_argv(["--source-slug", "personal"])
    with pytest.raises(SystemExit, match="personal"):
        e2e._parse_argv(["--target-slug", "personal"])


def test_parse_argv_help_exits_zero():
    with pytest.raises(SystemExit) as exc:
        e2e._parse_argv(["--help"])
    assert exc.value.code == 0


def test_parse_argv_rejects_unknown():
    with pytest.raises(SystemExit):
        e2e._parse_argv(["--what"])


def test_run_function_takes_isolation_seriously_in_source():
    src = Path(e2e.__file__).read_text(encoding="utf-8")
    # The isolation assertion must check that A never sees B's title.
    assert "leaked tenant B row into tenant A scope" in src
    # And the RPC must be invoked with tenant_id to make that test meaningful.
    assert "query_vector_hybrid" in src
    assert '"tenant_id": tenant_id' in src or "tenant_id=tenant_id" in src or 'tenant_id=eq.' in src


def test_run_cleans_up_unless_keep_flag(monkeypatch):
    """run() must call delete_entry / delete_tenant for everything it created when keep=False."""
    monkeypatch.setenv("SUPABASE_URL", "https://x")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")

    deleted_entries: list[str] = []
    deleted_tenants: list[str] = []

    monkeypatch.setattr(e2e, "ensure_tenant", lambda url, key, slug: f"tid-{slug}")
    monkeypatch.setattr(e2e, "seed_entry", lambda url, key, tid, p, t, c: f"entry-{tid}")
    # First two calls (A pre-import, B pre-import) return 1; B post-import returns 2.
    counts = iter([1, 1, 2])
    monkeypatch.setattr(e2e, "count_entries", lambda *a, **kw: next(counts))
    monkeypatch.setattr(e2e, "query_vector_hybrid", lambda *a, **kw: [])
    monkeypatch.setattr(e2e, "delete_entry", lambda url, key, eid: deleted_entries.append(eid))
    monkeypatch.setattr(e2e, "delete_tenant", lambda url, key, tid: deleted_tenants.append(tid))

    class _FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return []
    monkeypatch.setattr(e2e.httpx, "get", lambda *a, **kw: _FakeResp())

    # Stub the export/import calls so we don't need a live server.
    monkeypatch.setattr(e2e.tb, "cmd_export", lambda slug, out: {
        "schema_version": "1.0.0",
        "tables": {"vault_sections": 0, "vault_entries": 1},
        "markdown_files": 0,
    })
    monkeypatch.setattr(e2e.tb, "cmd_import", lambda *a, **kw: {
        "imported": {"vault_sections": 0, "vault_entries": 1},
        "cross_tenant_conflicts": 0,
    })

    report = e2e.run(source_slug="e2e-a", target_slug="e2e-b", keep=False)
    assert report["ok"] is True
    # Both tenants must be torn down.
    assert set(deleted_tenants) == {"tid-e2e-a", "tid-e2e-b"}
    # Both seeded entries must be deleted.
    assert "entry-tid-e2e-a" in deleted_entries
    assert "entry-tid-e2e-b" in deleted_entries


def test_run_skips_cleanup_when_keep_is_true(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")

    calls = {"delete_entry": 0, "delete_tenant": 0}
    monkeypatch.setattr(e2e, "ensure_tenant", lambda url, key, slug: f"tid-{slug}")
    monkeypatch.setattr(e2e, "seed_entry", lambda url, key, tid, p, t, c: f"entry-{tid}")
    monkeypatch.setattr(e2e, "count_entries", lambda *a, **kw: 1)
    monkeypatch.setattr(e2e, "query_vector_hybrid", lambda *a, **kw: [])
    monkeypatch.setattr(e2e, "delete_entry", lambda *a, **kw: calls.__setitem__("delete_entry", calls["delete_entry"] + 1))
    monkeypatch.setattr(e2e, "delete_tenant", lambda *a, **kw: calls.__setitem__("delete_tenant", calls["delete_tenant"] + 1))

    class _FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return []
    monkeypatch.setattr(e2e.httpx, "get", lambda *a, **kw: _FakeResp())
    monkeypatch.setattr(e2e.tb, "cmd_export", lambda *a, **kw: {"tables": {"vault_entries": 1}})
    monkeypatch.setattr(e2e.tb, "cmd_import", lambda *a, **kw: {"imported": {"vault_entries": 1}})

    e2e.run(source_slug="e2e-a", target_slug="e2e-b", keep=True)
    assert calls == {"delete_entry": 0, "delete_tenant": 0}


def test_module_never_reads_user_editable_metadata():
    src = Path(e2e.__file__).read_text(encoding="utf-8")
    assert "user_metadata" not in src
    assert "raw_user_meta_data" not in src
    assert "auth.role()" not in src

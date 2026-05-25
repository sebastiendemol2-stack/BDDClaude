"""Tests for the M8 tenant export/import pipeline (`tenant_bundle.py`)."""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Provide env defaults so the module imports cleanly under test.
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")

import tenant_bundle as tb  # noqa: E402


# ---------- helpers ----------

class FakeResp:
    def __init__(self, payload, status=200):
        self.status_code = status
        self._payload = payload
        self.text = json.dumps(payload) if not isinstance(payload, str) else payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


# ---------- arg parsing ----------

def test_parse_argv_export_minimal():
    opts = tb._parse_argv(["export", "--tenant", "alpha", "--out", "/tmp/bundle"])
    assert opts == {"cmd": "export", "tenant": "alpha", "out": "/tmp/bundle", "on_conflict": "skip"}


def test_parse_argv_import_with_on_conflict():
    opts = tb._parse_argv([
        "import", "--tenant", "beta", "--in", "/tmp/bundle", "--on-conflict", "overwrite",
    ])
    assert opts["cmd"] == "import"
    assert opts["tenant"] == "beta"
    assert opts["on_conflict"] == "overwrite"


def test_parse_argv_requires_tenant():
    with pytest.raises(SystemExit):
        tb._parse_argv(["export", "--out", "/tmp/x"])


def test_parse_argv_export_requires_out():
    with pytest.raises(SystemExit):
        tb._parse_argv(["export", "--tenant", "a"])


def test_parse_argv_import_requires_in():
    with pytest.raises(SystemExit):
        tb._parse_argv(["import", "--tenant", "a"])


def test_parse_argv_rejects_unknown_command():
    with pytest.raises(SystemExit):
        tb._parse_argv(["sync", "--tenant", "a"])


# ---------- tenant resolution ----------

def test_resolve_tenant_id_raises_for_unknown(monkeypatch):
    monkeypatch.setattr(tb.httpx, "get", lambda *a, **kw: FakeResp([]))
    with pytest.raises(RuntimeError, match="not found"):
        tb.resolve_tenant_id("https://x", "k", "ghost")


def test_resolve_tenant_id_refuses_inactive(monkeypatch):
    monkeypatch.setattr(
        tb.httpx, "get",
        lambda *a, **kw: FakeResp([{"id": "uuid-1", "status": "suspended"}]),
    )
    with pytest.raises(RuntimeError, match="not active"):
        tb.resolve_tenant_id("https://x", "k", "alpha")


def test_resolve_tenant_id_returns_active_id(monkeypatch):
    monkeypatch.setattr(
        tb.httpx, "get",
        lambda *a, **kw: FakeResp([{"id": "uuid-active", "status": "active"}]),
    )
    assert tb.resolve_tenant_id("https://x", "k", "alpha") == "uuid-active"


# ---------- fetch + jsonl roundtrip ----------

def test_fetch_tenant_rows_filters_by_tenant_id(monkeypatch):
    seen: list[str] = []

    def fake_get(url, headers=None, timeout=None):
        seen.append(url)
        return FakeResp([])  # empty -> stop paging immediately

    monkeypatch.setattr(tb.httpx, "get", fake_get)
    tb.fetch_tenant_rows("https://x", "k", "vault_entries", "tid-1")
    assert seen and "tenant_id=eq.tid-1" in seen[0]
    assert "vault_entries" in seen[0]


def test_write_then_read_jsonl_roundtrip(tmp_path):
    rows = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
    path = tmp_path / "out.jsonl"
    tb.write_jsonl(path, rows)
    assert tb.read_jsonl(path) == rows


def test_read_jsonl_missing_file_returns_empty(tmp_path):
    assert tb.read_jsonl(tmp_path / "nope.jsonl") == []


# ---------- markdown export ----------

def test_export_markdown_writes_files_at_obsidian_paths(tmp_path):
    entries = [
        {"obsidian_path": "wiki/Context/foo.md", "content": "# Foo\nbody"},
        {"obsidian_path": "wiki/Intelligence/bar.md", "content": "# Bar"},
    ]
    count = tb.export_markdown(tmp_path, entries)
    assert count == 2
    assert (tmp_path / "wiki" / "Context" / "foo.md").read_text(encoding="utf-8") == "# Foo\nbody"


def test_export_markdown_refuses_path_traversal(tmp_path):
    entries = [{"obsidian_path": "../escape.md", "content": "evil"}]
    with pytest.raises(ValueError, match="unsafe path"):
        tb.export_markdown(tmp_path, entries)


def test_export_markdown_skips_rows_without_content(tmp_path):
    entries = [
        {"obsidian_path": "wiki/A.md", "content": None},
        {"obsidian_path": None, "content": "x"},
        {"obsidian_path": "wiki/B.md", "content": "good"},
    ]
    assert tb.export_markdown(tmp_path, entries) == 1
    assert (tmp_path / "wiki" / "B.md").exists()


# ---------- export end-to-end (mocked HTTP) ----------

def test_cmd_export_writes_manifest_and_tables(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc")

    calls = {"sections": 0, "entries": 0, "tenant": 0}

    def fake_get(url, headers=None, timeout=None):
        if "vault_tenants" in url:
            calls["tenant"] += 1
            return FakeResp([{"id": "tid-source", "status": "active"}])
        if "vault_sections" in url:
            calls["sections"] += 1
            return FakeResp([{"id": "s1", "slug": "projets", "tenant_id": "tid-source"}])
        if "vault_entries" in url:
            calls["entries"] += 1
            return FakeResp([{
                "id": "e1",
                "obsidian_path": "wiki/Context/foo.md",
                "content": "# Foo\nbody",
                "tenant_id": "tid-source",
            }])
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(tb.httpx, "get", fake_get)

    out_dir = tmp_path / "bundle"
    manifest = tb.cmd_export("source", out_dir)

    assert manifest["schema_version"] == tb.SCHEMA_VERSION
    assert manifest["source"]["tenant_slug"] == "source"
    assert manifest["source"]["tenant_id"] == "tid-source"
    assert manifest["tables"] == {"vault_sections": 1, "vault_entries": 1}
    assert manifest["markdown_files"] == 1

    # On-disk artifacts.
    assert (out_dir / "manifest.json").exists()
    assert tb.read_jsonl(out_dir / "tables" / "vault_entries.jsonl")[0]["obsidian_path"] == "wiki/Context/foo.md"
    assert (out_dir / "markdown" / "wiki" / "Context" / "foo.md").read_text(encoding="utf-8") == "# Foo\nbody"


# ---------- import end-to-end (mocked HTTP) ----------

def _write_bundle(tmp_path: Path, *, with_conflict: bool = False) -> Path:
    bundle = tmp_path / "bundle"
    (bundle / "tables").mkdir(parents=True)
    (bundle / "markdown").mkdir(parents=True)
    tb.write_jsonl(bundle / "tables" / "vault_sections.jsonl", [
        {"id": "s1", "slug": "projets", "tenant_id": "tid-source", "name": "Projets"},
    ])
    tb.write_jsonl(bundle / "tables" / "vault_entries.jsonl", [
        {
            "id": "e1",
            "obsidian_path": "wiki/Context/foo.md",
            "content": "# Foo",
            "tenant_id": "tid-source",
            "created_at": "2026-05-01T00:00:00Z",
            "updated_at": "2026-05-01T00:00:00Z",
        },
    ])
    manifest = {
        "schema_version": tb.SCHEMA_VERSION,
        "exported_at": "2026-05-25T12:00:00Z",
        "source": {"tenant_slug": "source", "tenant_id": "tid-source"},
        "tables": {"vault_sections": 1, "vault_entries": 1},
        "markdown_files": 1,
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return bundle


def test_cmd_import_rewrites_tenant_id_and_strips_server_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc")

    bundle = _write_bundle(tmp_path)
    posted: list[dict] = []

    def fake_get(url, headers=None, timeout=None):
        if "vault_tenants" in url:
            return FakeResp([{"id": "tid-target", "status": "active"}])
        if "vault_entries" in url and "obsidian_path=in." in url:
            return FakeResp([])  # no conflicts
        raise AssertionError(f"Unexpected GET: {url}")

    def fake_post(url, headers=None, json=None, timeout=None):
        posted.append({"url": url, "rows": json, "prefer": headers.get("Prefer", "")})
        return FakeResp([], status=201)

    monkeypatch.setattr(tb.httpx, "get", fake_get)
    monkeypatch.setattr(tb.httpx, "post", fake_post)

    report = tb.cmd_import("target", bundle, on_conflict="skip")
    assert report["target_tenant_id"] == "tid-target"
    assert report["imported"] == {"vault_sections": 1, "vault_entries": 1}
    assert report["cross_tenant_conflicts"] == 0

    # Sections must be posted before entries.
    assert "vault_sections" in posted[0]["url"]
    assert "vault_entries" in posted[1]["url"]

    # tenant_id rewritten, id / created_at / updated_at stripped.
    entry_row = posted[1]["rows"][0]
    assert entry_row["tenant_id"] == "tid-target"
    assert "id" not in entry_row
    assert "created_at" not in entry_row
    assert "updated_at" not in entry_row

    # `skip` strategy must produce ignore-duplicates Prefer header.
    assert "ignore-duplicates" in posted[1]["prefer"]


def test_cmd_import_overwrite_uses_merge_duplicates(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc")
    bundle = _write_bundle(tmp_path)

    posted: list[dict] = []
    monkeypatch.setattr(tb.httpx, "get", lambda *a, **kw: FakeResp(
        [{"id": "tid-target", "status": "active"}] if "vault_tenants" in a[0] else []
    ))
    monkeypatch.setattr(tb.httpx, "post", lambda url, headers=None, json=None, timeout=None: (
        posted.append({"prefer": headers.get("Prefer", "")}) or FakeResp([], 201)
    ))

    tb.cmd_import("target", bundle, on_conflict="overwrite")
    assert any("merge-duplicates" in p["prefer"] for p in posted)


def test_cmd_import_blocks_cross_tenant_path_collision_in_skip_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc")
    bundle = _write_bundle(tmp_path)

    def fake_get(url, headers=None, timeout=None):
        if "vault_tenants" in url:
            return FakeResp([{"id": "tid-target", "status": "active"}])
        if "obsidian_path=in." in url:
            # Same path lives in a *different* tenant — that's the collision case.
            return FakeResp([
                {"obsidian_path": "wiki/Context/foo.md", "tenant_id": "tid-OTHER"},
            ])
        raise AssertionError(url)

    monkeypatch.setattr(tb.httpx, "get", fake_get)
    monkeypatch.setattr(tb.httpx, "post", lambda *a, **kw: FakeResp([], 201))

    with pytest.raises(RuntimeError, match="collision"):
        tb.cmd_import("target", bundle, on_conflict="skip")


def test_cmd_import_rejects_schema_mismatch(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc")
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "manifest.json").write_text(json.dumps({"schema_version": "0.9.0"}), encoding="utf-8")

    with pytest.raises(ValueError, match="schema_version"):
        tb.cmd_import("target", bundle, on_conflict="skip")


def test_cmd_import_rejects_unknown_strategy(tmp_path):
    with pytest.raises(ValueError, match="on-conflict"):
        tb.cmd_import("target", tmp_path, on_conflict="merge-bombs")


# ---------- security: no user-editable JWT fields ----------

def test_module_never_reads_user_editable_metadata():
    src = Path(tb.__file__).read_text(encoding="utf-8")
    assert "user_metadata" not in src
    assert "raw_user_meta_data" not in src
    assert "auth.role()" not in src

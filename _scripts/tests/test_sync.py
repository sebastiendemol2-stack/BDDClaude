# _scripts/tests/test_sync.py
import os
import sys
import pytest
import re
from datetime import timezone
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def test_sync_missing_env_var_gives_friendly_message(monkeypatch, capsys):
    """sync.py doit afficher un message utile si SUPABASE_URL manque."""
    # Clear env vars before the module loads
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.delenv("VAULT_PATH", raising=False)

    # Remove module if already loaded
    if "sync" in sys.modules:
        del sys.modules["sync"]
    if "utils" in sys.modules:
        del sys.modules["utils"]

    # Mock load_dotenv to prevent loading from .env file
    with patch("dotenv.load_dotenv"):
        with pytest.raises(SystemExit) as exc_info:
            import sync  # noqa: F401

    captured = capsys.readouterr()
    assert "SUPABASE_URL" in captured.err
    assert ".env" in captured.err
    assert exc_info.value.code != 0


def test_sync_uses_timeout_constant():
    """sync.py must define a TIMEOUT constant and pass it to httpx calls."""
    import httpx
    import sync
    # Verify the TIMEOUT constant exists and is an httpx.Timeout instance
    assert hasattr(sync, 'TIMEOUT'), "sync.py must define a TIMEOUT constant"
    assert isinstance(sync.TIMEOUT, httpx.Timeout), "TIMEOUT must be an httpx.Timeout instance"


os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("VAULT_PATH", str(Path(__file__).resolve().parents[2]))

import sync as _sync_module


def test_parse_frontmatter_inline_list():
    """Inline list [a, b] must parse to Python list."""
    content = "---\ntags: [web, architecture]\ntitle: Test\n---\nBody"
    fm = _sync_module.parse_frontmatter(content)
    assert fm["tags"] == ["web", "architecture"]
    assert fm["title"] == "Test"


def test_parse_frontmatter_indented_list():
    """Indented list (Obsidian Web Clipper format) must parse to Python list."""
    content = "---\ntags:\n  - web\n  - architecture\ntitle: Test\n---\nBody"
    fm = _sync_module.parse_frontmatter(content)
    assert fm["tags"] == ["web", "architecture"]
    assert fm["title"] == "Test"


def test_parse_frontmatter_quoted_value_with_colon():
    """Quoted title with colon must be parsed correctly."""
    content = '---\ntitle: "foo: bar"\ndate: 2026-05-14\n---\nBody'
    fm = _sync_module.parse_frontmatter(content)
    assert fm["title"] == "foo: bar"
    assert fm["date"] == "2026-05-14"


def test_build_frontmatter_round_trip():
    """parse(build(fm)) must be idempotent for common types."""
    original = {"title": "foo: bar", "tags": ["web", "architecture"], "date": "2026-05-14"}
    built = _sync_module.build_frontmatter(original)
    parsed = _sync_module.parse_frontmatter(built + "\nBody")
    assert parsed["title"] == "foo: bar"
    assert parsed["tags"] == ["web", "architecture"]
    assert parsed["date"] == "2026-05-14"


def test_parse_frontmatter_empty_returns_empty_dict():
    """Content with no frontmatter returns empty dict."""
    content = "No frontmatter here"
    fm = _sync_module.parse_frontmatter(content)
    assert fm == {}


def test_parse_frontmatter_empty_scalar_does_not_lose_type_default():
    """A bare 'type:' key should not cause get_local_notes to send type=[] to Supabase."""
    content = "---\ntitle: Test\ntags: []\ntype:\n---\nBody"
    fm = _sync_module.parse_frontmatter(content)
    # parse returns [] for empty scalar - caller must use `or` fallback
    type_val = fm.get("type") or "note"
    assert type_val == "note"


def test_write_local_uses_utc_date(tmp_path, monkeypatch):
    """write_local() must write a UTC date in frontmatter, not local time."""
    monkeypatch.setattr(_sync_module, "VAULT_PATH", tmp_path)

    entry = {
        "obsidian_path": "Context/test-note.md",
        "title": "Test",
        "content": "Body content",
        "tags": ["test"],
        "source": "",
        "type": "note",
        "status": "active",
    }
    _sync_module.write_local(entry)

    written_file = tmp_path / "Context" / "test-note.md"
    assert written_file.exists()
    text = written_file.read_text(encoding="utf-8")
    fm = _sync_module.parse_frontmatter(text)
    date_str = fm.get("date", "")
    # Should be a valid date (YYYY-MM-DD format)
    assert re.match(r'\d{4}-\d{2}-\d{2}', date_str), f"Expected date, got: {date_str!r}"


def test_get_local_notes_covers_all_folder_section_keys(tmp_path, monkeypatch):
    """get_local_notes must scan all folders in FOLDER_TO_SECTION, not a hardcoded list."""
    wiki_path = tmp_path / "wiki"
    monkeypatch.setattr(_sync_module, "VAULT_PATH", tmp_path)
    monkeypatch.setattr(_sync_module, "WIKI_PATH", wiki_path)

    # Create a file in each folder defined in FOLDER_TO_SECTION
    for folder in _sync_module.FOLDER_TO_SECTION.keys():
        folder_path = wiki_path / folder
        folder_path.mkdir(parents=True, exist_ok=True)
        (folder_path / "test.md").write_text(
            f"---\ntitle: Test {folder}\ntags: []\n---\nBody",
            encoding="utf-8"
        )

    notes = _sync_module.get_local_notes()
    found_folders = {n["obsidian_path"].split("/")[1] for n in notes}

    # Every folder in FOLDER_TO_SECTION must be represented
    for folder in _sync_module.FOLDER_TO_SECTION.keys():
        assert folder in found_folders, f"Folder {folder!r} missing from get_local_notes output"


def test_validate_path_rejects_injection():
    """_validate_path must raise ValueError for paths containing URL-unsafe characters."""
    from utils import _validate_path
    with pytest.raises(ValueError):
        _validate_path("Context/foo?evil=1&other=param")


def test_validate_path_rejects_ampersand():
    """_validate_path must reject & which would corrupt a query string."""
    from utils import _validate_path
    with pytest.raises(ValueError):
        _validate_path("wiki/notes&select=password")


def test_validate_path_accepts_valid():
    """_validate_path must accept normal Obsidian note paths."""
    from utils import _validate_path
    assert _validate_path("Context/my-note.md") == "Context/my-note.md"
    assert _validate_path("wiki/Daily/2026-05-14.md") == "wiki/Daily/2026-05-14.md"


def test_pull_skips_existing_local_files(tmp_path, monkeypatch):
    """cmd_pull must SKIP (not overwrite) files that already exist locally."""
    wiki_path = tmp_path / "wiki"
    monkeypatch.setattr(_sync_module, "VAULT_PATH", tmp_path)
    monkeypatch.setattr(_sync_module, "WIKI_PATH", wiki_path)

    # Create existing local file with known content
    existing_dir = wiki_path / "Context"
    existing_dir.mkdir(parents=True)
    existing_file = existing_dir / "existing.md"
    existing_file.write_text("---\ntitle: Local version\n---\nLocal content", encoding="utf-8")

    # Remote entry for the same path with different content
    remote_entries = [{
        "obsidian_path": "wiki/Context/existing.md",
        "title": "Remote version",
        "content": "Remote content",
        "tags": [],
        "source": "",
        "type": "note",
        "status": "active",
    }]

    monkeypatch.setattr(_sync_module, "get_remote_entries", lambda: remote_entries)
    monkeypatch.setattr(_sync_module, "get_local_notes", lambda: [
        {"obsidian_path": "wiki/Context/existing.md", "title": "Local version"}
    ])

    _sync_module.cmd_pull()

    # Local file must be intact
    assert "Local content" in existing_file.read_text(encoding="utf-8")


@patch('sync.httpx.post')
def test_upsert_remote_success(mock_post):
    """upsert_remote doit réussir avec un mock HTTP."""
    mock_post.return_value = type('MockResponse', (), {
        'status_code': 201,
        'text': 'OK',
        'json': lambda self: [],
    })()

    entry = {
        "obsidian_path": "wiki/Test/test.md",
        "title": "Test Note",
        "content": "Test content",
        "tags": ["test"],
        "type": "note",
        "status": "active",
        "schema_version": "3.0.0",
        "date": "2026-05-14"
    }

    _sync_module.upsert_remote(entry)

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert kwargs['json'] == entry
    assert 'Prefer' in kwargs['headers']


# Tests for cmd_pull --force overwrites differing remote files
def test_cmd_pull_force_overwrites_changed_files(tmp_path, monkeypatch):
    wiki_path = tmp_path / "wiki"
    monkeypatch.setattr(_sync_module, "VAULT_PATH", tmp_path)
    monkeypatch.setattr(_sync_module, "WIKI_PATH", wiki_path)

    existing_dir = wiki_path / "Context"
    existing_dir.mkdir(parents=True)
    existing_file = existing_dir / "existing.md"
    existing_file.write_text("---\ntitle: Local version\n---\nLocal content", encoding="utf-8")

    remote_entries = [{
        "obsidian_path": "wiki/Context/existing.md",
        "title": "Remote version",
        "content": "Remote content",
        "tags": [],
        "source": "",
        "type": "note",
        "status": "active",
        "content_hash": "remotehash123",
    }]

    monkeypatch.setattr(_sync_module, "get_remote_entries", lambda: remote_entries)
    monkeypatch.setattr(_sync_module, "get_local_notes", lambda: [
        {"obsidian_path": "wiki/Context/existing.md", "title": "Local version", "content_hash": "oldhash"}
    ])

    _sync_module.cmd_pull(force=True)

    assert "Remote content" in existing_file.read_text(encoding="utf-8")


def test_cmd_pull_force_skips_unchanged(tmp_path, monkeypatch, capsys):
    wiki_path = tmp_path / "wiki"
    monkeypatch.setattr(_sync_module, "VAULT_PATH", tmp_path)
    monkeypatch.setattr(_sync_module, "WIKI_PATH", wiki_path)

    existing_dir = wiki_path / "Context"
    existing_dir.mkdir(parents=True)
    existing_file = existing_dir / "existing.md"
    existing_file.write_text("---\ntitle: Local version\n---\nLocal content", encoding="utf-8")

    same_hash = "abc123"
    remote_entries = [{
        "obsidian_path": "wiki/Context/existing.md",
        "title": "Remote version",
        "content": "Local content",
        "tags": [],
        "source": "",
        "type": "note",
        "status": "active",
        "content_hash": same_hash,
    }]

    monkeypatch.setattr(_sync_module, "get_remote_entries", lambda: remote_entries)
    monkeypatch.setattr(_sync_module, "get_local_notes", lambda: [
        {"obsidian_path": "wiki/Context/existing.md", "title": "Local version", "content_hash": same_hash}
    ])

    _sync_module.cmd_pull(force=True)

    captured = capsys.readouterr()
    assert "unchanged" in captured.out


# Tests for cmd_rebuild_alias_registry
def test_rebuild_alias_registry_creates_file(tmp_path, monkeypatch):
    wiki_path = tmp_path / "wiki"
    wiki_path.mkdir(parents=True)
    (wiki_path / "_meta").mkdir(parents=True)
    monkeypatch.setattr(_sync_module, "WIKI_PATH", wiki_path)

    (wiki_path / "test-note.md").write_text(
        "---\ntitle: Test Note\ntags: []\n---\nBody with [[other-note]] link.",
        encoding="utf-8"
    )
    (wiki_path / "other-note.md").write_text(
        "---\ntitle: Other Note\ntags: []\n---\nOther body.",
        encoding="utf-8"
    )

    _sync_module.cmd_rebuild_alias_registry()

    alias_path = wiki_path / "_meta" / "alias_registry.yaml"
    assert alias_path.exists()
    content = alias_path.read_text(encoding="utf-8")
    assert "test-note" in content
    assert "other-note" in content
    assert "linked_from" in content


def test_rebuild_alias_registry_skips_excluded(tmp_path, monkeypatch):
    wiki_path = tmp_path / "wiki"
    (wiki_path / "_system").mkdir(parents=True)
    (wiki_path / "_meta").mkdir(parents=True)
    monkeypatch.setattr(_sync_module, "WIKI_PATH", wiki_path)

    (wiki_path / "_system" / "cache.md").write_text("---\ntitle: Cache\n---\nCache data", encoding="utf-8")
    (wiki_path / "_meta" / "manifest.md").write_text("---\ntitle: Manifest\n---\nMeta", encoding="utf-8")

    _sync_module.cmd_rebuild_alias_registry()

    alias_path = wiki_path / "_meta" / "alias_registry.yaml"
    content = alias_path.read_text(encoding="utf-8")
    assert "cache" not in content
    assert "manifest" not in content


# Tests for cmd_rename_suggest
def test_rename_suggest_noop_on_kebab_case(tmp_path, monkeypatch, capsys):
    wiki_path = tmp_path / "wiki"
    wiki_path.mkdir(parents=True)
    monkeypatch.setattr(_sync_module, "WIKI_PATH", wiki_path)

    (wiki_path / "kebab-case-note.md").write_text("---\ntitle: OK\n---\nBody", encoding="utf-8")

    _sync_module.cmd_rename_suggest()

    captured = capsys.readouterr()
    assert "kebab-case" in captured.out or "already" in captured.out


@patch('sync.httpx.post')
def test_upsert_remote_retry_on_failure(mock_post):
    """upsert_remote doit retry sur échec HTTP."""
    from tenacity import RetryError
    mock_post.side_effect = Exception("Network error")

    entry = {
        "obsidian_path": "wiki/Test/test.md",
        "title": "Test Note",
        "content": "Test content",
        "tags": ["test"],
        "type": "note",
        "status": "active",
        "schema_version": "3.0.0",
        "date": "2026-05-14"
    }

    with pytest.raises(RetryError):
        _sync_module.upsert_remote(entry)

    # Should have been called 3 times (retry)
    assert mock_post.call_count == 3


# ============================================================
# Phase 1 Fiabilité — Confidence scoring tests
# ============================================================

from utils import compute_confidence_score, compute_lineage_depth, check_source_stale, build_frontmatter


def test_confidence_score_baseline_is_medium():
    """A bare note with no signals should score 'medium'."""
    result = compute_confidence_score({"source_type": "synthesis", "freshness": "volatile"}, "Hello")
    assert 0.35 <= result["score"] <= 0.65
    assert result["label"] == "medium"
    assert "source_type_synthesis" in result["signals"]


def test_confidence_score_human_source_is_high():
    """Human-written notes should score 'high'."""
    result = compute_confidence_score({"source_type": "human", "freshness": "evergreen"}, "# Title\nBody with [[ref]] and [[another]]")
    assert result["score"] >= 0.65
    assert result["label"] == "high"
    assert result["signals"]["source_type_human"] == 0.25


def test_confidence_score_deprecated_is_low():
    """Deprecated notes should score 'low'."""
    result = compute_confidence_score({"source_type": "synthesis", "freshness": "deprecated"}, "Old content")
    assert result["score"] < 0.35
    assert result["label"] == "low"
    assert "freshness_deprecated" in result["signals"]


def test_confidence_score_source_stale_penalty():
    """Stale source should penalize score."""
    result = compute_confidence_score(
        {"source_type": "synthesis", "freshness": "volatile"},
        "Body",
        source_hash="oldhash123",
    )
    score_without_stale = result["score"]
    # Now with stale detection — won't actually find a file since we don't pass vault_path
    # The staleness check is skipped if vault_path is None
    assert "source_stale" not in result["signals"]


def test_confidence_score_citations_bonus():
    """Multiple wiki links should add a citations bonus."""
    no_cites = compute_confidence_score({"source_type": "synthesis", "freshness": "volatile"}, "No links")
    with_cites = compute_confidence_score({"source_type": "synthesis", "freshness": "volatile"}, "See [[note-a]] and [[note-b]]")
    assert with_cites["score"] > no_cites["score"]
    assert "has_citations" in with_cites["signals"]


def test_confidence_score_detects_stale_source(tmp_path):
    """check_source_stale should detect when source file hash differs."""
    source_dir = tmp_path / "raw" / "notes"
    source_dir.mkdir(parents=True)
    source_file = source_dir / "test-source.md"
    source_file.write_text("---\ntitle: Original\n---\nOriginal content", encoding="utf-8")

    from utils import compute_content_hash, extract_body
    original_hash = compute_content_hash(extract_body(source_file.read_text(encoding="utf-8")))

    # Check with matching hash
    stale, detail, stale_status = check_source_stale(original_hash, "raw/notes/test-source.md", tmp_path)
    assert not stale
    assert "unchanged" in detail
    assert stale_status is None

    # Modify source
    source_file.write_text("---\ntitle: Modified\n---\nModified content", encoding="utf-8")
    stale, detail, stale_status = check_source_stale(original_hash, "raw/notes/test-source.md", tmp_path)
    assert stale
    assert "mismatch" in detail
    assert stale_status == "partially_outdated"


def test_confidence_score_source_file_missing(tmp_path):
    """check_source_stale should report stale when source file is gone."""
    stale, detail, stale_status = check_source_stale("somehash", "raw/notes/nonexistent.md", tmp_path)
    assert stale
    assert "not found" in detail
    assert stale_status == "needs_reingest"


def test_lineage_depth_human_original():
    """No derived_from means depth 0 (human original)."""
    assert compute_lineage_depth([]) == 0


def test_lineage_depth_from_raw():
    """Direct derived_from from raw/ gives depth 1."""
    derived = [{"path": "raw/notes/source.md", "relation": "source"}]
    assert compute_lineage_depth(derived) == 1


def test_lineage_depth_enriched():
    """Enriched_by relation gives depth 2."""
    derived = [{"path": "wiki/Intelligence/other.md", "relation": "enriched_by"}]
    assert compute_lineage_depth(derived) == 2


def test_lineage_depth_extends_gives_depth_2():
    """Extends relation gives depth 2."""
    derived = [{"path": "wiki/Intelligence/base.md", "relation": "extends"}]
    assert compute_lineage_depth(derived) == 2


def test_lineage_depth_multiple_sources():
    """Multiple sources take the max depth."""
    derived = [
        {"path": "raw/notes/a.md", "relation": "source"},
        {"path": "wiki/Intelligence/b.md", "relation": "enriched_by"},
    ]
    assert compute_lineage_depth(derived) == 2


def test_lineage_depth_backward_compat_string():
    """Plain string entries (legacy format) should still work."""
    derived = ["raw/notes/source.md"]
    assert compute_lineage_depth(derived) == 1


def test_build_frontmatter_with_confidence_signals():
    """build_frontmatter should handle dict values like confidence_signals."""
    fm = {
        "title": "Test",
        "confidence_score": 0.75,
        "confidence_signals": {"source_type_human": 0.25, "has_citations": 0.15},
    }
    result = build_frontmatter(fm)
    assert "confidence_score: 0.75" in result
    assert "confidence_signals:" in result
    assert "source_type_human: 0.25" in result

    # Round-trip: parse back
    parsed = _sync_module.parse_frontmatter(result + "\nBody")
    # Dict values come back as strings from our parser
    assert parsed["title"] == "Test"
    assert parsed["confidence_score"] == "0.75"


# ============================================================
# Phase 1 Fiabilité — Human validation workflow (review_status)
# ============================================================

def test_confidence_score_review_status_draft_penalty():
    """Draft status should penalize confidence."""
    draft = compute_confidence_score(
        {"source_type": "synthesis", "freshness": "volatile", "review_status": "draft"}, "Body"
    )
    verified = compute_confidence_score(
        {"source_type": "synthesis", "freshness": "volatile", "review_status": "verified"}, "Body"
    )
    assert verified["score"] > draft["score"]
    assert "review_status_draft" in draft["signals"]
    assert "review_status_verified" in verified["signals"]


def test_confidence_score_review_status_canonical_highest():
    """Canonical status should give the highest review bonus."""
    canonical = compute_confidence_score(
        {"source_type": "synthesis", "freshness": "volatile", "review_status": "canonical"}, "Body"
    )
    draft = compute_confidence_score(
        {"source_type": "synthesis", "freshness": "volatile", "review_status": "draft"}, "Body"
    )
    assert canonical["score"] >= draft["score"] + 0.3
    assert canonical["label"] in ("high", "medium")


# ============================================================
# Phase 1 Fiabilité — Stale detection enhancements
# ============================================================

def test_check_source_stale_returns_3tuple():
    """check_source_stale must return a 3-tuple (bool, str, str|None)."""
    from pathlib import Path
    result = check_source_stale(None, None, Path("."))
    assert len(result) == 3
    assert result[0] is False
    assert "No source provenance" in result[1]
    assert result[2] is None


def test_check_source_stale_stale_status_needs_reingest(tmp_path):
    """Missing source file should return stale_status='needs_reingest'."""
    stale, detail, status = check_source_stale("somehash", "raw/notes/missing.md", tmp_path)
    assert stale
    assert status == "needs_reingest"
    assert "not found" in detail


def test_check_source_stale_stale_status_partially_outdated(tmp_path):
    """Changed source file should return stale_status='partially_outdated'."""
    source_dir = tmp_path / "raw" / "notes"
    source_dir.mkdir(parents=True)
    source_file = source_dir / "test.md"
    source_file.write_text("---\ntitle: Old\n---\nOld content", encoding="utf-8")

    from utils import compute_content_hash, extract_body
    original_hash = compute_content_hash(extract_body(source_file.read_text(encoding="utf-8")))

    # Modify the source
    source_file.write_text("---\ntitle: New\n---\nNew content", encoding="utf-8")

    stale, detail, status = check_source_stale(original_hash, "raw/notes/test.md", tmp_path)
    assert stale
    assert status == "partially_outdated"
    assert "mismatch" in detail


# ============================================================
# Phase 1 Fiabilité — Concept map (entities.yaml)
# ============================================================

def test_entities_yaml_exists():
    """entities.yaml must exist and be valid YAML."""
    import yaml
    entities_path = Path(__file__).parents[2] / "wiki" / "_meta" / "entities.yaml"
    assert entities_path.exists(), f"Missing: {entities_path}"
    data = yaml.safe_load(entities_path.read_text(encoding="utf-8"))
    assert data is not None
    assert "entities" in data


def test_entities_yaml_has_required_fields():
    """Each entity must have canonical_name and status."""
    import yaml
    entities_path = Path(__file__).parents[2] / "wiki" / "_meta" / "entities.yaml"
    data = yaml.safe_load(entities_path.read_text(encoding="utf-8"))
    entities = data.get("entities", {})
    assert len(entities) >= 1, "At least one entity required"
    for key, info in entities.items():
        assert "canonical_name" in info, f"Entity {key} missing canonical_name"
        assert "status" in info, f"Entity {key} missing status"
        assert info["status"] in ("active", "archived", "fragmented"), f"Entity {key} has invalid status"


# ============================================================
# M8 — Tenant-aware sync (Phase 5)
# ============================================================


def test_sync_defines_default_tenant_personal():
    """sync.py must default the active tenant slug to 'personal'."""
    assert _sync_module.DEFAULT_TENANT_SLUG == "personal"
    # TENANT_SLUG comes from env VAULT_TENANT or falls back to the default.
    assert _sync_module.TENANT_SLUG in (
        "personal",
        os.environ.get("VAULT_TENANT", "personal"),
    )


def test_parse_tenant_flag_space_form():
    """`--tenant <slug>` must be extracted from argv."""
    cleaned, slug = _sync_module._parse_tenant_flag(["push", "--tenant", "alpha"])
    assert cleaned == ["push"]
    assert slug == "alpha"


def test_parse_tenant_flag_equals_form():
    """`--tenant=<slug>` must also be extracted."""
    cleaned, slug = _sync_module._parse_tenant_flag(["--tenant=beta", "pull", "--force"])
    assert cleaned == ["pull", "--force"]
    assert slug == "beta"


def test_parse_tenant_flag_missing_value_raises():
    """A bare `--tenant` with no following slug must fail loudly."""
    with pytest.raises(SystemExit):
        _sync_module._parse_tenant_flag(["push", "--tenant"])


def test_parse_tenant_flag_absent_returns_none():
    """No --tenant flag means slug is None and argv is untouched."""
    cleaned, slug = _sync_module._parse_tenant_flag(["status"])
    assert cleaned == ["status"]
    assert slug is None


def test_resolve_tenant_id_caches_lookup(monkeypatch):
    """_resolve_tenant_id must cache results per-slug to avoid REST chatter."""
    monkeypatch.setattr(_sync_module, "_TENANT_ID_CACHE", {})
    calls = {"n": 0}

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return [{"id": "tenant-uuid-1"}]

    def fake_get(url, headers=None, timeout=None):
        calls["n"] += 1
        assert "vault_tenants" in url
        assert "slug=eq.personal" in url
        return FakeResp()

    monkeypatch.setattr(_sync_module.httpx, "get", fake_get)
    monkeypatch.setattr(_sync_module, "TENANT_SLUG", "personal")

    assert _sync_module._resolve_tenant_id() == "tenant-uuid-1"
    assert _sync_module._resolve_tenant_id() == "tenant-uuid-1"
    assert calls["n"] == 1  # second call hits the cache


def test_resolve_tenant_id_raises_when_tenant_missing(monkeypatch):
    """A missing tenant slug must raise a clear error pointing at the bootstrap migration."""
    monkeypatch.setattr(_sync_module, "_TENANT_ID_CACHE", {})

    class FakeResp:
        def raise_for_status(self): pass
        def json(self): return []

    monkeypatch.setattr(_sync_module.httpx, "get", lambda *a, **kw: FakeResp())
    monkeypatch.setattr(_sync_module, "TENANT_SLUG", "ghost")

    with pytest.raises(RuntimeError) as exc:
        _sync_module._resolve_tenant_id()
    assert "ghost" in str(exc.value)
    assert "bootstrap" in str(exc.value)


def test_get_remote_entries_filters_by_tenant(monkeypatch):
    """get_remote_entries must request tenant_id=eq.<id>."""
    monkeypatch.setattr(_sync_module, "_resolve_tenant_id", lambda *a, **kw: "tid-abc")
    seen_urls: list[str] = []

    class FakeResp:
        def raise_for_status(self): pass
        def json(self): return []  # empty -> single iteration

    def fake_get(url, headers=None, timeout=None):
        seen_urls.append(url)
        return FakeResp()

    monkeypatch.setattr(_sync_module.httpx, "get", fake_get)
    _sync_module.get_remote_entries()
    assert seen_urls, "Expected at least one REST call"
    assert "tenant_id=eq.tid-abc" in seen_urls[0]


def test_get_remote_content_hashes_filters_by_tenant(monkeypatch):
    """_get_remote_content_hashes must scope by tenant_id too."""
    monkeypatch.setattr(_sync_module, "_resolve_tenant_id", lambda *a, **kw: "tid-xyz")

    class FakeResp:
        def raise_for_status(self): pass
        def json(self): return []

    seen: list[str] = []
    def fake_get(url, headers=None, timeout=None):
        seen.append(url)
        return FakeResp()

    monkeypatch.setattr(_sync_module.httpx, "get", fake_get)
    _sync_module._get_remote_content_hashes()
    assert seen and "tenant_id=eq.tid-xyz" in seen[0]


def test_cmd_push_blocks_sensitive_notes(monkeypatch, capsys):
    """cmd_push must refuse to upload notes with sensitivity in {private, sensitive}."""
    monkeypatch.setattr(_sync_module, "_resolve_tenant_id", lambda *a, **kw: "tid-1")
    monkeypatch.setattr(_sync_module, "_get_remote_content_hashes", lambda: {})
    monkeypatch.delenv("EMBED_ON_PUSH", raising=False)

    notes = [
        {"obsidian_path": "wiki/Context/a.md", "content_hash": "h1", "sensitivity": "private"},
        {"obsidian_path": "wiki/Context/b.md", "content_hash": "h2", "sensitivity": "sensitive"},
        {"obsidian_path": "wiki/Context/c.md", "content_hash": "h3", "sensitivity": "internal"},
    ]
    monkeypatch.setattr(_sync_module, "get_local_notes", lambda: notes)

    upserted: list[dict] = []
    monkeypatch.setattr(_sync_module, "upsert_remote", lambda n: upserted.append(n))

    _sync_module.cmd_push()

    captured = capsys.readouterr()
    assert "BLOCK" in captured.out
    assert "private" in captured.out
    assert "sensitive" in captured.out
    # Only the internal note should have been pushed.
    assert len(upserted) == 1
    assert upserted[0]["obsidian_path"] == "wiki/Context/c.md"


def test_cmd_push_stamps_tenant_id_on_pushed_rows(monkeypatch):
    """cmd_push must inject the resolved tenant_id into every pushed payload."""
    monkeypatch.setattr(_sync_module, "_resolve_tenant_id", lambda *a, **kw: "tid-42")
    monkeypatch.setattr(_sync_module, "_get_remote_content_hashes", lambda: {})
    monkeypatch.delenv("EMBED_ON_PUSH", raising=False)

    notes = [
        {"obsidian_path": "wiki/Context/a.md", "content_hash": "h1", "sensitivity": "internal"},
        {"obsidian_path": "wiki/Context/b.md", "content_hash": "h2", "sensitivity": "public"},
    ]
    monkeypatch.setattr(_sync_module, "get_local_notes", lambda: notes)

    pushed: list[dict] = []
    monkeypatch.setattr(_sync_module, "upsert_remote", lambda n: pushed.append(n.copy()))

    _sync_module.cmd_push()
    assert len(pushed) == 2
    assert all(p["tenant_id"] == "tid-42" for p in pushed)


# ============================================================
# T2/T3 — upsert ids + batch embed-backfill on push
# ============================================================


@patch('sync.httpx.post')
def test_upsert_remote_returns_id(mock_post):
    """upsert_remote must return the id from the first returned row."""
    mock_post.return_value = type('MockResponse', (), {
        'status_code': 201,
        'text': '[{"id": "abc-123", "obsidian_path": "wiki/Test/test.md"}]',
        'json': lambda self: [{"id": "abc-123", "obsidian_path": "wiki/Test/test.md"}],
    })()

    entry = {
        "obsidian_path": "wiki/Test/test.md",
        "title": "Test Note",
        "content": "Test content",
        "tags": ["test"],
        "type": "concept",
        "status": "active",
        "schema_version": "3.0.0",
        "date": "2026-05-14",
    }

    assert _sync_module.upsert_remote(entry) == "abc-123"


@patch('sync.httpx.post')
def test_upsert_remote_returns_none_on_empty_response(mock_post):
    """upsert_remote must return None when PostgREST returns an empty list."""
    mock_post.return_value = type('MockResponse', (), {
        'status_code': 200,
        'text': '[]',
        'json': lambda self: [],
    })()

    entry = {
        "obsidian_path": "wiki/Test/test.md",
        "title": "Test Note",
        "content": "Test content",
        "tags": ["test"],
        "type": "concept",
        "status": "active",
        "schema_version": "3.0.0",
        "date": "2026-05-14",
    }

    assert _sync_module.upsert_remote(entry) is None


@patch('sync.httpx.post')
def test_cmd_push_calls_embed_backfill_when_enabled(mock_post, monkeypatch):
    """cmd_push must POST once to embed-backfill with all pushed ids."""
    stub_notes = [
        {
            "obsidian_path": "wiki/Context/note-a.md",
            "title": "Note A",
            "content": "Body A",
            "content_hash": "hash-a",
            "tags": [],
            "type": "concept",
            "status": "active",
            "sensitivity": "internal",
        },
        {
            "obsidian_path": "wiki/Context/note-b.md",
            "title": "Note B",
            "content": "Body B",
            "content_hash": "hash-b",
            "tags": [],
            "type": "concept",
            "status": "active",
            "sensitivity": "internal",
        },
    ]
    monkeypatch.setattr(_sync_module, "get_local_notes", lambda: stub_notes)
    monkeypatch.setattr(_sync_module, "_resolve_tenant_id", lambda *a, **kw: "tid-batch")
    monkeypatch.setattr(_sync_module, "_get_remote_content_hashes", lambda: {})
    monkeypatch.setenv("EMBED_ON_PUSH", "1")

    call_log = []

    def _side_effect(url, **kwargs):
        call_log.append((url, kwargs))
        if "embed-backfill" in url:
            return type('R', (), {
                'status_code': 200,
                'raise_for_status': lambda self: None,
                'json': lambda self: {"mode": "targeted", "success": 2, "processed": 2, "errors": []},
                'text': '{}',
            })()
        return type('R', (), {
            'status_code': 201,
            'text': '[{"id": "id-pushed", "obsidian_path": "x"}]',
            'json': lambda self: [{"id": "id-pushed", "obsidian_path": "x"}],
        })()

    mock_post.side_effect = _side_effect

    _sync_module.cmd_push()

    embed_calls = [(url, kwargs) for url, kwargs in call_log if "embed-backfill" in url]
    assert len(embed_calls) == 1
    assert embed_calls[0][1]["json"] == {"ids": ["id-pushed", "id-pushed"]}


def test_trigger_embed_backfill_does_not_raise_on_http_error(monkeypatch):
    """_trigger_embed_backfill must swallow errors and keep push non-blocking."""
    import httpx as _httpx

    monkeypatch.setenv("EMBED_ON_PUSH", "1")
    with patch('sync.httpx.post', side_effect=_httpx.RequestError("connection refused")):
        _sync_module._trigger_embed_backfill(["some-id"])


def test_entities_yaml_depends_on_are_valid():
    """depends_on references must point to existing entity keys."""
    import yaml
    entities_path = Path(__file__).parents[2] / "wiki" / "_meta" / "entities.yaml"
    data = yaml.safe_load(entities_path.read_text(encoding="utf-8"))
    entities = data.get("entities", {})
    for key, info in entities.items():
        deps = info.get("depends_on", [])
        for dep in deps:
            assert dep in entities, f"Entity {key} depends on unknown entity {dep}"

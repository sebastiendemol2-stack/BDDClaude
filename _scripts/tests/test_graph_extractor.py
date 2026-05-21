import os
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from graph_extractor import (
    _load_local_entries,
    _should_extract,
    extract_relations,
    query_relations,
    _resolve_target_path,
    _confidence_score,
    cmd_status,
)


# -- _should_extract ----------------------------------------------------------

def test_should_extract_decision():
    assert _should_extract({"type": "decision", "confidence": "low"}) is True


def test_should_extract_high_confidence():
    assert _should_extract({"type": "concept", "confidence": "high"}) is True


def test_should_extract_low_confidence_not_decision():
    assert _should_extract({"type": "concept", "confidence": "low"}) is False


def test_should_extract_medium_confidence_not_decision():
    assert _should_extract({"type": "concept", "confidence": "medium"}) is False


# -- _resolve_target_path -----------------------------------------------------

def test_resolve_target_path_full():
    assert _resolve_target_path("wiki/Context/test.md", "wiki/index.md") == "wiki/Context/test.md"


def test_resolve_target_path_short():
    result = _resolve_target_path("other-note", "wiki/Context/note.md")
    assert result.endswith("other-note.md")


def test_resolve_target_path_with_slash():
    result = _resolve_target_path("Intelligence/decision", "wiki/index.md")
    assert result.endswith("Intelligence/decision.md")


# -- _confidence_score --------------------------------------------------------

def test_confidence_score_high():
    assert _confidence_score("high") == 0.8


def test_confidence_score_medium():
    assert _confidence_score("medium") == 0.5


def test_confidence_score_low():
    assert _confidence_score("low") == 0.2


def test_confidence_score_unknown():
    assert _confidence_score("unknown") == 0.5


# -- _load_local_entries ------------------------------------------------------

def test_load_local_entries_empty_dir(tmp_path):
    entries = _load_local_entries(str(tmp_path))
    assert entries == []


def test_load_local_entries_reads_frontmatter(tmp_path):
    wiki = tmp_path / "wiki"
    wiki.mkdir(parents=True)
    note = wiki / "test-note.md"
    note.write_text("""---
title: Test Note
type: concept
confidence: high
tags: [test]
links_to:
  - other-note
---

# Test Note

Content with [[another-note]] link.
""", encoding="utf-8")

    entries = _load_local_entries(str(wiki))
    assert len(entries) >= 1
    entry = [e for e in entries if e["title"] == "Test Note"][0]
    assert entry["type"] == "concept"
    assert entry["confidence"] == "high"
    assert "other-note" in entry["links_to"]
    assert "another-note" in entry["links_to"] or "another-note.md" in str(entry["links_to"])


def test_load_local_entries_skips_underscore_dirs(tmp_path):
    wiki = tmp_path / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "_system").mkdir()
    (wiki / "_system" / "internal.md").write_text("---\ntitle: Internal\n---\nbody")
    (wiki / "public.md").write_text("---\ntitle: Public\n---\nbody")

    entries = _load_local_entries(str(wiki))
    assert all("_system" not in e["obsidian_path"] for e in entries)
    assert any("public.md" in e["obsidian_path"] for e in entries)


def test_load_local_entries_no_frontmatter(tmp_path):
    wiki = tmp_path / "wiki"
    wiki.mkdir(parents=True)
    note = wiki / "bare.md"
    note.write_text("Just content without frontmatter", encoding="utf-8")

    entries = _load_local_entries(str(wiki))
    assert len(entries) == 1
    # Should still be loaded with defaults
    assert entries[0]["type"] == "concept"
    assert entries[0]["confidence"] == "medium"


# -- extract_relations (mockée) -----------------------------------------------

@patch("graph_extractor._rest")
@patch("graph_extractor._rest_vault")
def test_extract_relations_skips_low_confidence(mock_rest_vault, mock_rest):
    mock_vault_response = MagicMock()
    mock_vault_response.json.return_value = []
    mock_rest_vault.return_value = mock_vault_response
    mock_rest_response = MagicMock()
    mock_rest_response.json.return_value = []
    mock_rest.return_value = mock_rest_response

    count = extract_relations("tests/fixtures/nonexistent")
    assert count == 0


# -- query_relations ----------------------------------------------------------

@patch("graph_extractor._rest")
def test_query_relations_success(mock_rest):
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"source_entry_id": "wiki/a.md",
         "target_entry_id": "wiki/b.md",
         "relation_type": "references", "confidence": 0.8},
    ]
    mock_rest.return_value = mock_response

    results = query_relations("wiki/a.md")
    assert len(results) == 1
    assert results[0]["source_entry_id"] == "wiki/a.md"
    assert results[0]["target_entry_id"] == "wiki/b.md"
    assert results[0]["relation_type"] == "references"


@patch("graph_extractor._rest")
def test_query_relations_invalid_path(mock_rest):
    mock_response = MagicMock()
    mock_response.json.return_value = []
    mock_rest.return_value = mock_response
    results = query_relations("../../../etc/passwd")
    assert results == []


# -- cmd_status ---------------------------------------------------------------

@patch("graph_extractor._rest")
def test_cmd_status_runs(mock_rest):
    mock_response1 = MagicMock()
    mock_response1.json.return_value = [
        {"relation_type": "references", "count": 5},
        {"relation_type": "decides", "count": 2},
    ]
    mock_response2 = MagicMock()
    mock_response2.json.return_value = [{"source_entry_id": "a"}, {"source_entry_id": "b"}]

    mock_rest.side_effect = [mock_response1, mock_response2]
    cmd_status()
    assert mock_rest.call_count == 2

import os
import sys
import json
import math
import pytest
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from rag_bridge import (
    chunk_by_sections,
    _cosine_similarity,
    _load_wiki_chunks,
    _embed_text,
    _log_retrieval,
    retrieve,
    _fallback_bm25,
    format_context,
)


# -- chunk_by_sections -------------------------------------------------------

def test_chunk_by_sections_basic():
    text = """---
title: Test
---

# Title

## Section One

Content A.

## Section Two

Content B.
"""
    chunks = chunk_by_sections(text)
    assert len(chunks) >= 2
    assert chunks[0]["header"] == "Title" or chunks[0]["header"] == ""
    assert chunks[1]["header"] == "Section One"
    assert "Content A" in chunks[1]["content"]
    if len(chunks) > 2:
        assert chunks[2]["header"] == "Section Two"
        assert "Content B" in chunks[2]["content"]


def test_chunk_by_sections_empty():
    assert chunk_by_sections("") == []


def test_chunk_by_sections_no_sections():
    text = "Just a plain paragraph with no markdown headers."
    chunks = chunk_by_sections(text)
    assert len(chunks) == 1
    assert chunks[0]["header"] == ""
    assert "paragraph" in chunks[0]["content"]


def test_chunk_by_sections_only_frontmatter():
    text = "---\ntitle: Empty\n---"
    chunks = chunk_by_sections(text)
    assert chunks == []


def test_chunk_by_sections_estimates_tokens():
    text = "## Header\n" + "word " * 100
    chunks = chunk_by_sections(text)
    assert chunks[0]["token_estimate"] > 0
    assert len(chunks) == 1


def test_chunk_by_sections_deep_headers():
    text = "## Level 2\n\n### Level 3\n\n#### Level 4"
    chunks = chunk_by_sections(text)
    assert len(chunks) == 1
    assert "Level 2" in chunks[0]["content"]
    assert "Level 3" in chunks[0]["content"]


# -- _cosine_similarity ------------------------------------------------------

def test_cosine_similarity_identical():
    v = [1.0, 2.0, 3.0]
    assert _cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal():
    assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_zero_vector():
    assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0
    assert _cosine_similarity([1.0, 0.0], [0.0, 0.0]) == 0.0


def test_cosine_similarity_partial():
    a = [1.0, 0.0]
    b = [0.5, 0.5]
    sim = _cosine_similarity(a, b)
    assert 0.5 < sim < 1.0


# -- _load_wiki_chunks -------------------------------------------------------

def test_load_wiki_chunks_empty_dir(tmp_path):
    result = _load_wiki_chunks(tmp_path)
    assert result == []


def test_load_wiki_chunks_skips_underscore_dirs(tmp_path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "_system").mkdir()
    (wiki / "_system" / "private.md").write_text("## Secret\nhidden", encoding="utf-8")
    (wiki / "public.md").write_text("## Visible\ncontent", encoding="utf-8")

    chunks = _load_wiki_chunks(tmp_path)
    assert all("_system" not in c["path"] for c in chunks)
    assert any("public.md" in c["file"] for c in chunks)
    assert len(chunks) == 1


def test_load_wiki_chunks_returns_path_header(tmp_path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "test.md").write_text("## My Header\ndata", encoding="utf-8")

    chunks = _load_wiki_chunks(tmp_path)
    assert len(chunks) == 1
    assert chunks[0]["header"] == "My Header"
    assert chunks[0]["path"] == "wiki/test.md"


# -- _embed_text (mocké) -----------------------------------------------------

@patch("rag_bridge.httpx.Client")
def test_embed_text_success(MockClient):
    mock_instance = MagicMock()
    MockClient.return_value.__enter__.return_value = mock_instance
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [{"embedding": [0.1, 0.2, 0.3], "index": 0}]
    }
    mock_response.raise_for_status = MagicMock()
    mock_instance.post.return_value = mock_response

    result = _embed_text("hello")
    assert result == [0.1, 0.2, 0.3]


@patch("rag_bridge.httpx.Client")
def test_embed_text_timeout(MockClient):
    mock_instance = MagicMock()
    MockClient.return_value.__enter__.return_value = mock_instance
    mock_instance.post.side_effect = Exception("Connection refused")

    result = _embed_text("hello")
    assert result is None


# -- _log_retrieval ----------------------------------------------------------

def test_log_retrieval_writes_file(tmp_path):
    results = [
        {"path": "wiki/test.md", "score": 0.95, "header": "Test"}
    ]
    _log_retrieval("my query", results, 42.5, False, tmp_path)

    log_dir = tmp_path / "wiki" / "_system" / "logs"
    assert log_dir.exists()

    log_files = list(log_dir.glob("rag_*.jsonl"))
    assert len(log_files) == 1

    line = log_files[0].read_text(encoding="utf-8").strip()
    entry = json.loads(line)
    assert entry["query"] == "my query"
    assert entry["top_k"] == 1
    assert entry["latency_ms"] == 42.5
    assert entry["fallback"] is False
    assert entry["results"][0]["path"] == "wiki/test.md"
    assert entry["results"][0]["score"] == 0.95


def test_log_retrieval_fallback_flag(tmp_path):
    _log_retrieval("q", [], 0.0, True, tmp_path)
    log_dir = tmp_path / "wiki" / "_system" / "logs"
    line = list(log_dir.glob("rag_*.jsonl"))[0].read_text(encoding="utf-8")
    assert json.loads(line)["fallback"] is True


def test_log_retrieval_multiple_calls_append(tmp_path):
    _log_retrieval("q1", [], 10.0, False, tmp_path)
    _log_retrieval("q2", [], 20.0, False, tmp_path)

    log_dir = tmp_path / "wiki" / "_system" / "logs"
    lines = list(log_dir.glob("rag_*.jsonl"))[0].read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2


# -- _fallback_bm25 ----------------------------------------------------------

def test_fallback_bm25_returns_results():
    chunks = [
        {"header": "A", "content": "machine learning concepts", "path": "a.md"},
        {"header": "B", "content": "cooking recipes", "path": "b.md"},
        {"header": "C", "content": "deep learning and neural networks", "path": "c.md"},
    ]
    results = _fallback_bm25("learning machine", chunks, 2, Path("."))
    assert len(results) >= 1
    assert any("a.md" in r["path"] for r in results)


def test_fallback_bm25_no_match():
    chunks = [{"header": "A", "content": "cooking", "path": "a.md"}]
    results = _fallback_bm25("quantum physics", chunks, 5, Path("."))
    assert results == []


# -- retrieve (intégration mockée) -------------------------------------------

@patch("rag_bridge._embed_text")
@patch("rag_bridge._load_wiki_chunks")
def test_retrieve_with_mocked_embeddings(mock_load, mock_embed):
    mock_load.return_value = [
        {"path": "wiki/a.md", "header": "A", "content": "hello world", "file": "a.md",
         "token_estimate": 3},
        {"path": "wiki/b.md", "header": "B", "content": "goodbye world", "file": "b.md",
         "token_estimate": 3},
    ]
    mock_embed.side_effect = [
        [1.0, 0.0],
        [1.0, 0.0],
        [0.5, 0.5],
    ]

    results = retrieve("hello", top_k=2, vault_path=Path("."))
    assert len(results) == 2
    assert results[0]["score"] > results[1]["score"]


@patch("rag_bridge._embed_text")
@patch("rag_bridge._load_wiki_chunks")
def test_retrieve_returns_empty_on_no_chunks(mock_load, mock_embed):
    mock_load.return_value = []
    results = retrieve("anything", vault_path=Path("."))
    assert results == []


# -- format_context -----------------------------------------------------------

def test_format_context_basic():
    results = [
        {"path": "wiki/a.md", "header": "Section A", "content": "Content A", "score": 0.95},
        {"path": "wiki/b.md", "header": "Section B", "content": "Content B", "score": 0.80},
    ]
    block = format_context(results, max_results=3, max_tokens=512)
    assert block["role"] == "context"
    assert len(block["content"]) == 2
    assert block["content"][0]["source"] == "wiki/a.md"
    assert block["content"][0]["section"] == "Section A"
    assert block["content"][0]["score"] == 0.95
    assert "Content A" in block["content"][0]["content"]


def test_format_context_limits_results():
    results = [{"path": f"wiki/{i}.md", "header": f"S{i}", "content": "x", "score": 1.0}
               for i in range(10)]
    block = format_context(results, max_results=3, max_tokens=512)
    assert len(block["content"]) == 3


def test_format_context_truncates_tokens():
    long_content = "word " * 2000
    results = [{"path": "wiki/a.md", "header": "A", "content": long_content, "score": 0.9}]
    block = format_context(results, max_results=1, max_tokens=16)
    assert len(block["content"][0]["content"]) < len(long_content)


def test_format_context_empty():
    block = format_context([], max_results=3, max_tokens=512)
    assert block == {"role": "context", "content": []}


def test_format_context_rounds_score():
    results = [{"path": "wiki/a.md", "header": "A", "content": "x", "score": 0.94444}]
    block = format_context(results)
    assert block["content"][0]["score"] == 0.9444

import os
import sys
import json
import math
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from memory_store import (
    _cosine_similarity,
    _embed_text,
    store_session,
    search_sessions,
    format_session_context,
    _validate_session_input,
    _safe_json_load,
)


# -- _cosine_similarity -------------------------------------------------------

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


# -- _embed_text (mocké) -----------------------------------------------------

@patch("memory_store.httpx.Client")
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


@patch("memory_store.httpx.Client")
def test_embed_text_timeout(MockClient):
    mock_instance = MagicMock()
    MockClient.return_value.__enter__.return_value = mock_instance
    mock_instance.post.side_effect = Exception("Connection refused")

    result = _embed_text("hello")
    assert result is None


# -- _validate_session_input --------------------------------------------------

def test_validate_session_input_valid():
    sid = "550e8400-e29b-41d4-a716-446655440000"
    result = _validate_session_input(sid, "summary content", [{"key": "a"}], [{"key": "b"}])
    assert result[0] == sid
    assert "summary" in result[1]
    assert len(result[2]) == 1
    assert len(result[3]) == 1


def test_validate_session_input_invalid_uuid():
    with pytest.raises(ValueError):
        _validate_session_input("not-a-uuid")


def test_validate_session_input_truncates():
    sid = "550e8400-e29b-41d4-a716-446655440000"
    long_summary = "x" * 2000
    long_decisions = [{"key": f"k{i}", "value": "v"} for i in range(50)]
    result = _validate_session_input(sid, long_summary, long_decisions)
    assert len(result[1]) <= 1000
    assert len(result[2]) <= 20


# -- store_session (mocké) ----------------------------------------------------

@patch("memory_store._rest")
@patch("memory_store._embed_text")
def test_store_session_success(mock_embed, mock_rest):
    mock_embed.return_value = [0.1, 0.2, 0.3]
    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": "mem-1", "session_id": "550e8400-e29b-41d4-a716-446655440000"}]
    mock_rest.return_value = mock_response

    result = store_session(
        "550e8400-e29b-41d4-a716-446655440000",
        "Test session",
        [{"key": "choice", "value": "A"}],
        [],
        "test-project"
    )
    assert result is not None
    assert result["id"] == "mem-1"


@patch("memory_store._rest")
@patch("memory_store._embed_text")
def test_store_session_no_embedding(mock_embed, mock_rest):
    mock_embed.return_value = None
    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": "mem-2"}]
    mock_rest.return_value = mock_response

    result = store_session(
        "550e8400-e29b-41d4-a716-446655440000",
        "No embedding session"
    )
    assert result is not None


@patch("memory_store._rest")
def test_store_session_invalid_uuid(mock_rest):
    result = store_session("bad-uuid")
    assert result is None
    mock_rest.assert_not_called()


# -- format_session_context ---------------------------------------------------

def test_format_session_context_basic():
    results = [
        {"session_id": "abc", "summary": "Good session", "decisions": [], "patterns": [], "score": 0.95},
        {"session_id": "def", "summary": "Another session", "decisions": [{"key": "x", "value": "y"}],
         "patterns": [], "score": 0.80},
    ]
    block = format_session_context(results, max_results=3, max_tokens=512)
    assert block["role"] == "context"
    assert len(block["content"]) == 2
    assert "Good session" in block["content"][0]["content"]
    assert "x=y" in block["content"][1]["content"]


def test_format_session_context_limits_results():
    results = [{"session_id": f"s{i}", "summary": "x", "decisions": [], "patterns": [], "score": 1.0}
               for i in range(10)]
    block = format_session_context(results, max_results=3, max_tokens=512)
    assert len(block["content"]) == 3


def test_format_session_context_empty():
    assert format_session_context([], max_results=3) == {"role": "context", "content": []}


def test_format_session_context_with_patterns():
    results = [
        {"session_id": "s1", "summary": "Session with patterns",
         "decisions": [], "patterns": [{"key": "review", "value": "always"}], "score": 0.9},
    ]
    block = format_session_context(results)
    assert "review=always" in block["content"][0]["content"]


def test_format_session_context_empty_summary():
    results = [
        {"session_id": "s1", "summary": "", "decisions": [], "patterns": [], "score": 0.5},
    ]
    block = format_session_context(results)
    assert block["content"][0]["content"] == ""


# -- _safe_json_load ----------------------------------------------------------

def test_safe_json_load_from_string():
    assert _safe_json_load('[{"key":"a"}]') == [{"key": "a"}]


def test_safe_json_load_from_list():
    assert _safe_json_load([1, 2, 3]) == [1, 2, 3]


def test_safe_json_load_invalid():
    assert _safe_json_load("not json") == []


def test_safe_json_load_none():
    assert _safe_json_load(None) == []


# -- search_sessions (mocké) --------------------------------------------------

@patch("memory_store._embed_text")
@patch("memory_store._rest")
def test_search_sessions_fallback_text_search(mock_rest, mock_embed):
    mock_embed.return_value = None
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"session_id": "s1", "summary": "machine learning session", "decisions": "[]", "patterns": "[]",
         "created_at": "2026-05-20T10:00:00"},
    ]
    mock_rest.return_value = mock_response

    results = search_sessions("learning", top_k=5)
    assert len(results) >= 1
    assert results[0]["session_id"] == "s1"

import os
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from feedback_pipeline import (
    collect_feedback,
    validate_feedback,
    promote_memory,
    cmd_status,
    _normalize_content,
    _slugify,
    PROMOTION_THRESHOLD,
)


# -- _normalize_content -------------------------------------------------------

def test_normalize_content_strips_case():
    assert _normalize_content("  Hello World  ") == "hello world"


def test_normalize_content_truncates():
    long_text = "a" * 500
    assert len(_normalize_content(long_text)) <= 200


# -- _slugify -----------------------------------------------------------------

def test_slugify_basic():
    assert _slugify("Hello World!") == "hello-world"


def test_slugify_special_chars():
    assert _slugify("What is the best approach? #3") == "what-is-the-best-approach-3"


def test_slugify_truncates():
    long_text = "a" * 100
    assert len(_slugify(long_text)) <= 50


# -- collect_feedback ---------------------------------------------------------

@patch("feedback_pipeline._rest")
def test_collect_feedback_new(mock_rest):
    mock_rest.side_effect = [
        MagicMock(json=lambda: []),  # GET existing -> empty
        MagicMock(json=lambda: [{"id": "fb-1", "status": "raw_feedback", "occurrences": 1}]),  # POST
    ]

    result = collect_feedback(
        "550e8400-e29b-41d4-a716-446655440000",
        "Great answer",
        True,
        source="jan"
    )
    assert result is not None
    assert result["id"] == "fb-1"


@patch("feedback_pipeline._rest")
def test_collect_feedback_increments(mock_rest):
    existing = [
        {"id": "fb-2", "content": "Great answer", "positive": True, "occurrences": 2,
         "status": "raw_feedback"}
    ]
    mock_response = MagicMock()
    mock_response.json.return_value = existing
    mock_rest.side_effect = [
        mock_response,  # GET existing
        MagicMock(json=lambda: [{"id": "fb-2", "occurrences": 3, "status": "validated_precedent"}]),  # PATCH
    ]

    result = collect_feedback(
        "550e8400-e29b-41d4-a716-446655440000",
        "Great answer",
        True
    )
    assert result is not None
    assert result["occurrences"] == 3
    assert result["status"] == "validated_precedent"


@patch("feedback_pipeline._rest")
def test_collect_feedback_different_content_no_increment(mock_rest):
    existing = [
        {"id": "fb-3", "content": "Different answer", "positive": True, "occurrences": 2,
         "status": "raw_feedback"}
    ]
    mock_response = MagicMock()
    mock_response.json.return_value = existing
    mock_rest.side_effect = [
        mock_response,  # GET
        MagicMock(json=lambda: [{"id": "fb-4", "status": "raw_feedback", "occurrences": 1}]),  # POST
    ]

    result = collect_feedback(
        "550e8400-e29b-41d4-a716-446655440000",
        "Totally different feedback",
        True
    )
    assert result is not None
    assert result["id"] == "fb-4"


@patch("feedback_pipeline._rest")
def test_collect_feedback_invalid_event_id(mock_rest):
    result = collect_feedback("not-a-uuid", "content", True)
    assert result is None
    mock_rest.assert_not_called()


# -- validate_feedback --------------------------------------------------------

@patch("feedback_pipeline._rest")
def test_validate_feedback_promotes(mock_rest):
    mock_rest.side_effect = [
        MagicMock(json=lambda: [
            {"id": "fb-5", "occurrences": 3, "status": "raw_feedback"},
            {"id": "fb-6", "occurrences": 4, "status": "raw_feedback"},
        ]),
        MagicMock(json=lambda: [{"id": "fb-5"}]),
        MagicMock(json=lambda: [{"id": "fb-6"}]),
    ]

    count = validate_feedback(threshold=3)
    assert count == 2


@patch("feedback_pipeline._rest")
def test_validate_feedback_below_threshold(mock_rest):
    mock_response = MagicMock()
    mock_response.json.return_value = []
    mock_rest.return_value = mock_response

    count = validate_feedback(threshold=5)
    assert count == 0


@patch("feedback_pipeline._rest")
def test_validate_feedback_network_error(mock_rest):
    mock_rest.side_effect = Exception("DB error")
    count = validate_feedback()
    assert count == 0


# -- promote_memory -----------------------------------------------------------

@patch("feedback_pipeline._rest")
def test_promote_memory_success(mock_rest):
    mock_rest.side_effect = [
        MagicMock(json=lambda: [
            {"id": "fb-7", "content": "Always run tests before merge", "positive": True,
             "occurrences": 5, "source": "feedback-pipeline"},
        ]),
        MagicMock(json=lambda: [{"id": "mem-1"}]),
        MagicMock(json=lambda: [{"id": "fb-7"}]),
    ]

    count = promote_memory(
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001",
        max_promote=10
    )
    assert count == 1


@patch("feedback_pipeline._rest")
def test_promote_memory_empty_feedback(mock_rest):
    mock_response = MagicMock()
    mock_response.json.return_value = []
    mock_rest.return_value = mock_response

    count = promote_memory(
        "550e8400-e29b-41d4-a716-446655440000",
        "660e8400-e29b-41d4-a716-446655440001"
    )
    assert count == 0


@patch("feedback_pipeline._rest")
def test_promote_memory_invalid_ids(mock_rest):
    count = promote_memory("bad-id", "bad-id")
    assert count == 0
    mock_rest.assert_not_called()


# -- cmd_status ---------------------------------------------------------------

@patch("feedback_pipeline._rest")
def test_cmd_status_runs(mock_rest):
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"status": "raw_feedback", "count": 5},
        {"status": "validated_precedent", "count": 3},
        {"status": "promoted_memory", "count": 10},
    ]
    mock_rest.return_value = mock_response

    cmd_status()
    assert mock_rest.called


# -- PROMOTION_THRESHOLD ------------------------------------------------------

def test_promotion_threshold():
    assert PROMOTION_THRESHOLD == 3

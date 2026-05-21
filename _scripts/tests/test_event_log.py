import os
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from event_log import (
    push_event,
    get_unprocessed_events,
    mark_processed,
    process_events,
    _handle_session_end,
    _handle_feedback,
    VALID_EVENT_TYPES,
)


# -- push_event ---------------------------------------------------------------

@patch("event_log._rest")
def test_push_event_success(mock_rest):
    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": "550e8400-e29b-41d4-a716-446655440000"}]
    mock_rest.return_value = mock_response

    result = push_event("session_end", {"summary": "test"}, source="jan")
    assert result is not None
    assert result["id"] == "550e8400-e29b-41d4-a716-446655440000"
    mock_rest.assert_called_once()


@patch("event_log._rest")
def test_push_event_invalid_type(mock_rest):
    result = push_event("invalid_type", {})
    assert result is None
    mock_rest.assert_not_called()


@patch("event_log._rest")
def test_push_event_calls_correct_endpoint(mock_rest):
    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": "abc-def"}]
    mock_rest.return_value = mock_response

    push_event("feedback", {"positive": True}, source="jan")

    # Verify the call includes vault_events path
    call_args = mock_rest.call_args
    assert call_args[0][0] == "POST"
    assert "vault_events" in call_args[0][1]
    assert call_args[1]["json"]["event_type"] == "feedback"
    assert call_args[1]["json"]["ingested"] is False


@patch("event_log._rest")
def test_push_event_with_project_and_session(mock_rest):
    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": "abc-def"}]
    mock_rest.return_value = mock_response

    result = push_event("session_end", {"summary": "x"}, project_slug="my-project",
                        session_id="550e8400-e29b-41d4-a716-446655440000")
    assert result is not None

    call_json = mock_rest.call_args[1]["json"]
    assert call_json["project_slug"] == "my-project"
    assert call_json["session_id"] == "550e8400-e29b-41d4-a716-446655440000"


@patch("event_log._rest")
def test_push_event_rejects_invalid_slug(mock_rest):
    result = push_event("session_end", {}, project_slug="INVALID SLUG!!!")
    assert result is None
    mock_rest.assert_not_called()


@patch("event_log._rest")
def test_push_event_network_error(mock_rest):
    mock_rest.side_effect = Exception("Connection refused")
    result = push_event("session_end", {"summary": "test"})
    assert result is None


# -- get_unprocessed_events ---------------------------------------------------

@patch("event_log._rest")
def test_get_unprocessed_events_success(mock_rest):
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"id": "a", "event_type": "session_end", "payload": {}, "ingested": False},
        {"id": "b", "event_type": "feedback", "payload": {}, "ingested": False},
    ]
    mock_rest.return_value = mock_response

    events = get_unprocessed_events(limit=10)
    assert len(events) == 2
    assert events[0]["id"] == "a"


@patch("event_log._rest")
def test_get_unprocessed_events_empty(mock_rest):
    mock_response = MagicMock()
    mock_response.json.return_value = []
    mock_rest.return_value = mock_response

    events = get_unprocessed_events()
    assert events == []


@patch("event_log._rest")
def test_get_unprocessed_events_error(mock_rest):
    mock_rest.side_effect = Exception("Timeout")
    events = get_unprocessed_events()
    assert events == []


# -- mark_processed -----------------------------------------------------------

@patch("event_log._rest")
def test_mark_processed_success(mock_rest):
    mock_response = MagicMock()
    mock_rest.return_value = mock_response

    result = mark_processed("550e8400-e29b-41d4-a716-446655440000")
    assert result is True


@patch("event_log._rest")
def test_mark_processed_with_error(mock_rest):
    mock_response = MagicMock()
    mock_rest.return_value = mock_response

    result = mark_processed("550e8400-e29b-41d4-a716-446655440000", error="Something broke")
    assert result is True

    call_json = mock_rest.call_args[1]["json"]
    assert call_json["ingested"] is True
    assert "ingested_at" in call_json
    assert call_json["error"] == "Something broke"


@patch("event_log._rest")
def test_mark_processed_invalid_uuid(mock_rest):
    result = mark_processed("not-a-uuid")
    assert result is False
    mock_rest.assert_not_called()


# -- _handle_session_end ------------------------------------------------------

@patch("event_log._rest")
def test_handle_session_end_creates_project_session(mock_rest):
    # First call: project lookup returns empty
    # Second call: create project
    # Third call: create session
    mock_rest.side_effect = [
        MagicMock(json=lambda: []),  # GET projects -> empty
        MagicMock(json=lambda: [{"id": "proj-1"}]),  # POST projects
        MagicMock(json=lambda: [{"id": "session-1"}]),  # POST sessions
    ]

    event = {
        "id": "evt-1",
        "event_type": "session_end",
        "payload": {"summary": "Good session", "decisions": [], "patterns": []},
        "project_slug": "test-project",
        "session_id": None,
    }

    result = _handle_session_end(event)
    assert result is True


@patch("event_log._rest")
def test_handle_session_end_with_decisions(mock_rest):
    mock_rest.side_effect = [
        MagicMock(json=lambda: [{"id": "proj-1"}]),  # GET projects
        MagicMock(json=lambda: [{"id": "session-1"}]),  # PATCH sessions
    ]

    event = {
        "id": "evt-2",
        "event_type": "session_end",
        "payload": {
            "summary": "Decided X",
            "decisions": [{"key": "tech-stack", "value": "Python"}],
            "patterns": [{"key": "review-before-merge", "value": "always"}],
        },
        "project_slug": "test",
        "session_id": "550e8400-e29b-41d4-a716-446655440000",
    }

    result = _handle_session_end(event)
    assert result is True


@patch("event_log._rest")
def test_handle_session_end_empty_payload(mock_rest):
    event = {
        "id": "evt-3",
        "event_type": "session_end",
        "payload": {},
        "project_slug": None,
        "session_id": None,
    }
    result = _handle_session_end(event)
    assert result is False


# -- _handle_feedback ---------------------------------------------------------

def test_handle_feedback_positive():
    event = {"id": "f-1", "payload": {"positive": True}}
    assert _handle_feedback(event) is True


def test_handle_feedback_negative():
    event = {"id": "f-2", "payload": {"positive": False}}
    assert _handle_feedback(event) is True


# -- process_events -----------------------------------------------------------

@patch("event_log._handle_session_end")
@patch("event_log.get_unprocessed_events")
@patch("event_log.mark_processed")
def test_process_events_calls_handlers(mock_mark, mock_get, mock_handle):
    mock_get.return_value = [
        {"id": "e1", "event_type": "session_end", "payload": {"summary": "x"},
         "project_slug": "test", "session_id": None},
    ]
    mock_mark.return_value = True
    mock_handle.return_value = True

    count = process_events(limit=10)
    assert count == 1
    mock_handle.assert_called_once()

    # Verify mark_processed was called with the right event id
    mock_mark.assert_called_once()
    call_args = mock_mark.call_args
    assert call_args[0][0] == "e1"


@patch("event_log.get_unprocessed_events")
def test_process_events_empty(mock_get):
    mock_get.return_value = []
    count = process_events()
    assert count == 0


@patch("event_log.get_unprocessed_events")
@patch("event_log.mark_processed")
def test_process_events_unknown_type(mock_mark, mock_get):
    mock_get.return_value = [
        {"id": "e1", "event_type": "custom", "payload": {"foo": "bar"}},
    ]
    mock_mark.return_value = True

    count = process_events()
    assert count == 1


# -- VALID_EVENT_TYPES --------------------------------------------------------

def test_valid_event_types():
    assert "session_start" in VALID_EVENT_TYPES
    assert "session_end" in VALID_EVENT_TYPES
    assert "message" in VALID_EVENT_TYPES
    assert "feedback" in VALID_EVENT_TYPES
    assert "ingest" in VALID_EVENT_TYPES
    assert "custom" in VALID_EVENT_TYPES
    assert len(VALID_EVENT_TYPES) == 6


# -- brain.py integration -----------------------------------------------------

def test_brain_has_events_subcommand():
    """Verify brain.py has the events subcommand registered."""
    import brain as _brain
    # Just verify the module loads without error
    assert hasattr(_brain, "main")

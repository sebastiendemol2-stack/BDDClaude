# _scripts/tests/test_brain.py
import os
import sys
import pytest
from unittest.mock import patch, Mock
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils import _validate_uuid, _validate_slug, _truncate_by_section


def test_missing_env_var_gives_friendly_message(monkeypatch, capsys):
    """Lazy loading: import succeeds, _get_brain_url() échoue avec message clair."""
    monkeypatch.delenv("BRAIN_URL", raising=False)
    monkeypatch.delenv("BRAIN_SERVICE_KEY", raising=False)
    monkeypatch.delenv("VAULT_PATH", raising=False)

    # Remove module if already loaded
    if "brain" in sys.modules:
        del sys.modules["brain"]

    with patch("dotenv.load_dotenv"):
        import brain  # noqa: F401 — should succeed now with lazy loading

    # Calling the lazy getter should fail
    with pytest.raises(SystemExit) as exc_info:
        brain._get_brain_url()

    captured = capsys.readouterr()
    assert "BRAIN_URL" in captured.err
    assert ".env" in captured.err
    assert exc_info.value.code != 0


# Tests for UUID validation
def test_validate_uuid_accepts_valid():
    """_validate_uuid should accept valid UUID v4 format."""
    result = _validate_uuid("550e8400-e29b-41d4-a716-446655440000")
    assert result == "550e8400-e29b-41d4-a716-446655440000"


def test_validate_uuid_rejects_injection():
    """_validate_uuid should reject injection attempts."""
    with pytest.raises(ValueError):
        _validate_uuid("abc&select=password")


def test_validate_uuid_rejects_empty():
    """_validate_uuid should reject empty strings."""
    with pytest.raises(ValueError):
        _validate_uuid("")


def test_validate_uuid_rejects_plain_string():
    """_validate_uuid should reject non-UUID strings."""
    with pytest.raises(ValueError):
        _validate_uuid("not-a-uuid")


# Tests for slug validation
def test_validate_slug_accepts_valid():
    """_validate_slug should accept valid slug format."""
    result = _validate_slug("my-project-slug")
    assert result == "my-project-slug"


def test_validate_slug_rejects_uppercase():
    """_validate_slug should reject uppercase letters."""
    with pytest.raises(ValueError):
        _validate_slug("My-Project")


def test_validate_slug_rejects_special_chars():
    """_validate_slug should reject special characters."""
    with pytest.raises(ValueError):
        _validate_slug("my-project&evil")


def test_validate_slug_rejects_hyphen_only():
    """_validate_slug should reject hyphen only."""
    with pytest.raises(ValueError):
        _validate_slug("-")


# Tests for section-aware truncation
def test_truncation_keeps_full_content_if_fits():
    """Truncation should keep full content if it fits."""
    content = "# Title\n\n## A\nshort content"
    result = _truncate_by_section(content, 10000)
    assert result == content


def test_truncation_does_not_cut_mid_section():
    """Truncation should not cut in the middle of a section."""
    section_a = "## Section A\n" + "x" * 100
    section_b = "## Section B\n" + "y" * 100
    content = "# Title\n\n" + section_a + "\n\n" + section_b
    # Max chars large enough for title + section A, but not section B
    max_chars = len("# Title\n\n") + len(section_a) + 50
    result = _truncate_by_section(content, max_chars)
    # Section B should not appear in the result (was cut)
    assert "Section B" not in result
    # Truncation marker should be present
    assert "_[tronqué" in result


def test_truncation_marker_always_present_when_truncated():
    """Truncation marker should always be present when content is truncated."""
    content = "# Title\n\n## A\n" + "x" * 200
    result = _truncate_by_section(content, 50)
    assert "_[tronqué" in result


# Tests for _sanitize_message
def test_sanitize_message_jwt():
    from brain import _sanitize_message
    msg = "token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNrvP5FQwC1J3gC0.abcdef"
    result = _sanitize_message(msg)
    assert "[KEY_REDACTED]" in result
    assert "eyJ" not in result


def test_sanitize_message_openai_key():
    from brain import _sanitize_message
    msg = "api_key=sk-proj-abc123def456ghi789jkl012"
    result = _sanitize_message(msg)
    assert "[REDACTED]" in result
    assert "sk-proj" not in result


def test_sanitize_message_bearer():
    from brain import _sanitize_message
    msg = "Authorization: Bearer abcdefghijklmnopqrstuvwxyz1234567890"
    result = _sanitize_message(msg)
    assert "Bearer [KEY_REDACTED]" in result


def test_sanitize_message_generic_api_key():
    from brain import _sanitize_message
    msg = "api_key=abcdefghijklmnopqrstuvwxyz1234567890"
    result = _sanitize_message(msg)
    assert "[REDACTED]" in result


def test_sanitize_message_leaves_innocent_text():
    from brain import _sanitize_message
    msg = "normal log message without secrets"
    result = _sanitize_message(msg)
    assert result == msg


# Tests for _validate_working_dir
def test_validate_working_dir_accepts_valid(monkeypatch):
    import tempfile
    from pathlib import Path
    from brain import _validate_working_dir
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setattr("brain.VAULT_PATH", Path(tmp))
        assert _validate_working_dir(tmp) is True


def test_validate_working_dir_rejects_outside(monkeypatch):
    import tempfile
    from pathlib import Path
    from brain import _validate_working_dir
    with tempfile.TemporaryDirectory() as vault:
        with tempfile.TemporaryDirectory() as outside:
            monkeypatch.setattr("brain.VAULT_PATH", Path(vault))
            assert _validate_working_dir(outside) is False


def test_validate_working_dir_rejects_path_traversal(monkeypatch):
    import tempfile
    from pathlib import Path
    from brain import _validate_working_dir
    with tempfile.TemporaryDirectory() as vault:
        monkeypatch.setattr("brain.VAULT_PATH", Path(vault))
        assert _validate_working_dir(f"{vault}/../etc/passwd") is False


def test_load_generates_context_session_file_and_returns_zero(tmp_path, monkeypatch):
    import brain
    # Patch environment and dependencies to avoid real network calls.
    monkeypatch.setattr("brain.VAULT_PATH", tmp_path)
    monkeypatch.setattr("brain._validate_working_dir", lambda wd: True)
    monkeypatch.setattr("brain.load_project_config", lambda wd: {"slug": "test", "name": "test"})
    monkeypatch.setattr("brain.get_or_create_project", lambda cfg, wd: {"id": "550e8400-e29b-41d4-a716-446655440000"})
    monkeypatch.setattr("brain.get_or_resume_session", lambda project_id, wd: {"id": "550e8400-e29b-41d4-a716-446655440001", "started_at": "2026-05-21T00:00:00Z"})

    class DummyResponse:
        def __init__(self, data):
            self._data = data
        def json(self):
            return self._data

    # Simulate claude_memory responses for each memory type and session summary
    def fake_rest(method, path, **kwargs):
        if path.startswith("claude_memory"):
            return DummyResponse([])
        if path.startswith("sessions?"):
            return DummyResponse([])
        raise AssertionError(f"Unexpected REST call: {path}")

    monkeypatch.setattr("brain.rest", fake_rest)

    result = brain.load(str(tmp_path))
    assert result == 0
    expected_file = tmp_path / "wiki" / "Context" / "context-session.md"
    assert expected_file.exists()
    content = expected_file.read_text(encoding="utf-8")
    assert "# Project" in content
    assert "# Current Session" in content


# Tests for acquire_lock / release_lock
def test_acquire_lock_success(tmp_path):
    from brain import acquire_lock, release_lock
    assert acquire_lock(str(tmp_path)) is True
    assert (tmp_path / ".brain" / "save.lock").exists()
    release_lock(str(tmp_path))
    assert not (tmp_path / ".brain" / "save.lock").exists()


def test_acquire_lock_fails_if_held(tmp_path):
    from brain import acquire_lock
    assert acquire_lock(str(tmp_path)) is True
    assert acquire_lock(str(tmp_path)) is False


def test_acquire_lock_stale_lock_removed(tmp_path, monkeypatch):
    from brain import acquire_lock, release_lock
    import json
    from datetime import datetime, timezone, timedelta

    brain_dir = tmp_path / ".brain"
    brain_dir.mkdir(parents=True, exist_ok=True)
    lock_path = brain_dir / "save.lock"
    stale_data = json.dumps({
        "pid": 99999,
        "created_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    })
    lock_path.write_text(stale_data, encoding="utf-8")

    monkeypatch.setattr("brain.LOCK_STALE_SECONDS", 300)
    assert acquire_lock(str(tmp_path)) is True
    release_lock(str(tmp_path))


# Tests for _strip_bom
def test_strip_bom_removes_utf8_bom():
    from utils import _strip_bom
    content = "\ufeff---\ntitle: Test\n---\nBody"
    result = _strip_bom(content)
    assert result == "---\ntitle: Test\n---\nBody"
    assert not result.startswith("\ufeff")


def test_strip_bom_no_bom():
    from utils import _strip_bom
    content = "---\ntitle: Test\n---\nBody"
    result = _strip_bom(content)
    assert result == content


def test_strip_bom_empty():
    from utils import _strip_bom
    assert _strip_bom("") == ""


# Tests for extract_body
def test_extract_body_removes_frontmatter():
    from utils import extract_body
    content = "---\ntitle: Test\n---\nBody content here"
    result = extract_body(content)
    assert result == "Body content here"
    assert "title:" not in result


def test_extract_body_no_frontmatter():
    from utils import extract_body
    content = "Just body text without frontmatter"
    result = extract_body(content)
    assert result == content


def test_extract_body_empty():
    from utils import extract_body
    assert extract_body("") == ""


def test_extract_body_only_frontmatter():
    from utils import extract_body
    content = "---\ntitle: Test\n---\n"
    result = extract_body(content)
    assert result == ""


# Tests for extract_wiki_links
def test_extract_wiki_links_basic():
    from utils import extract_wiki_links
    body = "See [[other-note]] for details"
    result = extract_wiki_links(body)
    assert result == ["other-note"]


def test_extract_wiki_links_with_alias():
    from utils import extract_wiki_links
    body = "See [[note|display text]] for details"
    result = extract_wiki_links(body)
    assert result == ["note"]


def test_extract_wiki_links_deduplicates():
    from utils import extract_wiki_links
    body = "Link [[same]] and [[same]] again"
    result = extract_wiki_links(body)
    assert result == ["same"]


def test_extract_wiki_links_strips_extension():
    from utils import extract_wiki_links
    body = "Link [[note.md]] here"
    result = extract_wiki_links(body)
    assert result == ["note"]


def test_extract_wiki_links_empty():
    from utils import extract_wiki_links
    assert extract_wiki_links("No links here") == []


def test_extract_wiki_links_multiple():
    from utils import extract_wiki_links
    body = "See [[a]] and [[b]] and [[c|see c]]"
    result = extract_wiki_links(body)
    assert result == ["a", "b", "c"]


@patch('httpx.request')
def test_call_upsert_rpc_success(mock_request):
    """call_upsert_rpc doit réussir avec mock."""
    mock_response = Mock()
    mock_response.json.return_value = {"changed": True}
    mock_response.raise_for_status.return_value = None
    mock_response.is_success = True
    mock_request.return_value = mock_response

    import brain as _brain_module
    result = _brain_module.call_upsert_rpc("project-id", "preference", "key", "value", "source", "session-id")

    assert result is True
    mock_request.assert_called_once()


@patch('httpx.request')
def test_call_upsert_rpc_retry_on_failure(mock_request):
    """call_upsert_rpc doit retry sur échec."""
    from tenacity import RetryError
    mock_request.side_effect = Exception("Network error")

    import brain as _brain_module
    with pytest.raises(RetryError):
        _brain_module.call_upsert_rpc("project-id", "preference", "key", "value", "source", "session-id")

    # Should have been called 3 times
    assert mock_request.call_count == 3

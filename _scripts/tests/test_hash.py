# _scripts/tests/test_hash.py
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils import normalize_for_hash, compute_content_hash


def test_normalize_for_hash_strips_whitespace():
    result = normalize_for_hash("  hello world  \n")
    assert result == "hello world"


def test_normalize_for_hash_normalizes_crlf():
    result = normalize_for_hash("line1\r\nline2\r\nline3")
    assert result == "line1\nline2\nline3"


def test_normalize_for_hash_preserves_case():
    result = normalize_for_hash("Hello World")
    assert result == "Hello World"


def test_normalize_for_hash_handles_empty():
    result = normalize_for_hash("")
    assert result == ""


def test_normalize_for_hash_handles_only_whitespace():
    result = normalize_for_hash("   \n\n  ")
    assert result == ""


def test_compute_content_hash_deterministic():
    h1 = compute_content_hash("same content")
    h2 = compute_content_hash("same content")
    assert h1 == h2


def test_compute_content_hash_different_content():
    h1 = compute_content_hash("content a")
    h2 = compute_content_hash("content b")
    assert h1 != h2


def test_compute_content_hash_ignores_whitespace_diff():
    h1 = compute_content_hash("  hello\n")
    h2 = compute_content_hash("hello")
    assert h1 == h2


def test_compute_content_hash_returns_hex_string():
    h = compute_content_hash("test")
    assert isinstance(h, str)
    assert len(h) == 64
    all(c in "0123456789abcdef" for c in h)

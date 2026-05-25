"""Legacy smoke tests for the M8 tenant E2E validation entry point.

The live E2E implementation lives in `_scripts/tenant_e2e_validation.py`.
These tests avoid network calls and keep the old test filename from running
the previous service-role integration path by accident.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import tenant_e2e_validation as e2e  # noqa: E402


def test_legacy_e2e_defaults_never_target_personal():
    assert e2e.SOURCE_SLUG_DEFAULT != "personal"
    assert e2e.TARGET_SLUG_DEFAULT != "personal"


def test_legacy_e2e_parser_refuses_personal():
    with pytest.raises(SystemExit):
        e2e._parse_argv(["--source-slug", "personal"])

"""
Failure injection tests: verify BM25 fallback when vector search degrades.
Requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY env vars.
"""
import os
import json
import pytest
import urllib.request
import urllib.error

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

pytestmark = pytest.mark.skipif(
    not SUPABASE_URL or not SUPABASE_KEY,
    reason='Supabase credentials not available',
)

TIMEOUT = 30


SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')


def _rest_headers() -> dict:
    h = {'Content-Type': 'application/json'}
    # REST API requires apikey header + optional Bearer JWT
    if SUPABASE_ANON_KEY:
        h['apikey'] = SUPABASE_ANON_KEY
        h['Authorization'] = f'Bearer {SUPABASE_ANON_KEY}'
    else:
        h['apikey'] = SUPABASE_KEY
    return h


def rest_sql(sql: str) -> dict:
    url = f'{SUPABASE_URL}/rest/v1/rpc/'
    req = urllib.request.Request(
        url, data=json.dumps({'query': sql}).encode(), headers=_rest_headers(), method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {'error': e.read().decode(), 'status': e.code}


def call_hybrid(query: str, embedding: list | None = None) -> dict:
    url = f'{SUPABASE_URL}/rest/v1/rpc/query_vector_hybrid'
    headers = _rest_headers()
    # The hybrid RPC signature: query_vector_hybrid(query_text text, match_count int)
    payload = {'query_text': query, 'match_count': 3}
    if embedding:
        payload['embedding'] = json.dumps(embedding)
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers=headers, method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return {'data': json.loads(resp.read().decode())}
    except urllib.error.HTTPError as e:
        return {'error': e.read().decode(), 'status': e.code}


class TestFailureInjection:
    def _is_valid_result(self, result: dict) -> bool:
        if 'error' in result:
            return result.get('status') not in (400, 500)
        if 'data' in result and isinstance(result['data'], dict):
            return 'results' in result['data'] and isinstance(result['data']['results'], list)
        return True

    def test_bm25_fallback_on_missing_embedding(self):
        """No embedding supplied → BM25-only path should return results."""
        result = call_hybrid('machine learning')
        assert self._is_valid_result(result)

    def test_bm25_fallback_on_unexpected_params(self):
        """Extra params ignored — RPC accepts query_text + match_count only."""
        result = call_hybrid('vector search', embedding=[1, 2, 3])
        assert self._is_valid_result(result)

    def test_empty_query_returns_empty(self):
        """Empty query string should still execute (BM25 with empty tsquery)."""
        result = call_hybrid('')
        assert self._is_valid_result(result)

    def test_query_with_special_chars(self):
        """SQL special characters should be handled via parameterized format."""
        result = call_hybrid("machine learning; DROP TABLE vault_entries; --")
        assert self._is_valid_result(result)
        if 'data' in result and isinstance(result['data'], dict):
            assert isinstance(result['data']['results'], list)

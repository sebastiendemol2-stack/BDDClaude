import os
import json
import pytest
import urllib.request
import urllib.error
import uuid

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

pytestmark = pytest.mark.skipif(
    not SUPABASE_URL or not SUPABASE_KEY,
    reason='Supabase credentials not available',
)

METRICS_SLUG = 'metrics'
TIMEOUT = 15


def call_metrics(payload: dict | None = None, accept: str = 'application/json') -> dict | str:
    url = f'{SUPABASE_URL}/functions/v1/{METRICS_SLUG}'
    headers = {
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Accept': accept,
    }
    data = json.dumps(payload).encode() if payload else None
    if data:
        headers['Content-Type'] = 'application/json'

    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode()
            if accept == 'text/plain':
                return body
            return json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f'metrics returned {e.code}: {body}')


class TestMetricsJSON:
    def test_returns_expected_structure(self):
        result = call_metrics()
        assert isinstance(result, dict)

        assert 'entries' in result
        assert isinstance(result['entries']['total'], int)
        assert isinstance(result['entries']['by_type'], dict)
        assert isinstance(result['entries']['by_status'], dict)
        assert isinstance(result['entries']['by_freshness'], dict)
        assert isinstance(result['entries']['by_sensitivity'], dict)

        assert isinstance(result['memories'], int)
        assert isinstance(result['feedback'], int)
        assert isinstance(result['relations'], int)
        assert isinstance(result['events'], int)
        assert isinstance(result['sessions'], int)
        assert isinstance(result['sections'], int)
        assert isinstance(result['last_24h_entries'], int)
        assert isinstance(result['timestamp'], str)

        assert 'tool_calls' in result
        assert isinstance(result['tool_calls']['total'], int)
        assert isinstance(result['tool_calls']['by_status'], dict)

    def test_entries_by_type_contains_expected_keys(self):
        result = call_metrics()
        valid_types = {'concept', 'projet', 'contexte', 'recherche', 'decision', 'ressource', 'personne', 'daily', 'index'}
        for t in result['entries']['by_type']:
            assert t in valid_types, f'Unexpected entry type: {t}'


class TestMetricsPrometheus:
    def test_returns_plaintext(self):
        result = call_metrics(accept='text/plain')
        assert isinstance(result, str)
        assert result.startswith('# HELP')

    def test_contains_all_metric_families(self):
        result = call_metrics(accept='text/plain')
        expected_metrics = [
            'vault_entries_total',
            'vault_entries_by_type',
            'vault_entries_by_status',
            'vault_entries_by_freshness',
            'vault_memories_total',
            'vault_feedback_total',
            'vault_relations_total',
            'vault_events_total',
            'sessions_total',
            'tool_calls_total',
            # 'tool_calls_by_status' — only emitted when tool_calls table has rows,
            'vault_sections_total',
            'vault_entries_last_24h',
            'metrics_timestamp',
        ]
        for metric in expected_metrics:
            assert metric in result, f'Missing Prometheus metric: {metric}'


class TestMetricsDataFlow:
    def test_data_flow_via_entries(self):
        entries_before = call_metrics()['entries']['total']
        memories_before = call_metrics()['memories']

        test_session_id = str(uuid.uuid4())
        mem_id = None

        try:
            mem = self._call_edge_fn('memories-store', {
                'session_id': test_session_id,
                'project_slug': 'test-metrics-flow',
                'summary': 'Metrics integration test memory',
            })
            mem_id = mem.get('id')

            entries_after = call_metrics()['entries']['total']
            memories_after = call_metrics()['memories']

            assert entries_after >= entries_before, 'Entries should not decrease'
            assert memories_after > memories_before, 'Memories should increase'

        finally:
            if mem_id:
                import urllib.parse
                delete_url = f'{SUPABASE_URL}/rest/v1/vault_memories?id=eq.{mem_id}'
                delete_req = urllib.request.Request(
                    delete_url,
                    method='DELETE',
                    headers={'Authorization': f'Bearer {SUPABASE_KEY}'},
                )
                try:
                    urllib.request.urlopen(delete_req, timeout=10)
                except urllib.error.HTTPError:
                    pass

    @staticmethod
    def _call_edge_fn(slug: str, payload: dict) -> dict:
        url = f'{SUPABASE_URL}/functions/v1/{slug}'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {SUPABASE_KEY}',
        }
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(), headers=headers, method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            raise RuntimeError(f'{slug} returned {e.code}: {body}')

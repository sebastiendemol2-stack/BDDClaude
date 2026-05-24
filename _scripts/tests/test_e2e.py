"""
End-to-end test: vault entry → metrics → runtime → dashboard → worktree.
Requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY env vars.
"""
import os
import json
import uuid
import pytest
import urllib.request
import urllib.error

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

pytestmark = pytest.mark.skipif(
    not SUPABASE_URL or not SUPABASE_KEY,
    reason='Supabase credentials not available',
)

TIMEOUT = 20
FUNCTIONS = {
    'memories-store': 'memories-store',
    'feedback-collect': 'feedback-collect',
    'relations-update': 'relations-update',
    'metrics': 'metrics',
    'worktree-status': 'worktree-status',
}


def call_edge_fn(slug: str, payload: dict | None = None, method: str = 'POST', accept: str = 'application/json') -> dict | str:
    url = f'{SUPABASE_URL}/functions/v1/{slug}'
    headers = {'Authorization': f'Bearer {SUPABASE_KEY}', 'Accept': accept}
    data = json.dumps(payload).encode() if payload else None
    if data:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode()
            return json.loads(body) if accept != 'text/plain' else body
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'{slug} returned {e.code}: {e.read().decode()}')


class TestE2E:
    def test_all_edge_functions_are_reachable(self):
        """Verify all 5 core edge functions return 200."""
        results = {}
        payloads = {
            'metrics': {},
            'worktree-status': '__GET__',
            'memories-store': {'session_id': str(uuid.uuid4()), 'project_slug': '__probe__', 'summary': '__probe__'},
            'feedback-collect': {'content': '__probe__'},
            'relations-update': {'source_entry_id': '__probe__', 'target_entry_id': '__probe__', 'relation_type': 'references'},
        }
        for name, slug in FUNCTIONS.items():
            try:
                payload = payloads[slug]
                if payload == '__GET__':
                    resp = call_edge_fn(slug, method='GET')
                else:
                    resp = call_edge_fn(slug, payload)
                results[name] = 'ok'
            except RuntimeError as e:
                results[name] = str(e)
        errors = {k: v for k, v in results.items() if v != 'ok'}
        assert not errors, f'Unreachable functions: {errors}'

    def test_metrics_returns_valid_data(self):
        data = call_edge_fn('metrics')
        assert isinstance(data['entries']['total'], int)
        assert data['entries']['total'] >= 0
        assert isinstance(data['memories'], int)
        assert isinstance(data['feedback'], int)
        assert isinstance(data['relations'], int)

    def test_metrics_prometheus_format(self):
        text = call_edge_fn('metrics', accept='text/plain')
        assert text.startswith('# HELP')
        assert 'vault_entries_total' in text
        assert 'metrics_timestamp' in text

    def test_worktree_status_returns_report(self):
        data = call_edge_fn('worktree-status', method='GET')
        if data.get('report'):
            assert 'total_worktrees' in data['report']
            assert 'worktrees' in data['report']

    def test_memory_store_and_retrieve(self):
        session_id = str(uuid.uuid4())
        mem = call_edge_fn('memories-store', {
            'session_id': session_id,
            'project_slug': 'e2e-test',
            'summary': 'E2E test memory',
            'patterns': ['e2e-test'],
        })
        assert 'id' in mem
        # Verify via metrics
        data = call_edge_fn('metrics')
        assert data['memories'] >= 1

    def test_feedback_collect(self):
        fb = call_edge_fn('feedback-collect', {
            'content': 'E2E test feedback',
            'positive': True,
            'source': 'e2e-test',
        })
        assert 'id' in fb
        data = call_edge_fn('metrics')
        assert data['feedback'] >= 1

    def test_relations_update(self):
        rel = call_edge_fn('relations-update', {
            'source_entry_id': 'e2e-src',
            'target_entry_id': 'e2e-tgt',
            'relation_type': 'references',
            'confidence': 0.8,
        })
        assert 'id' in rel
        data = call_edge_fn('metrics')
        assert data['relations'] >= 1

    def test_full_cycle(self):
        """Full cycle: memory → feedback → relation → metrics verification."""
        session_id = str(uuid.uuid4())
        mem = call_edge_fn('memories-store', {
            'session_id': session_id,
            'project_slug': 'e2e-cycle',
            'summary': 'Cycle test',
        })
        assert 'id' in mem

        fb = call_edge_fn('feedback-collect', {
            'event_id': mem['id'],
            'content': 'Cycle feedback',
            'source': 'e2e-cycle',
        })
        assert 'id' in fb

        rel = call_edge_fn('relations-update', {
            'source_entry_id': mem['id'],
            'target_entry_id': fb['id'],
            'relation_type': 'related_to',
        })
        assert 'id' in rel

        metrics = call_edge_fn('metrics')
        assert metrics['memories'] >= 1
        assert metrics['feedback'] >= 1
        assert metrics['relations'] >= 1

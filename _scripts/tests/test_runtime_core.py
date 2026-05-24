import os
import json
import pytest
import subprocess
import tempfile
import textwrap

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

pytestmark = pytest.mark.skipif(
    not SUPABASE_URL or not SUPABASE_KEY,
    reason='Supabase credentials not available',
)


# Helper: call an Edge Function
def call_edge_fn(slug: str, payload: dict) -> dict:
    import urllib.request
    import urllib.error
    url = f'{SUPABASE_URL}/functions/v1/{slug}'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {SUPABASE_KEY}',
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=headers,
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f'{slug} returned {e.code}: {body}')


# ---------------------------------------------------------------------------
# memories-store Edge Function tests
# ---------------------------------------------------------------------------

class TestMemoriesStore:
    def test_store_and_retrieve(self):
        result = call_edge_fn('memories-store', {
            'session_id': '00000000-0000-0000-0000-000000000001',
            'project_slug': 'test-project',
            'summary': 'Test memory from runtime test suite',
            'decisions': [{'title': 'Test decision', 'description': 'Test'}],
            'patterns': ['test-pattern'],
        })
        assert 'id' in result
        assert isinstance(result['id'], str)

    def test_missing_session_id(self):
        with pytest.raises(RuntimeError, match='400'):
            call_edge_fn('memories-store', {
                'project_slug': 'test-project',
                'summary': 'Missing session_id',
            })

    def test_missing_summary(self):
        with pytest.raises(RuntimeError, match='400'):
            call_edge_fn('memories-store', {
                'session_id': '00000000-0000-0000-0000-000000000002',
                'project_slug': 'test-project',
            })


# ---------------------------------------------------------------------------
# feedback-collect Edge Function tests
# ---------------------------------------------------------------------------

class TestFeedbackCollect:
    def test_collect_positive_feedback(self):
        result = call_edge_fn('feedback-collect', {
            'content': 'Test positive feedback',
            'positive': True,
            'source': 'pytest',
        })
        assert 'id' in result
        assert isinstance(result['id'], str)

    def test_collect_negative_feedback(self):
        result = call_edge_fn('feedback-collect', {
            'content': 'Test negative feedback',
            'positive': False,
            'source': 'pytest',
        })
        assert 'id' in result

    def test_missing_content(self):
        with pytest.raises(RuntimeError, match='400'):
            call_edge_fn('feedback-collect', {})


# ---------------------------------------------------------------------------
# relations-update Edge Function tests
# ---------------------------------------------------------------------------

class TestRelationsUpdate:
    def test_add_relation(self):
        result = call_edge_fn('relations-update', {
            'source_entry_id': 'src-entry-test',
            'target_entry_id': 'tgt-entry-test',
            'relation_type': 'references',
            'confidence': 0.9,
        })
        assert 'id' in result
        assert isinstance(result['id'], str)

    def test_invalid_relation_type(self):
        with pytest.raises(RuntimeError, match='400'):
            call_edge_fn('relations-update', {
                'source_entry_id': 'a',
                'target_entry_id': 'b',
                'relation_type': 'invalid_type',
            })

    def test_missing_required_fields(self):
        with pytest.raises(RuntimeError, match='400'):
            call_edge_fn('relations-update', {
                'source_entry_id': 'a',
            })

    def test_depends_on_relation(self):
        result = call_edge_fn('relations-update', {
            'source_entry_id': 'src-entry-dep',
            'target_entry_id': 'tgt-entry-dep',
            'relation_type': 'depends_on',
        })
        assert 'id' in result


# ---------------------------------------------------------------------------
# Combined: full cycle test
# ---------------------------------------------------------------------------

class TestRuntimeCycle:
    def test_full_cycle(self):
        memory = call_edge_fn('memories-store', {
            'session_id': '00000000-0000-0000-0000-0000000000ff',
            'project_slug': 'test-cycle',
            'summary': 'Cycle test memory',
        })
        assert 'id' in memory

        feedback = call_edge_fn('feedback-collect', {
            'event_id': memory['id'],
            'content': 'Cycle test feedback',
            'source': 'pytest-cycle',
        })
        assert 'id' in feedback

        relation = call_edge_fn('relations-update', {
            'source_entry_id': memory['id'],
            'target_entry_id': feedback['id'],
            'relation_type': 'related_to',
        })
        assert 'id' in relation

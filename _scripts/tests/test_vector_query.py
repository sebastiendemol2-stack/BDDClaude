import os
import json
import subprocess
import sys
import pytest

# Ensure Supabase URL and service key are set in the environment for the test
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

@pytest.fixture(scope='module')
def supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        pytest.skip('Supabase credentials not available – integration test skipped')
    # Use the supabase-js client via node script for simplicity
    # We'll call a tiny node helper that executes the RPC and returns JSON
    def run_rpc(payload: dict):
        script = '''
            const { createClient } = require('@supabase/supabase-js');
            const url = process.env.SUPABASE_URL;
            const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
            const supabase = createClient(url, key);
            const payload = JSON.parse(process.argv[2]);
            supabase.rpc('query_vector_hybrid', payload).then(r => {
                console.log(JSON.stringify(r.data));
            }).catch(e => {
                console.error('RPC error', e);
                process.exit(1);
            });
        '''
        # Write temporary node script
        import tempfile, textwrap
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.js') as f:
            f.write(textwrap.dedent(script))
            script_path = f.name
        env = os.environ.copy()
        result = subprocess.run(['node', script_path, json.dumps(payload)], env=env, capture_output=True, text=True)
        os.unlink(script_path)
        if result.returncode != 0:
            raise RuntimeError(f'Node RPC call failed: {result.stderr}')
        return json.loads(result.stdout)
    return run_rpc

def test_vector_search_without_embedding(supabase_client):
    payload = {'query': 'test', 'limit': 1}
    data = supabase_client(payload)
    assert isinstance(data, list)
    assert len(data) == 1
    # Each result should contain id, title, snippet, score
    for key in ('id', 'title', 'snippet', 'score'):
        assert key in data[0]

def test_vector_search_with_embedding(supabase_client):
    # Use a dummy small vector (dimension = 3 for test – actual column expects 1536 but PG will accept any length)
    payload = {'query': 'test', 'embedding': json.dumps([0.1, 0.2, 0.3]), 'limit': 1}
    data = supabase_client(payload)
    assert isinstance(data, list)
    assert len(data) == 1
    for key in ('id', 'title', 'snippet', 'score'):
        assert key in data[0]

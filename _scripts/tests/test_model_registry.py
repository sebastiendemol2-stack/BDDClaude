"""
Integration tests for the M7 Model Registry Edge Functions.
Requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY.
"""
import json
import os
import uuid
import urllib.error
import urllib.parse
import urllib.request

import pytest


SUPABASE_URL = os.getenv('SUPABASE_URL')
SERVICE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
ANON_KEY = os.getenv('SUPABASE_ANON_KEY')
RUN_REMOTE = os.getenv('RUN_MODEL_REGISTRY_INTEGRATION') == '1'

TIMEOUT = 20
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def read_repo_file(*parts: str) -> str:
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as handle:
        return handle.read()


def call_edge_fn(slug: str, payload: dict, key: str | None = None) -> dict:
    token = key or SERVICE_KEY
    url = f'{SUPABASE_URL}/functions/v1/{slug}'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}',
        'apikey': token,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=headers,
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f'{slug} returned {e.code}: {body}')


def delete_model(model_id: str) -> None:
    encoded_id = urllib.parse.quote(model_id)
    req = urllib.request.Request(
        f'{SUPABASE_URL}/rest/v1/vault_models?id=eq.{encoded_id}',
        method='DELETE',
        headers={
            'Authorization': f'Bearer {SERVICE_KEY}',
            'apikey': SERVICE_KEY,
        },
    )
    try:
        urllib.request.urlopen(req, timeout=TIMEOUT)
    except urllib.error.HTTPError:
        pass


class TestModelRegistryStatic:
    def test_migration_uses_versioned_identity_and_restricted_rls(self):
        sql = read_repo_file('supabase', 'migrations', '2026-05-22_model_registry.sql')
        assert 'UNIQUE (provider, name, version)' in sql
        assert 'TO service_role' in sql
        assert 'TO anon, authenticated' in sql
        assert "USING (status = 'active')" in sql

    def test_admin_mutations_require_admin_request(self):
        register_fn = read_repo_file('supabase', 'functions', 'model-register', 'index.ts')
        deactivate_fn = read_repo_file('supabase', 'functions', 'model-deactivate', 'index.ts')
        assert 'isAdminRequest(req)' in register_fn
        assert 'isAdminRequest(req)' in deactivate_fn

    def test_sdk_exposes_model_fallback_helpers(self):
        sdk = read_repo_file('supabase', 'ukp-client.ts')
        assert 'async latestModel' in sdk
        assert 'async getModelFallbackChain' in sdk
        assert 'async updateModelStatus' in sdk

    def test_dashboard_uses_supabase_auth_jwt_for_admin_writes(self):
        auth_provider = read_repo_file('dashboard', 'src', 'lib', 'auth.tsx')
        assert 'supabase.auth.getSession' in auth_provider
        assert 'onAuthStateChange' in auth_provider
        assert "metadata.role === 'admin'" in auth_provider

        models_page = read_repo_file('dashboard', 'src', 'pages', 'Models.tsx')
        assert "from '../lib/auth'" in models_page
        assert 'useAuth()' in models_page
        assert 'session?.access_token' in models_page
        assert 'Bearer ${accessToken}' in models_page

        login_page = read_repo_file('dashboard', 'src', 'pages', 'Login.tsx')
        assert 'signIn(' in login_page

        app_shell = read_repo_file('dashboard', 'src', 'App.tsx')
        assert 'AuthProvider' in app_shell
        assert '/login' in app_shell


@pytest.mark.skipif(
    not RUN_REMOTE or not SUPABASE_URL or not SERVICE_KEY,
    reason='Set RUN_MODEL_REGISTRY_INTEGRATION=1 plus Supabase credentials to run remote tests',
)
class TestModelRegistryRemote:
    def test_register_latest_and_deactivate_cycle(self):
        suffix = uuid.uuid4().hex[:8]
        provider = 'pytest'
        first_name = f'embed-small-{suffix}'
        second_name = f'embed-large-{suffix}'
        created: list[str] = []

        try:
            first = call_edge_fn('model-register', {
                'name': first_name,
                'provider': provider,
                'version': '1.0.0',
                'kind': 'embedding',
                'dimension': 1536,
                'priority': 10,
                'fallback_order': 20,
                'rollout_percent': 100,
                'status': 'active',
            })['model']
            created.append(first['id'])

            second = call_edge_fn('model-register', {
                'name': second_name,
                'provider': provider,
                'version': '1.0.0',
                'kind': 'embedding',
                'dimension': 3072,
                'priority': 20,
                'fallback_order': 10,
                'rollout_percent': 0,
                'status': 'active',
            })['model']
            created.append(second['id'])

            listed = call_edge_fn('model-list', {'provider': provider, 'include_inactive': True})
            assert listed['total'] == 2

            latest = call_edge_fn('model-latest', {'provider': provider, 'kind': 'embedding'})
            assert latest['model']['id'] == second['id']
            assert latest['fallbacks'][0]['id'] == first['id']

            updated = call_edge_fn('model-deactivate', {'id': second['id'], 'status': 'inactive'})['model']
            assert updated['status'] == 'inactive'

            fallback_latest = call_edge_fn('model-latest', {'provider': provider, 'kind': 'embedding'})
            assert fallback_latest['model']['id'] == first['id']

        finally:
            for model_id in created:
                delete_model(model_id)

    def test_register_requires_required_fields(self):
        with pytest.raises(RuntimeError, match='400'):
            call_edge_fn('model-register', {'provider': 'pytest', 'dimension': 1536})

    @pytest.mark.skipif(not ANON_KEY, reason='SUPABASE_ANON_KEY not available')
    def test_public_list_does_not_include_inactive_models(self):
        suffix = uuid.uuid4().hex[:8]
        provider = 'pytest-public'
        created: list[str] = []

        try:
            inactive = call_edge_fn('model-register', {
                'name': f'inactive-{suffix}',
                'provider': provider,
                'dimension': 1536,
                'status': 'inactive',
            })['model']
            created.append(inactive['id'])

            public_list = call_edge_fn(
                'model-list',
                {'provider': provider, 'include_inactive': True},
                key=ANON_KEY,
            )
            assert public_list['total'] == 0

        finally:
            for model_id in created:
                delete_model(model_id)

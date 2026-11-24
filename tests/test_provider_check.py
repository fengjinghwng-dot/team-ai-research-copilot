import json

import httpx
import pytest

from copilot import provider_check
from copilot.config import Settings


@pytest.mark.parametrize('outcome', ['success', 'missing_model', 'unauthorized', 'timeout'])
def test_catalog_check_is_get_only_and_never_echoes_credentials(monkeypatch, outcome):
    cfg = Settings(_env_file=None, llm_provider='openai_compatible', llm_base_url='https://custom.test.invalid/v1',
        cheap_model='custom-model', deep_model='custom-model', llm_api_key='test-credential-do-not-echo')
    requests = []
    def handle(request):
        requests.append(request)
        assert request.method == 'GET' and request.url.path == '/v1/models'
        assert request.headers['Authorization'] == 'Bearer ' + cfg.llm_api_key
        if outcome == 'timeout':
            raise httpx.ReadTimeout(cfg.llm_api_key)
        if outcome == 'unauthorized':
            return httpx.Response(401, json={'error': cfg.llm_api_key})
        return httpx.Response(200, json={'data': [{'id': 'custom-model' if outcome == 'success' else 'another-model'}]})
    client = httpx.Client(transport=httpx.MockTransport(handle))
    monkeypatch.setattr(provider_check, 'settings', lambda: cfg)
    monkeypatch.setattr(provider_check.httpx, 'Client', lambda **kwargs: client)
    result = provider_check.check_provider()
    assert len(requests) == 1 and result['ok'] == (outcome == 'success')
    assert result['generation_requests'] == 0 and not result['llm_enabled'] and not result['pricing_confirmed']
    assert cfg.llm_api_key not in json.dumps(result)


def test_missing_key_is_detected_before_network(monkeypatch):
    cfg = Settings(_env_file=None, llm_provider='openai_compatible', llm_base_url='https://custom.test.invalid/v1',
        cheap_model='custom-model', deep_model='custom-model')
    monkeypatch.setattr(provider_check, 'settings', lambda: cfg)
    def forbidden(**kwargs):
        raise AssertionError('Must not request without key')
    monkeypatch.setattr(provider_check.httpx, 'Client', forbidden)
    assert provider_check.check_provider()['state'] == 'key_missing'

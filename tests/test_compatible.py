import json
from decimal import Decimal

import httpx
import pytest
from openai import APITimeoutError, OpenAI

from copilot import llm
from copilot.config import Settings
from copilot.schemas import RelevanceReport


def config(**overrides):
    values = dict(llm_provider="openai_compatible", llm_base_url="https://model.test.invalid/v1",
                  cheap_model="test-custom", deep_model="test-custom", daily_token_limit=10000000)
    return Settings(_env_file=None, **(values | overrides))


def test_custom_endpoint_requires_confirmed_prices_before_enablement():
    assert config(llm_input_cny_per_million="").monetary_guard_rate is None
    with pytest.raises(ValueError, match="confirmed") as error:
        config(llm_enabled=True, llm_api_key="private-test-value")
    assert "private-test-value" not in str(error.value)
    cfg = config(llm_enabled=True, llm_api_key="test-only", llm_input_cny_per_million="1",
                 llm_output_cny_per_million="4")
    assert cfg.effective_daily_token_limit == 5000000
    assert cfg.monetary_guard_rate == Decimal("4")
    assert cfg.llm_cache_identity != config(llm_base_url="https://another.test.invalid/v1").llm_cache_identity
    with pytest.raises(ValueError):
        config(llm_base_url="https://user:password@model.test.invalid/v1")


@pytest.mark.parametrize("outcome", ["success", "refusal", "timeout", "invalid_json"])
def test_chat_schema_usage_and_single_attempt(monkeypatch, outcome):
    cfg = config(llm_enabled=True, llm_api_key="test-only", llm_input_cny_per_million="1",
                 llm_output_cny_per_million="4")
    events, requests = [], []
    def handle(request):
        assert events == ["reserved"]
        assert request.url.path == "/v1/chat/completions"
        body = json.loads(request.content)
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["strict"] is True
        assert body["model"] == cfg.cheap_model and body["max_tokens"] == 3500
        requests.append(request)
        if outcome == "timeout":
            raise httpx.ReadTimeout("test timeout")
        content = '{"topics":[],"quality":0.8,"reason":"test"}' if outcome != "invalid_json" else "invalid"
        message = {"role": "assistant", "content": content} if outcome != "refusal" else {"role": "assistant", "refusal": "declined"}
        return httpx.Response(200, json={"id":"test","object":"chat.completion","created":1,"model":cfg.cheap_model,
            "choices":[{"index":0,"finish_reason":"stop","message":message}],
            "usage":{"prompt_tokens":40,"completion_tokens":10,"total_tokens":50}})
    client = OpenAI(api_key=cfg.llm_api_key, base_url=cfg.llm_base_url, max_retries=0,
                    http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    monkeypatch.setattr(llm, "settings", lambda: cfg)
    monkeypatch.setattr(llm, "client", lambda: client)
    monkeypatch.setattr(llm, "reserve", lambda *args: events.append("reserved") or "call")
    monkeypatch.setattr(llm, "settle", lambda *args, **kwargs: events.append(("settled", args[1], kwargs)))
    monkeypatch.setattr(llm, "uncertain", lambda *args: events.append("uncertain"))
    try:
        if outcome == "success":
            assert llm.structured("team", cfg.cheap_model, "rank", "prompt", {}, RelevanceReport).quality == .8
        else:
            with pytest.raises((ValueError, APITimeoutError)):
                llm.structured("team", cfg.cheap_model, "rank", "prompt", {}, RelevanceReport)
        assert len(requests) == 1
        if outcome in {"success", "refusal"}:
            assert events[-1][0:2] == ("settled", 50) and "uncertain" not in events
        else:
            assert events[-1] == "uncertain"
    finally:
        client.close()

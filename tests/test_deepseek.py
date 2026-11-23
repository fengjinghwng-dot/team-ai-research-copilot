from decimal import Decimal
from types import SimpleNamespace

import pytest

from copilot import llm
from copilot.config import Settings
from copilot.schemas import RelevanceReport


def config(**overrides):
    return Settings(_env_file=None, **{
        "llm_provider": "deepseek", "cheap_model": "deepseek-flash", "deep_model": "deepseek-flash",
        "daily_token_limit": 10_000_000, "daily_budget_cny": Decimal("20"), **overrides,
    })


def test_cny_budget_uses_peak_output_price_for_every_token():
    assert config().effective_daily_token_limit == 2_500_000
    assert config(daily_budget_cny="0.01").effective_daily_token_limit == 1250
    assert config(daily_token_limit=300_000).effective_daily_token_limit == 300_000


def test_deepseek_rejects_wrong_model_or_missing_key():
    with pytest.raises(ValueError, match="budget guard"):
        config(deep_model="deepseek-v4-pro")
    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        config(llm_enabled=True, openai_api_key="wrong-provider-placeholder", deepseek_api_key="")
    assert config(llm_enabled=True, deepseek_api_key="placeholder").llm_enabled


def test_client_uses_only_official_deepseek_endpoint_without_retries(monkeypatch):
    cfg = config(llm_enabled=True, deepseek_api_key="placeholder")
    monkeypatch.setattr(llm, "settings", lambda: cfg)
    captured = {}
    monkeypatch.setattr(llm, "OpenAI", lambda **kwargs: captured.update(kwargs) or "client")
    assert llm.client() == "client"
    assert captured == {"api_key": "placeholder", "base_url": "https://api.deepseek.com",
                        "max_retries": 0, "timeout": 120}


def test_deepseek_structured_response_still_reserves_and_validates(monkeypatch):
    monkeypatch.setattr(llm, "settings", lambda: config())
    events, requests = [], []
    parsed = RelevanceReport(topics=[], quality=.8, reason="Test")
    response = SimpleNamespace(status="completed", usage=SimpleNamespace(input_tokens=20, output_tokens=10),
                               output_parsed=parsed)
    def parse(**kwargs):
        requests.append(kwargs)
        return response
    monkeypatch.setattr(llm, "client", lambda: SimpleNamespace(responses=SimpleNamespace(parse=parse)))
    monkeypatch.setattr(llm, "reserve", lambda *args: events.append("reserved") or "call")
    monkeypatch.setattr(llm, "settle", lambda call, usage, **kwargs: events.append(usage))
    assert llm.structured("team", "deepseek-flash", "ranking", "prompt", {}, RelevanceReport) == parsed
    assert events == ["reserved", 30]
    assert requests[0]["reasoning"] == {"effort": "none"}
    assert requests[0]["text_format"] is RelevanceReport
    with pytest.raises(ValueError, match="Unpriced"):
        llm.structured("team", "deepseek-v4-pro", "ranking", "prompt", {}, RelevanceReport)
    assert events == ["reserved", 30]


def test_deepseek_embedding_is_explicitly_unavailable_without_spending(monkeypatch):
    monkeypatch.setattr(llm, "settings", lambda: config())
    def unexpected():
        pytest.fail("An unsupported embedding request must never reach a provider")
    monkeypatch.setattr(llm, "client", unexpected)
    with pytest.raises(llm.LLMDisabled, match="embedding provider"):
        llm.embed("team", ["query"])

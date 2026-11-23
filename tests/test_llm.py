from types import SimpleNamespace

import pytest

from copilot import llm
from copilot.schemas import RelevanceReport


def mock_budget(monkeypatch):
    events = []
    monkeypatch.setattr(llm, "reserve", lambda *args: events.append(("reserve", args[-1])) or "call-id")
    monkeypatch.setattr(llm, "settle", lambda call, actual, **kwargs: events.append(("settle", actual)))
    monkeypatch.setattr(llm, "uncertain", lambda call: events.append(("uncertain", call)))
    return events


def test_structured_call_settles_before_publishing(monkeypatch):
    events = mock_budget(monkeypatch)
    parsed = RelevanceReport(topics=[], quality=.8, reason="Test")
    response = SimpleNamespace(status="completed", usage=SimpleNamespace(input_tokens=50, output_tokens=20),
                               output_parsed=parsed)
    monkeypatch.setattr(llm, "client", lambda: SimpleNamespace(responses=SimpleNamespace(parse=lambda **kw: response)))
    assert llm.structured("team", "model", "rank", "prompt", {}, RelevanceReport) == parsed
    assert events[0][0] == "reserve" and events[1] == ("settle", 70)


def test_timeout_retains_reservation(monkeypatch):
    events = mock_budget(monkeypatch)
    def fail(**kwargs):
        raise TimeoutError("ambiguous")
    monkeypatch.setattr(llm, "client", lambda: SimpleNamespace(responses=SimpleNamespace(parse=fail)))
    with pytest.raises(TimeoutError):
        llm.structured("team", "model", "rank", "prompt", {}, RelevanceReport)
    assert events[-1][0] == "uncertain" and not any(x[0] == "settle" for x in events)


def test_refusal_is_not_published_but_usage_is_settled(monkeypatch):
    events = mock_budget(monkeypatch)
    response = SimpleNamespace(status="completed", usage=SimpleNamespace(input_tokens=10, output_tokens=5),
                               output_parsed=None)
    monkeypatch.setattr(llm, "client", lambda: SimpleNamespace(responses=SimpleNamespace(parse=lambda **kw: response)))
    with pytest.raises(ValueError):
        llm.structured("team", "model", "rank", "prompt", {}, RelevanceReport)
    assert events[-1] == ("settle", 15)

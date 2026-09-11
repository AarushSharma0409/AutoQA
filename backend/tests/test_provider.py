import asyncio
import json
import httpx
import pytest
from app.config import settings
from app.provider import live_decision, prepare_call


def test_structured_provider_request(monkeypatch):
    original = httpx.AsyncClient
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"tool_calls": [{"function": {"name": "search", "arguments": '{"query":"retail evidence"}'}}]}}],
                "usage": {"total_tokens": 123},
            },
        )

    monkeypatch.setattr("app.provider.httpx.AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    decision, tokens = asyncio.run(live_decision("Research retail", {}, []))
    assert decision.tool == "search" and tokens == 123
    assert requests[0]["tool_choice"] == "required"
    assert requests[0]["parallel_tool_calls"] is False
    assert "UNTRUSTED DATA" in requests[0]["messages"][0]["content"]
    assert {t["function"]["name"] for t in requests[0]["tools"]} >= {"search", "python", "browse", "report"}


@pytest.mark.parametrize("field,value,error", [("max_tokens", 20, "Token budget"), ("max_cost", 0.0000001, "cost budget")])
def test_provider_preflight_budget(monkeypatch, field, value, error):
    monkeypatch.setattr(settings(), field, value)
    with pytest.raises(ValueError, match=error):
        prepare_call("Research retail", {}, [])


def test_optional_reasoning_effort(monkeypatch):
    monkeypatch.setattr(settings(), "llm_reasoning_effort", "low")
    request, _ = prepare_call("Research retail", {}, [])
    assert request["reasoning_effort"] == "low"
    monkeypatch.setattr(settings(), "llm_reasoning_effort", "")
    assert "reasoning_effort" not in prepare_call("Research retail", {}, [])[0]

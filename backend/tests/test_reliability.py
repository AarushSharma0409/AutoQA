import asyncio
import json
import httpx
import pytest
from app.provider import live_decision, prepare_call, RateLimited
from app.tools import report
from app.schemas import Report
from app.db import Session, Task
from app.runtime import run_task


def test_long_history_is_compacted_without_modifying_saved_context():
    cp = {"context_results": [{"output": {"text": "x" * 50000}}] * 30, "results": [{"tool": "search", "output": {"sources": [{"id": "source-1", "url": "https://example.com", "excerpt": "evidence " * 2000}]}}]}
    request, reserve = prepare_call("Revise this report", cp, [])
    assert reserve < 15000
    assert "source-1" in request["messages"][1]["content"]
    assert len(cp["context_results"][0]["output"]["text"]) == 50000
    json.loads(request["messages"][1]["content"])


def test_rate_limit_wait_then_success(monkeypatch):
    original = httpx.AsyncClient
    calls, waits = [], []
    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, json={"choices": [{"message": {"tool_calls": [{"function": {"name": "finish", "arguments": '{"summary":"Done"}'}}]}}], "usage": {"total_tokens": 25}})
    async def sleep(delay):
        waits.append(delay)
    monkeypatch.setattr("app.provider.httpx.AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setattr("app.provider.asyncio.sleep", sleep)
    decision, tokens = asyncio.run(live_decision("Finish", {}, []))
    assert decision.tool == "finish" and tokens == 25 and waits == [2]


def test_long_quota_reset_does_not_retry_early(monkeypatch):
    original = httpx.AsyncClient
    monkeypatch.setattr("app.provider.httpx.AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(lambda _: httpx.Response(429, headers={"Retry-After": "3600"})), **kwargs))
    with pytest.raises(RateLimited):
        asyncio.run(live_decision("Finish", {}, []))


def test_rejected_rate_limited_request_releases_reservation(monkeypatch):
    with Session.begin() as db:
        task = Task(owner="test", goal="Research Python", mode="live", checkpoint={})
        db.add(task)
        db.flush()
        task_id = task.id
    async def rejected(*args, **kwargs):
        raise RateLimited("Model provider HTTP 429: quota exhausted")
    monkeypatch.setattr("app.runtime.live_decision", rejected)
    asyncio.run(run_task(task_id))
    with Session() as db:
        task = db.get(Task, task_id)
        assert task.status == "failed"
        assert task.checkpoint["tokens"] == 0
        assert task.checkpoint["cost"] == pytest.approx(0)
        assert "provider_reservation" not in task.checkpoint


def test_report_requires_inline_evidence():
    cp = {"results": [{"tool": "search", "output": {"sources": [{"id": "s1", "title": "Source", "url": "https://example.com", "excerpt": "Observed value is 10."}]}}]}
    with pytest.raises(ValueError, match="inline"):
        report(Report(title="Report", findings="Value is 10", hypotheses="", source_ids=["s1"]), cp, "live")
    result, artifacts = report(Report(title="Report", findings="Value is 10 [s1]", hypotheses="", source_ids=["s1"]), cp, "live")
    assert result["source_ids"] == ["s1"] and len(artifacts) == 3
    with pytest.raises(ValueError, match="numbers absent"):
        report(Report(title="Report", findings="Value is 99 [s1]", hypotheses="", source_ids=["s1"]), cp, "live")

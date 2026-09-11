import asyncio
import json

import httpx
import pytest

from app.config import settings
from app.schemas import Search
from app.tools import search


@pytest.mark.parametrize("provider,key", [("tavily", ""), ("tavily", "test-key"), ("brave", "test-key")])
def test_search_auth_and_safe_retrieval(monkeypatch, provider, key):
    cfg = settings()
    monkeypatch.setattr(cfg, "search_provider", provider)
    monkeypatch.setattr(cfg, "tavily_api_key", key)
    monkeypatch.setattr(cfg, "search_api_key", key)
    original = httpx.AsyncClient
    retrieved = []

    def handler(request):
        if provider == "tavily":
            assert request.method == "POST"
            body = json.loads(request.content)
            assert body["search_depth"] == "basic" and body["auto_parameters"] is False
            assert request.headers.get("Authorization") == (f"Bearer {key}" if key else None)
            assert request.headers.get("X-Tavily-Access-Mode") == (None if key else "keyless")
        else:
            assert request.headers["X-Subscription-Token"] == key
        results = [{"title": "Blocked", "url": "http://127.0.0.1"}, {"title": "Public", "url": "https://example.com"}]
        return httpx.Response(200, json={"results": results} if provider == "tavily" else {"web": {"results": results}})

    def fetch(url):
        retrieved.append(url)
        if url.startswith("http://127"):
            raise ValueError("Private address")
        return {"url": url, "body": "<p>Verified page text</p>"}

    monkeypatch.setattr("app.tools.httpx.AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setattr("app.tools.fetch_public", fetch)
    result = asyncio.run(search(Search(query="public evidence"), "live"))
    assert len(retrieved) == 2
    assert len(result["sources"]) == 1
    assert result["sources"][0]["excerpt"] == "Verified page text"
    assert result["sources"][0]["fixture"] is False


def test_tavily_quota_error(monkeypatch):
    monkeypatch.setattr(settings(), "search_provider", "tavily")
    original = httpx.AsyncClient
    monkeypatch.setattr("app.tools.httpx.AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(lambda _: httpx.Response(429)), **kwargs))
    with pytest.raises(ValueError, match="quota or rate limit"):
        asyncio.run(search(Search(query="public evidence"), "live"))

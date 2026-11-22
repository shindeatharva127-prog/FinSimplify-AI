"""FinSimplify AI tests. NewsAPI and Groq calls are mocked with respx (no real keys needed)."""
from __future__ import annotations

import json
import os

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

os.environ.setdefault("NEWSAPI_KEY", "test-newsapi-key")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("GROQ_MODEL", "llama-3.3-70b-versatile")

from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_health_ok_when_fully_configured(monkeypatch):
    monkeypatch.setenv("NEWSAPI_KEY", "abc123")
    monkeypatch.setenv("GROQ_API_KEY", "def456")
    get_settings.cache_clear()
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["newsapi_configured"] is True
    assert body["groq_configured"] is True
    assert "abc123" not in response.text
    assert "def456" not in response.text


def test_health_degraded_when_missing_keys(monkeypatch):
    monkeypatch.setenv("NEWSAPI_KEY", "")
    monkeypatch.setenv("GROQ_API_KEY", "")
    get_settings.cache_clear()
    body = client.get("/api/health").json()
    assert body["status"] == "degraded"
    assert body["newsapi_configured"] is False
    assert body["groq_configured"] is False


NEWSAPI_SAMPLE_RESPONSE = {
    "status": "ok",
    "totalResults": 2,
    "articles": [
        {"source": {"id": None, "name": "Reuters"}, "title": "Central bank raises interest rates",
         "description": "A short description of monetary policy.", "url": "https://example.com/article-1",
         "urlToImage": "https://example.com/image1.jpg", "publishedAt": "2024-05-01T12:00:00Z", "content": "Full content here."},
        {"source": {"id": None, "name": "Reuters"}, "title": "Central bank raises interest rates (dup)",
         "description": "duplicate", "url": "https://example.com/article-1", "urlToImage": None,
         "publishedAt": "2024-05-01T12:00:00Z", "content": None},
        {"source": {"id": None, "name": "Bloomberg"}, "title": "[Removed]", "description": None,
         "url": "https://removed.example.com", "urlToImage": None, "publishedAt": None, "content": None},
        {"source": {"id": None, "name": "Bloomberg"}, "title": "Tech company reports strong earnings",
         "description": "Earnings beat expectations.", "url": "https://example.com/article-2", "urlToImage": None,
         "publishedAt": "2024-05-02T08:30:00Z", "content": "Earnings details."},
    ],
}


@respx.mock
def test_get_news_success(monkeypatch):
    monkeypatch.setenv("NEWSAPI_KEY", "abc123")
    get_settings.cache_clear()
    respx.get("https://newsapi.org/v2/everything").mock(return_value=httpx.Response(200, json=NEWSAPI_SAMPLE_RESPONSE))
    response = client.get("/api/news", params={"topic": "banking"})
    assert response.status_code == 200
    urls = [a["url"] for a in response.json()["articles"]]
    assert urls.count("https://example.com/article-1") == 1
    assert "https://removed.example.com" not in urls
    assert len(urls) == 2


@respx.mock
def test_get_news_with_query(monkeypatch):
    monkeypatch.setenv("NEWSAPI_KEY", "abc123")
    get_settings.cache_clear()
    route = respx.get("https://newsapi.org/v2/everything").mock(
        return_value=httpx.Response(200, json={"status": "ok", "totalResults": 0, "articles": []})
    )
    assert client.get("/api/news", params={"q": "Tesla"}).status_code == 200
    assert dict(route.calls[0].request.url.params)["q"] == "Tesla"


def test_get_news_missing_api_key(monkeypatch):
    monkeypatch.setenv("NEWSAPI_KEY", "")
    get_settings.cache_clear()
    response = client.get("/api/news")
    assert response.status_code == 503
    assert "NEWSAPI_KEY" in response.json()["detail"]


@respx.mock
def test_get_news_upstream_unauthorized(monkeypatch):
    monkeypatch.setenv("NEWSAPI_KEY", "bad-key")
    get_settings.cache_clear()
    respx.get("https://newsapi.org/v2/everything").mock(return_value=httpx.Response(401, json={"status": "error", "message": "Invalid key"}))
    assert client.get("/api/news").status_code == 502


@respx.mock
def test_get_news_upstream_rate_limited(monkeypatch):
    monkeypatch.setenv("NEWSAPI_KEY", "abc123")
    get_settings.cache_clear()
    respx.get("https://newsapi.org/v2/everything").mock(return_value=httpx.Response(429, json={"status": "error", "message": "Rate limited"}))
    assert client.get("/api/news").status_code == 429


@respx.mock
def test_get_news_network_error(monkeypatch):
    monkeypatch.setenv("NEWSAPI_KEY", "abc123")
    get_settings.cache_clear()
    respx.get("https://newsapi.org/v2/everything").mock(side_effect=httpx.ConnectError("boom"))
    assert client.get("/api/news").status_code == 502


def test_get_news_page_size_too_large(monkeypatch):
    monkeypatch.setenv("NEWSAPI_KEY", "abc123")
    get_settings.cache_clear()
    assert client.get("/api/news", params={"page_size": 999}).status_code == 400


def test_get_news_invalid_topic():
    assert client.get("/api/news", params={"topic": "not-a-real-topic"}).status_code == 422


GROQ_VALID_JSON = {
    "simple_summary": "The central bank raised interest rates to fight inflation.",
    "key_takeaways": ["Interest rates went up.", "This affects loans and savings.", "The bank is trying to slow inflation."],
    "why_it_matters": "Higher rates can make borrowing more expensive for consumers.",
    "topic": "Banking",
    "sentiment": "neutral",
    "important_terms": [
        {"term": "Interest rate", "explanation": "The cost of borrowing money, shown as a percentage."},
        {"term": "Inflation", "explanation": "A general rise in prices over time."},
    ],
}
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
BASIC_BODY = {"title": "Some headline", "description": "", "content": "", "url": ""}


def _groq_response(content: str) -> dict:
    return {"id": "chatcmpl-test", "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}]}


@respx.mock
def test_summarize_success(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "def456")
    get_settings.cache_clear()
    respx.post(GROQ_URL).mock(return_value=httpx.Response(200, json=_groq_response(json.dumps(GROQ_VALID_JSON))))
    response = client.post("/api/summarize", json={
        "title": "Central bank raises interest rates", "description": "A short description.",
        "content": "Full content here.", "url": "https://example.com/article-1"})
    assert response.status_code == 200
    body = response.json()
    assert body["sentiment"] == "neutral"
    assert len(body["key_takeaways"]) == 3
    assert len(body["important_terms"]) == 2
    assert "disclaimer" in body


@respx.mock
def test_summarize_handles_markdown_fenced_json(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "def456")
    get_settings.cache_clear()
    fenced = "```json\n" + json.dumps(GROQ_VALID_JSON) + "\n```"
    respx.post(GROQ_URL).mock(return_value=httpx.Response(200, json=_groq_response(fenced)))
    assert client.post("/api/summarize", json=BASIC_BODY).status_code == 200


@respx.mock
def test_summarize_malformed_json_returns_502(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "def456")
    get_settings.cache_clear()
    respx.post(GROQ_URL).mock(return_value=httpx.Response(200, json=_groq_response("not json at all")))
    assert client.post("/api/summarize", json=BASIC_BODY).status_code == 502


def test_summarize_missing_api_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    get_settings.cache_clear()
    assert client.post("/api/summarize", json=BASIC_BODY).status_code == 503


def test_summarize_missing_title_field():
    assert client.post("/api/summarize", json={"description": "no title provided"}).status_code == 422


def test_summarize_blank_title():
    assert client.post("/api/summarize", json={"title": "   ", "description": "x"}).status_code == 422


@respx.mock
def test_summarize_upstream_unauthorized(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "bad-key")
    get_settings.cache_clear()
    respx.post(GROQ_URL).mock(return_value=httpx.Response(401, json={"error": {"message": "Invalid API key"}}))
    assert client.post("/api/summarize", json=BASIC_BODY).status_code == 502


@respx.mock
def test_summarize_upstream_rate_limited(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "def456")
    get_settings.cache_clear()
    respx.post(GROQ_URL).mock(return_value=httpx.Response(429, json={"error": {"message": "rate limited"}}))
    assert client.post("/api/summarize", json=BASIC_BODY).status_code == 429


def test_index_page_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "FinSimplify AI" in response.text


def test_static_assets_served():
    assert client.get("/static/css/style.css").status_code == 200
    assert client.get("/static/js/app.js").status_code == 200


def test_placeholder_keys_count_as_unconfigured(monkeypatch):
    monkeypatch.setenv("NEWSAPI_KEY", "your_newsapi_key_here")
    monkeypatch.setenv("GROQ_API_KEY", "your_groq_api_key_here")
    get_settings.cache_clear()
    body = client.get("/api/health").json()
    assert body["status"] == "degraded"
    assert client.get("/api/news").status_code == 503

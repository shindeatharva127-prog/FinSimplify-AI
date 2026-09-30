"""
Service responsible for talking to NewsAPI (https://newsapi.org) and
normalizing its responses into our internal NewsArticle schema.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Optional

import httpx

from app.config import Settings
from app.models.schemas import NewsArticle, NewsTopic

logger = logging.getLogger("finsimplify.news_service")

# Maps our curated topic filters to NewsAPI-friendly query terms.
# NewsAPI's /v2/everything endpoint does not offer a dedicated "stock
# market" category, so we approximate each topic with a targeted keyword
# query rather than assuming such a feed exists.
TOPIC_QUERY_MAP: dict[str, str] = {
    NewsTopic.economy.value: "economy OR inflation OR GDP OR \"interest rates\"",
    NewsTopic.stock_market.value: "\"stock market\" OR shares OR equities OR Nasdaq OR \"S&P 500\"",
    NewsTopic.banking.value: "bank OR banking OR \"central bank\" OR lender",
    NewsTopic.business.value: "business OR corporate OR earnings OR company",
    NewsTopic.technology.value: "(technology OR tech) AND (business OR company OR earnings OR startup)",
    NewsTopic.global_news.value: "\"global economy\" OR \"world markets\" OR trade OR tariffs",
}

DEFAULT_FINANCE_QUERY = (
    "finance OR economy OR markets OR business OR banking OR investing"
)


class NewsServiceError(Exception):
    """Raised for any recoverable failure while fetching news."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _make_article_id(url: str, title: str) -> str:
    basis = (url or title).encode("utf-8", errors="ignore")
    return hashlib.sha256(basis).hexdigest()[:16]


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        # NewsAPI returns ISO-8601 like "2024-05-01T12:34:00Z"
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        logger.debug("Could not parse publish date: %s", value)
        return None


def _normalize_article(raw: dict) -> Optional[NewsArticle]:
    """Convert a raw NewsAPI article dict into our schema, or None if unusable."""
    title = (raw.get("title") or "").strip()
    url = (raw.get("url") or "").strip()

    # Skip articles NewsAPI marks as removed, or that lack the essentials.
    if not title or not url or title.lower() == "[removed]":
        return None

    source_obj = raw.get("source") or {}
    source_name = (source_obj.get("name") or "Unknown source").strip()

    return NewsArticle(
        id=_make_article_id(url, title),
        title=title,
        description=(raw.get("description") or "").strip() or None,
        content=(raw.get("content") or "").strip() or None,
        url=url,
        image_url=(raw.get("urlToImage") or None),
        source=source_name,
        published_at=_parse_datetime(raw.get("publishedAt")),
    )


def _deduplicate(articles: List[NewsArticle]) -> List[NewsArticle]:
    seen: set[str] = set()
    unique: List[NewsArticle] = []
    for article in articles:
        key = article.url.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(article)
    return unique


async def fetch_news(
    settings: Settings,
    query: Optional[str] = None,
    topic: Optional[str] = None,
    page_size: int = 12,
) -> tuple[List[NewsArticle], int]:
    """
    Fetch recent financial/business news from NewsAPI.

    Returns (articles, total_results). Raises NewsServiceError on failure.
    """
    if not settings.newsapi_configured:
        raise NewsServiceError(
            "NewsAPI is not configured. Set NEWSAPI_KEY in the environment.",
            status_code=503,
        )

    # Build the search query: explicit user query wins, else topic mapping,
    # else a broad default finance query so results are never empty by default.
    if query:
        search_terms = query
    elif topic and topic in TOPIC_QUERY_MAP:
        search_terms = TOPIC_QUERY_MAP[topic]
    else:
        search_terms = DEFAULT_FINANCE_QUERY

    params = {
        "q": search_terms,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": str(page_size),
        "apiKey": settings.NEWSAPI_KEY,
    }

    url = f"{settings.NEWSAPI_BASE_URL}/everything"

    try:
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
            response = await client.get(url, params=params)
    except httpx.TimeoutException as exc:
        raise NewsServiceError("NewsAPI request timed out. Please try again.", 504) from exc
    except httpx.RequestError as exc:
        raise NewsServiceError(f"Could not reach NewsAPI: network error.", 502) from exc

    if response.status_code == 401:
        raise NewsServiceError("NewsAPI rejected the API key (unauthorized).", 502)
    if response.status_code == 429:
        raise NewsServiceError("NewsAPI rate limit exceeded. Please try again later.", 429)
    if response.status_code >= 400:
        # Try to surface NewsAPI's own error message without leaking internals.
        try:
            payload = response.json()
            upstream_message = payload.get("message", "Unknown upstream error")
        except Exception:
            upstream_message = "Unknown upstream error"
        raise NewsServiceError(f"NewsAPI error: {upstream_message}", 502)

    try:
        data = response.json()
    except Exception as exc:
        raise NewsServiceError("NewsAPI returned an invalid response.", 502) from exc

    raw_articles = data.get("articles", []) or []
    total_results = int(data.get("totalResults", len(raw_articles)))

    normalized = [a for a in (_normalize_article(r) for r in raw_articles) if a is not None]
    deduped = _deduplicate(normalized)

    return deduped, total_results

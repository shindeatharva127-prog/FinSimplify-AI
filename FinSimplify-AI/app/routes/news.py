"""API routes: health, news retrieval, and AI summarization."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.models.schemas import HealthResponse, NewsResponse, NewsTopic, SummarizeRequest, SummarizeResponse
from app.services import ai_service, news_service

logger = logging.getLogger("finsimplify.routes")
router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    both_ok = settings.newsapi_configured and settings.groq_configured
    return HealthResponse(
        status="ok" if both_ok else "degraded",
        app_name=settings.APP_NAME,
        environment=settings.ENVIRONMENT,
        newsapi_configured=settings.newsapi_configured,
        groq_configured=settings.groq_configured,
        groq_model=settings.GROQ_MODEL,
    )


@router.get("/news", response_model=NewsResponse)
async def get_news(
    q: Optional[str] = Query(default=None, max_length=200),
    topic: Optional[NewsTopic] = Query(default=None),
    page_size: int = Query(default=12, ge=1),
    settings: Settings = Depends(get_settings),
) -> NewsResponse:
    if page_size > settings.MAX_PAGE_SIZE:
        raise HTTPException(status_code=400, detail=f"page_size must not exceed {settings.MAX_PAGE_SIZE}")

    q_clean = q.strip() if q else None
    if not q_clean:
        q_clean = None

    try:
        articles, total = await news_service.fetch_news(
            settings=settings, query=q_clean, topic=topic.value if topic else None, page_size=page_size
        )
    except news_service.NewsServiceError as exc:
        logger.warning("News fetch failed: %s", exc.message)
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return NewsResponse(total_results=total, articles=articles, query=q_clean, topic=topic.value if topic else None)


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize(payload: SummarizeRequest, settings: Settings = Depends(get_settings)) -> SummarizeResponse:
    try:
        return await ai_service.summarize_article(
            settings=settings,
            title=payload.title,
            description=payload.description or "",
            content=payload.content or "",
            url=payload.url or "",
        )
    except ai_service.AIServiceError as exc:
        logger.warning("Summarization failed: %s", exc.message)
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

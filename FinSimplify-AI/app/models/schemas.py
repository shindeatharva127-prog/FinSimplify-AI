"""Pydantic models shared across routes and services."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str
    newsapi_configured: bool
    groq_configured: bool
    groq_model: str


class NewsTopic(str, Enum):
    economy = "economy"
    stock_market = "stock_market"
    banking = "banking"
    business = "business"
    technology = "technology"
    global_news = "global_news"


class NewsArticle(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    content: Optional[str] = None
    url: str
    image_url: Optional[str] = None
    source: str
    published_at: Optional[datetime] = None


class NewsResponse(BaseModel):
    total_results: int
    articles: List[NewsArticle]
    query: Optional[str] = None
    topic: Optional[str] = None


class SummarizeRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(default="", max_length=6000)
    content: Optional[str] = Field(default="", max_length=6000)
    url: Optional[str] = Field(default="", max_length=2000)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be blank")
        return v.strip()


class Sentiment(str, Enum):
    positive = "positive"
    negative = "negative"
    neutral = "neutral"


class ImportantTerm(BaseModel):
    term: str
    explanation: str


class SummarizeResponse(BaseModel):
    simple_summary: str
    key_takeaways: List[str]
    why_it_matters: str
    topic: str
    sentiment: Sentiment
    important_terms: List[ImportantTerm]
    model_used: str
    disclaimer: str = (
        "AI-generated summary for educational purposes only. It may contain "
        "inaccuracies and is not personalized financial advice."
    )


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None

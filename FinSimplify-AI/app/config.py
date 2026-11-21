"""Application configuration. Secrets come only from environment variables / .env."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    """Read-only settings; values are read in __init__ so new instances reflect the current env."""

    APP_NAME: str = "FinSimplify AI"

    def __init__(self) -> None:
        self.NEWSAPI_KEY: str = os.getenv("NEWSAPI_KEY", "").strip()
        self.GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
        self.GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
        self.GROQ_API_BASE: str = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1").strip()
        self.NEWSAPI_BASE_URL: str = os.getenv("NEWSAPI_BASE_URL", "https://newsapi.org/v2").strip()
        self.ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").strip()
        self.HOST: str = os.getenv("HOST", "0.0.0.0").strip()
        self.PORT: int = int(os.getenv("PORT", "8000"))
        self.DEFAULT_PAGE_SIZE: int = int(os.getenv("DEFAULT_PAGE_SIZE", "12"))
        self.MAX_PAGE_SIZE: int = int(os.getenv("MAX_PAGE_SIZE", "50"))
        self.HTTP_TIMEOUT_SECONDS: float = float(os.getenv("HTTP_TIMEOUT_SECONDS", "12"))
        self.MAX_SUMMARIZE_FIELD_LENGTH: int = int(os.getenv("MAX_SUMMARIZE_FIELD_LENGTH", "6000"))
        raw_cors = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
        self.CORS_ALLOWED_ORIGINS: List[str] = _split_csv(raw_cors) if raw_cors else []
        self.CORS_ENABLED: bool = bool(self.CORS_ALLOWED_ORIGINS)

    @staticmethod
    def _is_real_key(value: str) -> bool:
        # Treat blank values and untouched .env.example placeholders as "not configured".
        return bool(value) and not value.lower().startswith("your_")

    @property
    def newsapi_configured(self) -> bool:
        return self._is_real_key(self.NEWSAPI_KEY)

    @property
    def groq_configured(self) -> bool:
        return self._is_real_key(self.GROQ_API_KEY)


@lru_cache
def get_settings() -> Settings:
    return Settings()

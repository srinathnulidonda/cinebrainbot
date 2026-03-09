# bot/config.py
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    BOT_TOKEN: str

    DATABASE_URL: str
    REDIS_URL: str

    TMDB_API_KEY: str
    TMDB_BASE_URL: str = "https://api.themoviedb.org/3"
    TMDB_IMG_BASE: str = "https://image.tmdb.org/t/p"

    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    MISTRAL_API_KEY: str = ""
    COHERE_API_KEY: str = ""
    HUGGINGFACE_API_KEY: str = ""
    CLOUDFLARE_ACCOUNT_ID: str = ""
    CLOUDFLARE_API_KEY: str = ""

    YOUTUBE_API_KEY: str
    YOUTUBE_BASE_URL: str = "https://www.googleapis.com/youtube/v3"

    STREAMING_API_KEY: str
    STREAMING_API_HOST: str = "streaming-availability.p.rapidapi.com"

    ADMIN_IDS: list[int] = []

    FREE_DAILY_SEARCHES: int = 10
    FREE_DAILY_EXPLAINS: int = 3
    FREE_DAILY_RECOMMENDS: int = 5
    FREE_WATCHLIST_LIMIT: int = 20
    REDEEM_HOURLY_LIMIT: int = 5
    REDEEM_DAILY_LIMIT: int = 10

    CACHE_MOVIE_TTL: int = 86400
    CACHE_SEARCH_TTL: int = 21600
    CACHE_STREAMING_TTL: int = 43200

    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 1800

    ITEMS_PER_PAGE: int = 5

    CHAT_SESSION_TTL: int = 86400
    CHAT_HISTORY_TTL: int = 604800
    CHAT_BLOCK_TTL: int = 604800
    CHAT_RATE_LIMIT_INTERVAL: int = 2
    CHAT_RATE_LIMIT_HOURLY: int = 30

    @property
    def async_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif not url.startswith("postgresql+asyncpg://"):
            url = f"postgresql+asyncpg://{url}"
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
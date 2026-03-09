# bot/services/backend_health.py
import logging
import time
import asyncio
from bot.models.engine import engine, redis_client
from bot.config import get_settings

logger = logging.getLogger(__name__)
_s = get_settings()


async def check_database() -> tuple[bool, int | None]:
    """Check PostgreSQL connection and return (ok, latency_ms)."""
    try:
        start = time.perf_counter()
        async with engine.connect() as conn:
            from sqlalchemy import text
            await conn.execute(text("SELECT 1"))
        latency = int((time.perf_counter() - start) * 1000)
        return True, latency
    except Exception as e:
        logger.error(f"DB health check failed: {e}")
        return False, None


async def check_redis() -> tuple[bool, int | None]:
    """Check Redis connection and return (ok, latency_ms)."""
    try:
        start = time.perf_counter()
        await redis_client.ping()
        latency = int((time.perf_counter() - start) * 1000)
        return True, latency
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return False, None


async def check_tmdb() -> tuple[bool, int | None]:
    """Check TMDB API and return (ok, latency_ms)."""
    try:
        import httpx
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{_s.TMDB_BASE_URL}/configuration",
                params={"api_key": _s.TMDB_API_KEY},
            )
            resp.raise_for_status()
        latency = int((time.perf_counter() - start) * 1000)
        return True, latency
    except Exception as e:
        logger.error(f"TMDB health check failed: {e}")
        return False, None


async def check_youtube() -> tuple[bool, int | None]:
    """Check YouTube API and return (ok, latency_ms)."""
    if not _s.YOUTUBE_API_KEY:
        return False, None
    try:
        import httpx
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{_s.YOUTUBE_BASE_URL}/videos",
                params={"key": _s.YOUTUBE_API_KEY, "part": "id", "chart": "mostPopular", "maxResults": 1},
            )
            resp.raise_for_status()
        latency = int((time.perf_counter() - start) * 1000)
        return True, latency
    except Exception as e:
        logger.error(f"YouTube health check failed: {e}")
        return False, None


async def get_db_pool_stats() -> dict:
    """Get database connection pool statistics."""
    try:
        pool = engine.pool
        return {
            "size": pool.size(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "checked_in": pool.checkedin(),
        }
    except Exception:
        return {}


async def get_redis_stats() -> dict:
    """Get Redis statistics."""
    try:
        info = await redis_client.info("memory")
        clients = await redis_client.info("clients")
        return {
            "memory": info.get("used_memory_human", "?"),
            "connections": clients.get("connected_clients", "?"),
        }
    except Exception:
        return {}


async def get_full_health() -> dict:
    """Get complete backend health status."""
    results = await asyncio.gather(
        check_database(),
        check_redis(),
        check_tmdb(),
        check_youtube(),
        get_db_pool_stats(),
        get_redis_stats(),
        return_exceptions=True,
    )

    db_ok, db_ms = results[0] if not isinstance(results[0], Exception) else (False, None)
    redis_ok, redis_ms = results[1] if not isinstance(results[1], Exception) else (False, None)
    tmdb_ok, tmdb_ms = results[2] if not isinstance(results[2], Exception) else (False, None)
    yt_ok, yt_ms = results[3] if not isinstance(results[3], Exception) else (False, None)
    pool_stats = results[4] if not isinstance(results[4], Exception) else {}
    redis_stats = results[5] if not isinstance(results[5], Exception) else {}

    return {
        "db": db_ok,
        "db_ms": db_ms,
        "redis": redis_ok,
        "redis_ms": redis_ms,
        "tmdb": tmdb_ok,
        "tmdb_ms": tmdb_ms,
        "youtube": yt_ok,
        "youtube_ms": yt_ms,
        "streaming": True,
        "db_pool_size": pool_stats.get("size"),
        "db_pool_checked": pool_stats.get("checked_out"),
        "redis_connections": redis_stats.get("connections"),
        "redis_memory": redis_stats.get("memory"),
    }
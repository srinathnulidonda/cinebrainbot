# bot/services/streaming_service.py
import logging
import json
import httpx
from bot.config import get_settings
from bot.models.engine import redis_client
from bot.services import tmdb_service

logger = logging.getLogger(__name__)
_s = get_settings()
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            limits=httpx.Limits(max_connections=30, max_keepalive_connections=10),
        )
    return _client


async def get_streaming_info(movie_id: int, country: str = "US") -> dict | None:
    cache_key = f"stream:{movie_id}:{country}"
    cached = await redis_client.get(cache_key)
    if cached:
        data = json.loads(cached)
        return data if data != "__NONE__" else None

    try:
        providers_data = await tmdb_service.get_watch_providers(movie_id)
        results = providers_data.get("results", {})
        country_data = results.get(country, results.get("US", {}))
        if not country_data:
            await redis_client.setex(cache_key, _s.CACHE_STREAMING_TTL, json.dumps("__NONE__"))
            return None
        result = {
            "link": country_data.get("link", ""),
            "flatrate": country_data.get("flatrate", []),
            "rent": country_data.get("rent", []),
            "buy": country_data.get("buy", []),
        }
        await redis_client.setex(cache_key, _s.CACHE_STREAMING_TTL, json.dumps(result))
        return result
    except Exception as e:
        logger.error(f"Failed to get streaming info for {movie_id}: {e}")
        return await _fallback_streaming(movie_id, country)


async def _fallback_streaming(movie_id: int, country: str) -> dict | None:
    cache_key = f"stream_api:{movie_id}:{country}"
    cached = await redis_client.get(cache_key)
    if cached:
        data = json.loads(cached)
        return data if data != "__NONE__" else None

    client = _get_client()
    try:
        resp = await client.get(
            f"https://{_s.STREAMING_API_HOST}/shows/movie/{movie_id}",
            headers={
                "X-RapidAPI-Key": _s.STREAMING_API_KEY,
                "X-RapidAPI-Host": _s.STREAMING_API_HOST,
            },
            params={"output_language": "en"},
        )
        if resp.status_code == 404:
            await redis_client.setex(cache_key, _s.CACHE_STREAMING_TTL, json.dumps("__NONE__"))
            return None
        resp.raise_for_status()
        data = resp.json()
        streaming = data.get("streamingInfo", {}).get(country.lower(), [])
        if not streaming:
            await redis_client.setex(cache_key, _s.CACHE_STREAMING_TTL, json.dumps("__NONE__"))
            return None
        result: dict = {"link": "", "flatrate": [], "rent": [], "buy": []}
        for s in streaming:
            stype = s.get("streamingType", "")
            provider = {"provider_name": s.get("service", "").title(), "provider_id": 0}
            if stype == "subscription":
                result["flatrate"].append(provider)
            elif stype == "rent":
                result["rent"].append(provider)
            elif stype == "buy":
                result["buy"].append(provider)
            if s.get("link") and not result["link"]:
                result["link"] = s["link"]
        await redis_client.setex(cache_key, _s.CACHE_STREAMING_TTL, json.dumps(result))
        return result
    except Exception as e:
        logger.error(f"Fallback streaming failed for {movie_id}: {e}")
        return None


async def close():
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
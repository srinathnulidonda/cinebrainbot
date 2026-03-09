# bot/services/tmdb_service.py
import logging
import json
import httpx
from typing import Any
from bot.config import get_settings
from bot.models.engine import redis_client
from bot import MovieNotFoundError, ExternalAPIError

logger = logging.getLogger(__name__)
_s = get_settings()

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=_s.TMDB_BASE_URL,
            params={"api_key": _s.TMDB_API_KEY, "language": "en-US"},
            timeout=httpx.Timeout(15.0, connect=5.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=30),
        )
    return _client


async def _request(path: str, params: dict | None = None, cache_key: str | None = None, ttl: int = 0) -> dict:
    if cache_key:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    client = _get_client()
    retries = 3
    for attempt in range(retries):
        try:
            resp = await client.get(path, params=params or {})
            if resp.status_code == 429:
                wait = min(2 ** attempt, 8)
                import asyncio
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            if cache_key and ttl:
                await redis_client.setex(cache_key, ttl, json.dumps(data))
            return data
        except httpx.TimeoutException:
            if attempt == retries - 1:
                raise ExternalAPIError("TMDb")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise MovieNotFoundError()
            if attempt == retries - 1:
                raise ExternalAPIError("TMDb")
        except Exception:
            if attempt == retries - 1:
                raise ExternalAPIError("TMDb")
    raise ExternalAPIError("TMDb")


async def search_movies(query: str, page: int = 1) -> dict:
    cache_key = f"tmdb:search:{query.lower().strip()}:{page}"
    data = await _request("/search/movie", {"query": query, "page": page}, cache_key, _s.CACHE_SEARCH_TTL)
    if not data.get("results"):
        raise MovieNotFoundError(query)
    return data


async def get_movie(movie_id: int) -> dict:
    cache_key = f"tmdb:movie:{movie_id}"
    return await _request(
        f"/movie/{movie_id}",
        {"append_to_response": "credits,release_dates,external_ids,keywords"},
        cache_key, _s.CACHE_MOVIE_TTL,
    )


async def get_movie_credits(movie_id: int) -> dict:
    cache_key = f"tmdb:credits:{movie_id}"
    return await _request(f"/movie/{movie_id}/credits", cache_key=cache_key, ttl=_s.CACHE_MOVIE_TTL)


async def get_similar(movie_id: int, page: int = 1) -> dict:
    cache_key = f"tmdb:similar:{movie_id}:{page}"
    return await _request(f"/movie/{movie_id}/similar", {"page": page}, cache_key, _s.CACHE_SEARCH_TTL)


async def get_recommendations(movie_id: int, page: int = 1) -> dict:
    cache_key = f"tmdb:recs:{movie_id}:{page}"
    return await _request(f"/movie/{movie_id}/recommendations", {"page": page}, cache_key, _s.CACHE_SEARCH_TTL)


async def discover_movies(
    genres: list[int] | None = None,
    sort_by: str = "popularity.desc",
    min_rating: float = 0,
    year: int | None = None,
    page: int = 1,
) -> dict:
    params: dict[str, Any] = {"sort_by": sort_by, "page": page, "vote_count.gte": 50}
    if genres:
        params["with_genres"] = ",".join(str(g) for g in genres)
    if min_rating:
        params["vote_average.gte"] = min_rating
    if year:
        params["primary_release_year"] = year
    genre_str = "_".join(str(g) for g in (genres or []))
    cache_key = f"tmdb:discover:{genre_str}:{sort_by}:{min_rating}:{year}:{page}"
    return await _request("/discover/movie", params, cache_key, _s.CACHE_SEARCH_TTL)


async def get_trending(time_window: str = "week", page: int = 1) -> dict:
    cache_key = f"tmdb:trending:{time_window}:{page}"
    return await _request(f"/trending/movie/{time_window}", {"page": page}, cache_key, _s.CACHE_SEARCH_TTL)


async def get_upcoming(page: int = 1) -> dict:
    cache_key = f"tmdb:upcoming:{page}"
    return await _request("/movie/upcoming", {"page": page, "region": "US"}, cache_key, _s.CACHE_SEARCH_TTL)


async def get_watch_providers(movie_id: int) -> dict:
    cache_key = f"tmdb:providers:{movie_id}"
    return await _request(f"/movie/{movie_id}/watch/providers", cache_key=cache_key, ttl=_s.CACHE_STREAMING_TTL)


async def get_movie_videos(movie_id: int) -> dict:
    cache_key = f"tmdb:videos:{movie_id}"
    return await _request(f"/movie/{movie_id}/videos", cache_key=cache_key, ttl=_s.CACHE_MOVIE_TTL)


async def multi_search(query: str) -> dict:
    cache_key = f"tmdb:multi:{query.lower().strip()}"
    return await _request("/search/multi", {"query": query}, cache_key, _s.CACHE_SEARCH_TTL)


async def get_poster_url(path: str | None, size: str = "w500") -> str | None:
    if not path:
        return None
    return f"{_s.TMDB_IMG_BASE}/{size}{path}"


async def close():
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
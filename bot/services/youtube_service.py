# bot/services/youtube_service.py
import logging
import json
import httpx
from bot.config import get_settings
from bot.models.engine import redis_client

logger = logging.getLogger(__name__)
_s = get_settings()
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=_s.YOUTUBE_BASE_URL,
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_connections=30, max_keepalive_connections=10),
        )
    return _client


async def find_trailer(movie_title: str, year: str = "") -> dict | None:
    cache_key = f"yt:trailer:{movie_title.lower()}:{year}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    query = f"{movie_title} {year} official trailer".strip()
    client = _get_client()
    for attempt in range(2):
        try:
            resp = await client.get("/search", params={
                "key": _s.YOUTUBE_API_KEY,
                "q": query,
                "part": "snippet",
                "type": "video",
                "maxResults": 1,
                "videoCategoryId": "1",
            })
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            if not items:
                return None
            item = items[0]
            result = {
                "video_id": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                "thumbnail": item["snippet"]["thumbnails"].get("high", {}).get("url", ""),
            }
            await redis_client.setex(cache_key, 86400, json.dumps(result))
            return result
        except Exception as e:
            logger.error(f"YouTube search attempt {attempt + 1} failed: {e}")
            if attempt == 1:
                return None
            import asyncio
            await asyncio.sleep(1)
    return None


async def find_trailer_from_tmdb(videos: dict) -> dict | None:
    results = videos.get("results", [])
    trailers = [v for v in results if v.get("type") == "Trailer" and v.get("site") == "YouTube"]
    if not trailers:
        trailers = [v for v in results if v.get("site") == "YouTube"]
    if not trailers:
        return None
    v = trailers[0]
    return {
        "video_id": v["key"],
        "title": v.get("name", "Trailer"),
        "url": f"https://www.youtube.com/watch?v={v['key']}",
        "thumbnail": f"https://img.youtube.com/vi/{v['key']}/hqdefault.jpg",
    }


async def close():
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
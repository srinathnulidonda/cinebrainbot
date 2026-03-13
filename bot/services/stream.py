# bot/services/stream.py
import logging
import json
import httpx
from datetime import datetime, timezone
from bot.config import get_settings
from bot.models.engine import redis_client

logger = logging.getLogger(__name__)
_s = get_settings()

VIDEASY_BASE = _s.VIDEASY_BASE_URL
VIDKING_BASE = _s.VIDKING_BASE_URL
FRONTEND_URL = _s.FRONTEND_URL

VIDEASY_PARAMS_MOVIE = "?color=e50914&overlay=true"
VIDEASY_PARAMS_TV = (
    "?color=e50914&nextEpisode=true"
    "&autoplayNextEpisode=true&overlay=true"
)

VIDKING_PARAMS_MOVIE = "?color=e50914&autoPlay=true"
VIDKING_PARAMS_TV = (
    "?color=e50914&autoPlay=true"
    "&nextEpisode=true&episodeSelector=true"
)

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
    return _client


def get_videasy_movie_embed_url(tmdb_id: int) -> str:
    return f"{VIDEASY_BASE}/movie/{tmdb_id}{VIDEASY_PARAMS_MOVIE}"


def get_videasy_tv_embed_url(tmdb_id: int, season: int, episode: int) -> str:
    return f"{VIDEASY_BASE}/tv/{tmdb_id}/{season}/{episode}{VIDEASY_PARAMS_TV}"


def get_vidking_movie_embed_url(tmdb_id: int) -> str:
    return f"{VIDKING_BASE}/embed/movie/{tmdb_id}{VIDKING_PARAMS_MOVIE}"


def get_vidking_tv_embed_url(tmdb_id: int, season: int, episode: int) -> str:
    return f"{VIDKING_BASE}/embed/tv/{tmdb_id}/{season}/{episode}{VIDKING_PARAMS_TV}"


def get_movie_embed_url(tmdb_id: int) -> str:
    return get_videasy_movie_embed_url(tmdb_id)


def get_tv_embed_url(tmdb_id: int, season: int, episode: int) -> str:
    return get_videasy_tv_embed_url(tmdb_id, season, episode)


def get_movie_player_url(tmdb_id: int) -> str:
    return f"{FRONTEND_URL}/movie/{tmdb_id}"


def get_tv_player_url(tmdb_id: int, season: int = 1, episode: int = 1) -> str:
    return f"{FRONTEND_URL}/tv/{tmdb_id}/{season}/{episode}"


async def get_movie_sources(tmdb_id: int) -> dict:
    cache_key = f"stream:sources:movie:{tmdb_id}:v2"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    result = {
        "tmdb_id": tmdb_id,
        "type": "movie",
        "default_server": "videasy",
        "sources": [
            {
                "server": "videasy",
                "name": "Server 1",
                "quality": "auto",
                "embed_url": get_videasy_movie_embed_url(tmdb_id),
                "player_url": get_movie_player_url(tmdb_id),
            },
            {
                "server": "vidking",
                "name": "Server 2",
                "quality": "auto",
                "embed_url": get_vidking_movie_embed_url(tmdb_id),
                "player_url": get_movie_player_url(tmdb_id),
            },
        ],
    }
    await redis_client.setex(cache_key, 3600, json.dumps(result))
    return result


async def get_tv_sources(tmdb_id: int, season: int, episode: int) -> dict:
    cache_key = f"stream:sources:tv:{tmdb_id}:{season}:{episode}:v2"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    result = {
        "tmdb_id": tmdb_id,
        "type": "tv",
        "season": season,
        "episode": episode,
        "default_server": "videasy",
        "sources": [
            {
                "server": "videasy",
                "name": "Server 1",
                "quality": "auto",
                "embed_url": get_videasy_tv_embed_url(tmdb_id, season, episode),
                "player_url": get_tv_player_url(tmdb_id, season, episode),
            },
            {
                "server": "vidking",
                "name": "Server 2",
                "quality": "auto",
                "embed_url": get_vidking_tv_embed_url(tmdb_id, season, episode),
                "player_url": get_tv_player_url(tmdb_id, season, episode),
            },
        ],
    }
    await redis_client.setex(cache_key, 3600, json.dumps(result))
    return result

async def get_tv_seasons(tmdb_id: int) -> dict | None:
    cache_key = f"stream:seasons:{tmdb_id}"
    cached = await redis_client.get(cache_key)
    if cached:
        data = json.loads(cached)
        return data if data != "__NONE__" else None

    client = _get_client()
    try:
        resp = await client.get(
            f"{_s.TMDB_BASE_URL}/tv/{tmdb_id}",
            params={"api_key": _s.TMDB_API_KEY, "language": "en-US"},
        )
        resp.raise_for_status()
        show = resp.json()

        seasons_data = []
        for s in show.get("seasons", []):
            sn = s.get("season_number", 0)
            if sn == 0:
                continue
            season_detail = await _fetch_season_detail(tmdb_id, sn)
            episodes = []
            if season_detail:
                for ep in season_detail.get("episodes", []):
                    episodes.append({
                        "episode_number": ep.get("episode_number"),
                        "name": ep.get("name", ""),
                        "overview": ep.get("overview", "")[:200],
                        "still_path": ep.get("still_path"),
                        "air_date": ep.get("air_date"),
                        "runtime": ep.get("runtime"),
                        "vote_average": ep.get("vote_average", 0),
                    })
            seasons_data.append({
                "season_number": sn,
                "name": s.get("name", f"Season {sn}"),
                "episode_count": s.get("episode_count", 0),
                "air_date": s.get("air_date"),
                "poster_path": s.get("poster_path"),
                "overview": s.get("overview", "")[:200],
                "episodes": episodes,
            })

        result = {
            "tmdb_id": tmdb_id,
            "name": show.get("name", ""),
            "poster_path": show.get("poster_path"),
            "backdrop_path": show.get("backdrop_path"),
            "number_of_seasons": show.get("number_of_seasons", 0),
            "number_of_episodes": show.get("number_of_episodes", 0),
            "status": show.get("status", ""),
            "vote_average": show.get("vote_average", 0),
            "genres": [g["name"] for g in show.get("genres", [])],
            "seasons": seasons_data,
        }
        await redis_client.setex(cache_key, 21600, json.dumps(result))
        return result
    except Exception as e:
        logger.error(f"Failed to fetch TV seasons for {tmdb_id}: {e}")
        await redis_client.setex(cache_key, 300, json.dumps("__NONE__"))
        return None


async def _fetch_season_detail(tmdb_id: int, season_number: int) -> dict | None:
    client = _get_client()
    try:
        resp = await client.get(
            f"{_s.TMDB_BASE_URL}/tv/{tmdb_id}/season/{season_number}",
            params={"api_key": _s.TMDB_API_KEY, "language": "en-US"},
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Failed to fetch season {season_number} for {tmdb_id}: {e}")
        return None

async def get_movie_info(tmdb_id: int) -> dict | None:
    cache_key = f"stream:info:movie:{tmdb_id}:v2"
    cached = await redis_client.get(cache_key)
    if cached:
        data = json.loads(cached)
        return data if data != "__NONE__" else None

    client = _get_client()
    try:
        resp = await client.get(
            f"{_s.TMDB_BASE_URL}/movie/{tmdb_id}",
            params={
                "api_key": _s.TMDB_API_KEY,
                "language": "en-US",
                "append_to_response": "credits,videos",
            },
        )
        resp.raise_for_status()
        movie = resp.json()

        directors = [
            c["name"]
            for c in movie.get("credits", {}).get("crew", [])
            if c.get("job") == "Director"
        ][:2]
        cast = [
            {"name": a["name"], "character": a.get("character", "")}
            for a in movie.get("credits", {}).get("cast", [])[:6]
        ]

        trailers = [
            v for v in movie.get("videos", {}).get("results", [])
            if v.get("type") == "Trailer" and v.get("site") == "YouTube"
        ]
        trailer_key = trailers[0]["key"] if trailers else None

        result = {
            "tmdb_id": tmdb_id,
            "type": "movie",
            "title": movie.get("title", ""),
            "overview": movie.get("overview", ""),
            "poster_path": movie.get("poster_path"),
            "backdrop_path": movie.get("backdrop_path"),
            "release_date": movie.get("release_date", ""),
            "runtime": movie.get("runtime"),
            "vote_average": movie.get("vote_average", 0),
            "vote_count": movie.get("vote_count", 0),
            "genres": [g["name"] for g in movie.get("genres", [])],
            "directors": directors,
            "cast": cast,
            "trailer_key": trailer_key,
            "player_url": get_movie_player_url(tmdb_id),
            "embed_url": get_videasy_movie_embed_url(tmdb_id),
            "servers": {
                "videasy": get_videasy_movie_embed_url(tmdb_id),
                "vidking": get_vidking_movie_embed_url(tmdb_id),
            },
        }
        await redis_client.setex(cache_key, 86400, json.dumps(result))
        return result
    except Exception as e:
        logger.error(f"Failed to fetch movie info for {tmdb_id}: {e}")
        return None


async def get_tv_info(tmdb_id: int) -> dict | None:
    cache_key = f"stream:info:tv:{tmdb_id}:v2"
    cached = await redis_client.get(cache_key)
    if cached:
        data = json.loads(cached)
        return data if data != "__NONE__" else None

    client = _get_client()
    try:
        resp = await client.get(
            f"{_s.TMDB_BASE_URL}/tv/{tmdb_id}",
            params={
                "api_key": _s.TMDB_API_KEY,
                "language": "en-US",
                "append_to_response": "credits,videos",
            },
        )
        resp.raise_for_status()
        show = resp.json()

        cast = [
            {"name": a["name"], "character": a.get("character", "")}
            for a in show.get("credits", {}).get("cast", [])[:6]
        ]
        creators = [c["name"] for c in show.get("created_by", [])][:3]

        trailers = [
            v for v in show.get("videos", {}).get("results", [])
            if v.get("type") == "Trailer" and v.get("site") == "YouTube"
        ]
        trailer_key = trailers[0]["key"] if trailers else None

        result = {
            "tmdb_id": tmdb_id,
            "type": "tv",
            "name": show.get("name", ""),
            "overview": show.get("overview", ""),
            "poster_path": show.get("poster_path"),
            "backdrop_path": show.get("backdrop_path"),
            "first_air_date": show.get("first_air_date", ""),
            "last_air_date": show.get("last_air_date", ""),
            "number_of_seasons": show.get("number_of_seasons", 0),
            "number_of_episodes": show.get("number_of_episodes", 0),
            "status": show.get("status", ""),
            "vote_average": show.get("vote_average", 0),
            "vote_count": show.get("vote_count", 0),
            "genres": [g["name"] for g in show.get("genres", [])],
            "creators": creators,
            "cast": cast,
            "trailer_key": trailer_key,
            "player_url": get_tv_player_url(tmdb_id),
            "embed_url": get_videasy_tv_embed_url(tmdb_id, 1, 1),
            "servers": {
                "videasy": get_videasy_tv_embed_url(tmdb_id, 1, 1),
                "vidking": get_vidking_tv_embed_url(tmdb_id, 1, 1),
            },
        }
        await redis_client.setex(cache_key, 86400, json.dumps(result))
        return result
    except Exception as e:
        logger.error(f"Failed to fetch TV info for {tmdb_id}: {e}")
        return None


async def save_progress(
    user_id: int, media_id: int, media_type: str,
    progress: float, current_time: float, duration: float,
    season: int | None = None, episode: int | None = None,
) -> dict:
    key = f"progress:{user_id}:{media_type}:{media_id}"
    if media_type == "tv" and season is not None and episode is not None:
        key = f"progress:{user_id}:tv:{media_id}:{season}:{episode}"

    data = {
        "user_id": user_id,
        "media_id": media_id,
        "media_type": media_type,
        "progress": min(100.0, max(0.0, progress)),
        "current_time": current_time,
        "duration": duration,
        "season": season,
        "episode": episode,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await redis_client.setex(key, 604800, json.dumps(data))

    list_key = f"progress:list:{user_id}"
    entry = f"{media_type}:{media_id}"
    if media_type == "tv" and season is not None:
        entry = f"tv:{media_id}:{season}:{episode}"
    await redis_client.sadd(list_key, entry)
    await redis_client.expire(list_key, 604800)

    return data


async def get_progress(
    user_id: int, media_id: int, media_type: str = "movie",
    season: int | None = None, episode: int | None = None,
) -> dict | None:
    key = f"progress:{user_id}:{media_type}:{media_id}"
    if media_type == "tv" and season is not None and episode is not None:
        key = f"progress:{user_id}:tv:{media_id}:{season}:{episode}"
    cached = await redis_client.get(key)
    if cached:
        return json.loads(cached)
    return None


async def close():
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
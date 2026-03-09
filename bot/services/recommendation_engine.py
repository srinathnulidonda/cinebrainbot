# bot/services/recommendation_engine.py
import logging
import random
from datetime import datetime
from bot.services import tmdb_service
from bot.services import ai_service
from bot.models.engine import get_session
from bot.models.watched import WatchedRepo
from bot.models.preference import PreferenceRepo
from bot.utils.constants import TMDB_GENRES, MOOD_MAP

logger = logging.getLogger(__name__)


async def get_user_context(user_db_id: int) -> tuple[dict, list[str], list[int]]:
    async with get_session() as session:
        prefs = await PreferenceRepo.get_or_create(session, user_db_id)
        recent = await WatchedRepo.get_recent(session, user_db_id, 30)
        watched_ids = await WatchedRepo.get_all_movie_ids(session, user_db_id)
        rating_stats = await WatchedRepo.get_rating_stats(session, user_db_id)
    watched_titles = [w.movie_title for w in recent]
    preferences = {
        "liked_genres": prefs.liked_genres or {},
        "liked_actors": prefs.liked_actors or {},
        "taste_vector": prefs.taste_vector or {},
        "avg_rating": rating_stats.get("avg", 0),
        "total_watched": rating_stats.get("count", 0),
    }
    return preferences, watched_titles, watched_ids


def _compute_confidence(movie: dict, preferences: dict) -> int:
    score = 50.0
    liked_genres = preferences.get("liked_genres", {})
    movie_genres = [str(g) for g in (movie.get("genre_ids") or [])]
    if not movie_genres and movie.get("genres"):
        movie_genres = [str(g["id"]) for g in movie["genres"]]
    total_genre_weight = sum(g.get("count", 0) for g in liked_genres.values()) or 1
    for gid in movie_genres:
        if gid in liked_genres:
            count = liked_genres[gid].get("count", 0)
            score += min(8, (count / total_genre_weight) * 25)
    rating = movie.get("vote_average", 0)
    if rating >= 8.0:
        score += 15
    elif rating >= 7.0:
        score += 10
    elif rating >= 6.0:
        score += 5
    votes = movie.get("vote_count", 0)
    if votes >= 5000:
        score += 5
    elif votes >= 1000:
        score += 4
    elif votes >= 500:
        score += 3
    elif votes >= 100:
        score += 1
    popularity = movie.get("popularity", 0)
    if popularity >= 100:
        score += 4
    elif popularity >= 50:
        score += 2
    year_str = movie.get("release_date", "")[:4]
    if year_str:
        try:
            age = datetime.now().year - int(year_str)
            if age <= 3:
                score += 3
            elif age <= 8:
                score += 1
        except ValueError:
            pass
    return min(99, max(60, int(score)))


def _ensure_diversity(movies: list[dict], max_per_genre: int = 2) -> list[dict]:
    genre_count: dict[int, int] = {}
    diverse: list[dict] = []
    overflow: list[dict] = []
    for m in movies:
        gids = m.get("genre_ids") or []
        primary = gids[0] if gids else 0
        if genre_count.get(primary, 0) < max_per_genre:
            diverse.append(m)
            genre_count[primary] = genre_count.get(primary, 0) + 1
        else:
            overflow.append(m)
    for m in overflow:
        if len(diverse) >= 5:
            break
        diverse.append(m)
    return diverse


async def recommend_by_mood(user_db_id: int, mood: str) -> list[dict]:
    preferences, watched_titles, watched_ids = await get_user_context(user_db_id)
    genre_ids = MOOD_MAP.get(mood, [35, 18])
    min_rating = max(6.0, preferences.get("avg_rating", 6.5) - 1.5)
    tmdb_results = []
    try:
        for page in random.sample(range(1, 6), min(3, 5)):
            data = await tmdb_service.discover_movies(
                genres=genre_ids[:2], min_rating=min_rating, page=page,
            )
            tmdb_results.extend(
                m for m in data.get("results", []) if m["id"] not in watched_ids
            )
            if len(tmdb_results) >= 15:
                break
    except Exception as e:
        logger.warning(f"TMDb discover failed for mood: {e}")
    ai_results = []
    try:
        ai_results = await ai_service.mood_recommendations(mood, preferences, watched_titles)
    except Exception as e:
        logger.warning(f"AI mood recs failed: {e}")
    return await _merge_results(tmdb_results, ai_results, watched_ids, preferences)


async def recommend_by_genre(user_db_id: int, genre_ids: list[int]) -> list[dict]:
    preferences, watched_titles, watched_ids = await get_user_context(user_db_id)
    min_rating = max(5.5, preferences.get("avg_rating", 6.0) - 2.0)
    tmdb_results = []
    try:
        for page in random.sample(range(1, 8), min(3, 7)):
            data = await tmdb_service.discover_movies(
                genres=genre_ids, min_rating=min_rating, page=page,
            )
            tmdb_results.extend(
                m for m in data.get("results", []) if m["id"] not in watched_ids
            )
            if len(tmdb_results) >= 15:
                break
    except Exception as e:
        logger.warning(f"TMDb discover failed: {e}")
    genre_names = [TMDB_GENRES.get(g, str(g)) for g in genre_ids]
    ai_results = []
    try:
        ai_results = await ai_service.get_recommendations(
            preferences, watched_titles, "genre",
            f"Focus on genres: {', '.join(genre_names)}",
        )
    except Exception as e:
        logger.warning(f"AI genre recs failed: {e}")
    return await _merge_results(tmdb_results, ai_results, watched_ids, preferences)


async def recommend_similar(user_db_id: int, movie_id: int) -> list[dict]:
    preferences, _, watched_ids = await get_user_context(user_db_id)
    tmdb_results = []
    try:
        data = await tmdb_service.get_similar(movie_id)
        tmdb_results = [m for m in data.get("results", []) if m["id"] not in watched_ids][:12]
    except Exception as e:
        logger.warning(f"TMDb similar failed: {e}")
    try:
        rec_data = await tmdb_service.get_recommendations(movie_id)
        seen_ids = {m["id"] for m in tmdb_results}
        extra = [
            m for m in rec_data.get("results", [])
            if m["id"] not in watched_ids and m["id"] not in seen_ids
        ]
        tmdb_results.extend(extra[:6])
    except Exception:
        pass
    for m in tmdb_results:
        m["confidence"] = _compute_confidence(m, preferences)
    tmdb_results.sort(key=lambda m: m.get("confidence", 0), reverse=True)
    return _ensure_diversity(tmdb_results)[:5]


async def recommend_surprise(user_db_id: int) -> list[dict]:
    preferences, watched_titles, watched_ids = await get_user_context(user_db_id)
    tmdb_results = []
    try:
        source = random.choice(["trending", "discover", "discover"])
        if source == "trending":
            data = await tmdb_service.get_trending("week", random.randint(1, 3))
        else:
            data = await tmdb_service.discover_movies(
                sort_by="popularity.desc",
                min_rating=7.0,
                page=random.randint(1, 15),
            )
        tmdb_results = [m for m in data.get("results", []) if m["id"] not in watched_ids]
        random.shuffle(tmdb_results)
        tmdb_results = tmdb_results[:12]
    except Exception as e:
        logger.warning(f"TMDb surprise failed: {e}")
    ai_results = []
    try:
        ai_results = await ai_service.get_recommendations(
            preferences, watched_titles, "surprise",
            "Surprise them with unexpected but great picks across different genres and eras. "
            "Include hidden gems and critically acclaimed films they likely haven't seen.",
        )
    except Exception as e:
        logger.warning(f"AI surprise failed: {e}")
    return await _merge_results(tmdb_results, ai_results, watched_ids, preferences)


async def get_random_movie(genre_id: int | None = None) -> dict | None:
    try:
        genres = [genre_id] if genre_id else None
        page = random.randint(1, 20)
        data = await tmdb_service.discover_movies(
            genres=genres, sort_by="popularity.desc", min_rating=5.5, page=page,
        )
        results = data.get("results", [])
        if results:
            return random.choice(results)
    except Exception as e:
        logger.error(f"Random movie failed: {e}")
    return None


async def _merge_results(
    tmdb_results: list[dict],
    ai_results: list[dict],
    watched_ids: list[int],
    preferences: dict,
) -> list[dict]:
    scored: list[dict] = []
    seen_ids: set[int] = set()

    for m in tmdb_results:
        mid = m.get("id")
        if mid and mid not in watched_ids and mid not in seen_ids:
            m["confidence"] = _compute_confidence(m, preferences)
            scored.append(m)
            seen_ids.add(mid)

    for ai_rec in ai_results:
        if len(scored) >= 15:
            break
        title = ai_rec.get("title", "")
        if not title:
            continue
        try:
            search = await tmdb_service.search_movies(f"{title} {ai_rec.get('year', '')}")
            results = search.get("results", [])
            if results:
                tmdb_movie = results[0]
                mid = tmdb_movie["id"]
                if mid not in watched_ids and mid not in seen_ids:
                    base = _compute_confidence(tmdb_movie, preferences)
                    ai_conf = ai_rec.get("confidence", 75)
                    tmdb_movie["confidence"] = min(99, (base + ai_conf) // 2 + 5)
                    tmdb_movie["ai_reason"] = ai_rec.get("reason", "")
                    scored.append(tmdb_movie)
                    seen_ids.add(mid)
        except Exception:
            continue

    scored.sort(key=lambda m: m.get("confidence", 0), reverse=True)
    diverse = _ensure_diversity(scored)
    return diverse[:5]
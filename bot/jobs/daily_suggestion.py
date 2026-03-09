# bot/jobs/daily_suggestion.py
import logging
import random
from telegram.ext import ContextTypes
from bot.models.engine import get_session
from bot.models.user import UserRepo
from bot.models.watched import WatchedRepo
from bot.models.preference import PreferenceRepo
from bot.models.database import SubscriptionTier
from bot.services import recommendation_engine, tmdb_service
from bot.utils.formatters import format_movie_short
from bot.utils.keyboards import movie_detail_kb
from bot.utils.constants import E_SPARKLE, E_MOVIE, TMDB_GENRES

logger = logging.getLogger(__name__)


async def daily_suggestion_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Running daily suggestion job")
    async with get_session() as session:
        pro_ids = await UserRepo.get_pro_user_ids(session)
        free_ids = await UserRepo.get_all_user_ids(session)
    all_ids = list(set(pro_ids + random.sample(free_ids, min(len(free_ids), len(free_ids) // 5 + 1))))
    sent, failed = 0, 0

    for telegram_id in all_ids:
        try:
            async with get_session() as session:
                user = await UserRepo.get_by_telegram_id(session, telegram_id)
                if not user:
                    continue
                prefs = await PreferenceRepo.get_or_create(session, user.id)
                watched_ids = await WatchedRepo.get_all_movie_ids(session, user.id)

            liked_genres = prefs.liked_genres or {}
            genre_ids = []
            if liked_genres:
                sorted_genres = sorted(liked_genres.items(), key=lambda x: x[1].get("count", 0), reverse=True)
                genre_ids = [int(gid) for gid, _ in sorted_genres[:3]]
            elif user.preferred_genres:
                reverse_map = {v: k for k, v in TMDB_GENRES.items()}
                genre_ids = [reverse_map[g] for g in user.preferred_genres if g in reverse_map][:3]

            movie = None
            if genre_ids:
                page = random.randint(1, 5)
                try:
                    data = await tmdb_service.discover_movies(
                        genres=genre_ids[:2], min_rating=6.5, page=page,
                    )
                    candidates = [m for m in data.get("results", []) if m["id"] not in watched_ids]
                    if candidates:
                        movie = random.choice(candidates)
                except Exception:
                    pass

            if not movie:
                try:
                    data = await tmdb_service.get_trending("day", 1)
                    candidates = [m for m in data.get("results", []) if m["id"] not in watched_ids]
                    if candidates:
                        movie = random.choice(candidates[:10])
                except Exception:
                    pass

            if not movie:
                continue

            title = movie.get("title", "Unknown")
            year = movie.get("release_date", "")[:4]
            rating = movie.get("vote_average", 0)
            overview = movie.get("overview", "")[:200]
            genres = ", ".join(TMDB_GENRES.get(g, "") for g in movie.get("genre_ids", []) if g in TMDB_GENRES)

            text = (
                f"{E_SPARKLE} <b>Your Daily Movie Pick</b> {E_MOVIE}\n\n"
                f"🎬 <b>{title}</b> ({year})\n"
                f"⭐ {rating:.1f}/10\n"
                f"🎭 {genres}\n\n"
                f"📝 {overview}{'...' if len(movie.get('overview', '')) > 200 else ''}\n\n"
                f"<i>Picked just for you based on your taste! 🍿</i>"
            )

            kb = movie_detail_kb(movie["id"])
            await context.bot.send_message(
                telegram_id, text, parse_mode="HTML",
                reply_markup=kb, disable_web_page_preview=True,
            )
            sent += 1
        except Exception as e:
            logger.debug(f"Daily suggestion failed for {telegram_id}: {e}")
            failed += 1

    logger.info(f"Daily suggestion job complete: sent={sent}, failed={failed}")
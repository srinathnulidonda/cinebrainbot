# bot/handlers/stats.py
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from bot.middleware.subscription_check import ensure_user
from bot.middleware.analytics import track_command
from bot.models.engine import get_session
from bot.models.watched import WatchedRepo
from bot.utils.formatters import format_stats, build_genre_bars
from bot.utils.constants import MSG_WATCHED_EMPTY

logger = logging.getLogger(__name__)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    user_db_id = context.user_data.get("db_user_id", 0)

    async with get_session() as session:
        total = await WatchedRepo.count(session, user_db_id)
        if total == 0:
            await update.message.reply_text(MSG_WATCHED_EMPTY, parse_mode="HTML")
            return
        rating_stats = await WatchedRepo.get_rating_stats(session, user_db_id)
        genre_counts = await WatchedRepo.get_genre_stats(session, user_db_id)
        recent = await WatchedRepo.get_recent(session, user_db_id, 50)

    best = "N/A"
    if recent:
        rated = [m for m in recent if m.user_rating]
        if rated:
            best_movie = max(rated, key=lambda m: m.user_rating)
            best = f"{best_movie.movie_title} ({best_movie.user_rating}/10)"

    month_counts: dict[str, int] = {}
    for m in recent:
        if m.watched_at:
            month_key = m.watched_at.strftime("%b %Y")
            month_counts[month_key] = month_counts.get(month_key, 0) + 1
    active_month = max(month_counts, key=month_counts.get) if month_counts else "N/A"

    stats = {
        "total_watched": total,
        "avg_rating": rating_stats["avg"],
        "best": best,
        "active_month": active_month,
        "genre_bars": build_genre_bars(genre_counts),
    }
    text = format_stats(stats)
    await update.message.reply_text(text, parse_mode="HTML")


def get_handlers() -> list:
    return [CommandHandler("stats", stats_command)]
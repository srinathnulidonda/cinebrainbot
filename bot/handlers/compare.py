# bot/handlers/compare.py
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from bot.middleware.subscription_check import ensure_user
from bot.middleware.analytics import track_command
from bot.services import tmdb_service
from bot.services import ai_service
from bot.utils.formatters import format_comparison
from bot.utils.validators import parse_compare_query
from bot.utils.constants import E_TROPHY, LINE
from bot import CineBotError

logger = logging.getLogger(__name__)


async def compare_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text(
            f"{E_TROPHY} <b>COMPARE MOVIES</b>\n"
            f"{LINE}\n\n"
            "Usage: <code>/compare Movie A vs Movie B</code>\n\n"
            "💡 <code>/compare Inception vs Interstellar</code>",
            parse_mode="HTML",
        )
        return
    parsed = parse_compare_query(query)
    if not parsed:
        await update.message.reply_text(
            "❌ Use '<b>vs</b>' to separate movies\n\n"
            "💡 <code>/compare Inception vs Interstellar</code>",
            parse_mode="HTML",
        )
        return

    title_a, title_b = parsed
    loading = await update.message.reply_text(
        f"{E_TROPHY} <b>{title_a}</b> ⚔️ <b>{title_b}</b>\n\n⏳ Analyzing...",
        parse_mode="HTML",
    )

    try:
        data_a = await tmdb_service.search_movies(title_a)
        data_b = await tmdb_service.search_movies(title_b)
        results_a = data_a.get("results", [])
        results_b = data_b.get("results", [])
        if not results_a or not results_b:
            await loading.edit_text(
                "❌ Couldn't find one or both movies 🙈", parse_mode="HTML",
            )
            return
        movie_a = await tmdb_service.get_movie(results_a[0]["id"])
        movie_b = await tmdb_service.get_movie(results_b[0]["id"])
        comparison_text = format_comparison(movie_a, movie_b)

        movie_a["genres_text"] = ", ".join(g["name"] for g in movie_a.get("genres", []))
        movie_b["genres_text"] = ", ".join(g["name"] for g in movie_b.get("genres", []))

        try:
            ai_analysis = await ai_service.compare_movies(movie_a, movie_b)
            comparison_text += f"\n\n─── ◆ AI Analysis ◆ ───\n{ai_analysis}"
        except Exception:
            pass

        await loading.edit_text(comparison_text, parse_mode="HTML")
    except CineBotError as e:
        await loading.edit_text(e.user_message, parse_mode="HTML")


def get_handlers() -> list:
    return [CommandHandler("compare", compare_command)]
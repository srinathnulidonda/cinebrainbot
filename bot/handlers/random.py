# bot/handlers/random.py
import logging
import asyncio
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from bot.middleware.subscription_check import ensure_user
from bot.middleware.analytics import track_command
from bot.services import recommendation_engine, tmdb_service
from bot.utils.formatters import format_movie_card
from bot.utils.keyboards import random_filter_kb, movie_detail_kb
from bot.utils.constants import E_DICE, TMDB_GENRES, LINE
from bot.models.engine import get_session
from bot.models.watchlist import WatchlistRepo
from bot import CineBotError

logger = logging.getLogger(__name__)


async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    await update.message.reply_text(
        f"{E_DICE} <b>RANDOM PICK</b>\n"
        f"{LINE}\n\n"
        "Choose a genre or go random:",
        reply_markup=random_filter_kb(),
        parse_mode="HTML",
    )


async def random_genre_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    genre_str = query.data.split(":")[1]
    genre_id = None if genre_str == "any" else int(genre_str)
    genre_name = TMDB_GENRES.get(genre_id, "Any Genre") if genre_id else "Any Genre"
    await ensure_user(update, context)

    frames = ["🎰 Spinning...", "🎰 Spinning... 🎬", "🎰 Spinning... 🎬🎬", "🎰 Spinning... 🎬🎬🎬"]
    await query.edit_message_text(frames[0], parse_mode="HTML")
    for frame in frames[1:]:
        await asyncio.sleep(0.35)
        try:
            await query.edit_message_text(frame, parse_mode="HTML")
        except Exception:
            break

    try:
        movie = await recommendation_engine.get_random_movie(genre_id)
        if not movie:
            await query.edit_message_text(
                "😕 Couldn't find a movie. Try again! 🎲", parse_mode="HTML",
            )
            return
        movie_detail = await tmdb_service.get_movie(movie["id"])
        card = format_movie_card(movie_detail)
        text = f"{E_DICE} <b>Random {genre_name} Pick!</b>\n\n{card}"

        user_db_id = context.user_data.get("db_user_id", 0)
        in_watchlist = False
        if user_db_id:
            async with get_session() as session:
                in_watchlist = await WatchlistRepo.exists(session, user_db_id, movie["id"])

        kb = movie_detail_kb(movie["id"], in_watchlist)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    except CineBotError as e:
        await query.edit_message_text(e.user_message, parse_mode="HTML")


def get_handlers() -> list:
    return [
        CommandHandler("random", random_command),
        CallbackQueryHandler(random_genre_callback, pattern=r"^random_genre:"),
    ]
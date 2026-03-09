# bot/handlers/search.py
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from bot.middleware.subscription_check import ensure_user
from bot.middleware.rate_limiter import check_rate_limit, increment_usage
from bot.middleware.analytics import track_command
from bot.services import tmdb_service
from bot.models.engine import get_session
from bot.models.user import UserRepo
from bot.models.watchlist import WatchlistRepo
from bot.utils.formatters import format_movie_card, format_movie_credits, format_no_results
from bot.utils.keyboards import movie_detail_kb, search_results_kb, no_results_kb
from bot.utils.validators import validate_movie_title
from bot.utils.constants import E_SEARCH, LINE
from bot import MovieNotFoundError, CineBotError

logger = logging.getLogger(__name__)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)

    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text(
            f"{E_SEARCH} <b>SEARCH</b>\n"
            f"{LINE}\n\n"
            f"Usage: <code>/search Movie Name</code>\n"
            f"Example: <code>/search Inception</code>\n\n"
            "💡 Or just type any movie name!",
            parse_mode="HTML",
        )
        return

    title = validate_movie_title(query)
    if not title:
        await update.message.reply_text(
            format_no_results(query), reply_markup=no_results_kb(), parse_mode="HTML",
        )
        return

    telegram_id = update.effective_user.id
    async with get_session() as session:
        user = await UserRepo.get_by_telegram_id(session, telegram_id)
    is_pro = user.is_pro if user else False
    await check_rate_limit(telegram_id, "search", is_pro)

    loading = await update.message.reply_text(
        f"{E_SEARCH} Searching \"<b>{title}</b>\"...", parse_mode="HTML",
    )

    try:
        data = await tmdb_service.search_movies(title)
        results = data.get("results", [])
        if not results:
            await loading.edit_text(
                format_no_results(title), reply_markup=no_results_kb(), parse_mode="HTML",
            )
            return
        await increment_usage(telegram_id, "search")

        if len(results) == 1 or results[0].get("vote_count", 0) > 100:
            await _show_movie_detail(loading, results[0]["id"], user.id if user else 0)
        else:
            count = min(len(results), 8)
            await loading.edit_text(
                f"{E_SEARCH} <b>{count} results</b> for \"<b>{title}</b>\"\n{LINE}\n\nSelect a movie:",
                reply_markup=search_results_kb(results),
                parse_mode="HTML",
            )
    except MovieNotFoundError:
        await loading.edit_text(
            format_no_results(title), reply_markup=no_results_kb(), parse_mode="HTML",
        )
    except CineBotError as e:
        await loading.edit_text(e.user_message, parse_mode="HTML")


async def movie_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    movie_id = int(query.data.split(":")[1])
    await ensure_user(update, context)
    user_db_id = context.user_data.get("db_user_id", 0)
    await _show_movie_detail(query.message, movie_id, user_db_id, edit=True)


async def _show_movie_detail(message, movie_id: int, user_db_id: int, edit: bool = True) -> None:
    try:
        movie = await tmdb_service.get_movie(movie_id)
        card_text = format_movie_card(movie)
        credits = movie.get("credits")
        if credits:
            credits_text = format_movie_credits(credits)
            if credits_text:
                card_text += f"\n\n{credits_text}"

        in_watchlist = False
        if user_db_id:
            async with get_session() as session:
                in_watchlist = await WatchlistRepo.exists(session, user_db_id, movie_id)

        kb = movie_detail_kb(movie_id, in_watchlist)
        poster_url = await tmdb_service.get_poster_url(movie.get("poster_path"))

        if edit:
            try:
                await message.edit_text(card_text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await message.reply_text(card_text, reply_markup=kb, parse_mode="HTML")
        else:
            if poster_url:
                try:
                    await message.reply_photo(
                        poster_url, caption=card_text[:1024], reply_markup=kb, parse_mode="HTML",
                    )
                    return
                except Exception:
                    pass
            await message.reply_text(card_text, reply_markup=kb, parse_mode="HTML")
    except CineBotError as e:
        text = e.user_message
        if edit:
            await message.edit_text(text, parse_mode="HTML")
        else:
            await message.reply_text(text, parse_mode="HTML")


async def similar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Loading similar... 🎬")
    movie_id = int(query.data.split(":")[1])
    try:
        data = await tmdb_service.get_similar(movie_id)
        results = data.get("results", [])[:6]
        if not results:
            await query.answer("No similar movies found 🙈", show_alert=True)
            return
        await query.message.reply_text(
            f"🔍 <b>Similar Movies</b>\n{LINE}",
            reply_markup=search_results_kb(results),
            parse_mode="HTML",
        )
    except Exception:
        await query.answer("Failed to load 🙈", show_alert=True)


def get_handlers() -> list:
    return [
        CommandHandler("search", search_command),
        CallbackQueryHandler(movie_detail_callback, pattern=r"^movie:\d+$"),
        CallbackQueryHandler(similar_callback, pattern=r"^similar:\d+$"),
    ]
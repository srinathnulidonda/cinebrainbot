# bot/handlers/watchlist.py
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from bot.middleware.subscription_check import ensure_user
from bot.middleware.analytics import track_command
from bot.models.engine import get_session
from bot.models.user import UserRepo
from bot.models.watchlist import WatchlistRepo
from bot.models.database import Priority
from bot.services import tmdb_service
from bot.utils.formatters import format_watchlist_item
from bot.utils.keyboards import pagination_kb, priority_kb, search_results_kb, rate_limit_kb
from bot.utils.constants import E_LIST, E_CHECK, FREE_LIMITS, MSG_WATCHLIST_EMPTY, LINE
from bot.utils.pagination import AsyncPaginator
from bot import CineBotError
from bot.config import get_settings

logger = logging.getLogger(__name__)
_s = get_settings()


async def watchlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    args = context.args or []
    if args and args[0].lower() == "add" and len(args) > 1:
        query = " ".join(args[1:])
        await _watchlist_search(update, context, query)
        return
    if args and args[0].lower() == "remove" and len(args) > 1:
        try:
            movie_id = int(args[1])
            await _watchlist_remove(update, context, movie_id)
        except ValueError:
            await update.message.reply_text("❌ Usage: /watchlist remove <movie_id>", parse_mode="HTML")
        return
    await _show_watchlist(update, context, page=1)


async def _show_watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1, message=None) -> None:
    user_db_id = context.user_data.get("db_user_id", 0)
    async with get_session() as session:
        items, total = await WatchlistRepo.get_paginated(session, user_db_id, page, _s.ITEMS_PER_PAGE)
    if not items and page == 1:
        target = message or update.message or update.callback_query.message
        if message:
            await target.edit_text(MSG_WATCHLIST_EMPTY, parse_mode="HTML")
        else:
            await target.reply_text(MSG_WATCHLIST_EMPTY, parse_mode="HTML")
        return

    pag = AsyncPaginator(items, total, page, _s.ITEMS_PER_PAGE)
    lines = [
        f"{E_LIST} <b>WATCHLIST</b> ({total} movies)",
        LINE,
        "",
    ]
    offset = (page - 1) * _s.ITEMS_PER_PAGE
    for i, item in enumerate(items, offset + 1):
        lines.append(format_watchlist_item(item, i))
    lines.append(f"\n📄 {pag.info}")
    text = "\n".join(lines)
    kb = pagination_kb("wl", page, pag.total_pages)

    target = message or update.message or update.callback_query.message
    if message:
        await target.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def _watchlist_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
    try:
        data = await tmdb_service.search_movies(query)
        results = data.get("results", [])[:6]
        if not results:
            from bot.utils.formatters import format_no_results
            from bot.utils.keyboards import no_results_kb
            await update.message.reply_text(
                format_no_results(query), reply_markup=no_results_kb(), parse_mode="HTML",
            )
            return
        await update.message.reply_text(
            f"{E_LIST} Select a movie to save:",
            reply_markup=search_results_kb(results),
            parse_mode="HTML",
        )
    except CineBotError as e:
        await update.message.reply_text(e.user_message, parse_mode="HTML")


async def _watchlist_remove(update: Update, context: ContextTypes.DEFAULT_TYPE, movie_id: int) -> None:
    user_db_id = context.user_data.get("db_user_id", 0)
    async with get_session() as session:
        removed = await WatchlistRepo.remove(session, user_db_id, movie_id)
    if removed:
        await update.message.reply_text(f"{E_CHECK} Removed! 🍿", parse_mode="HTML")
    else:
        await update.message.reply_text("❌ Not in your watchlist 🙈", parse_mode="HTML")


async def wl_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    movie_id = int(query.data.split(":")[1])
    await ensure_user(update, context)
    user_db_id = context.user_data.get("db_user_id", 0)
    is_pro = context.user_data.get("is_pro", False)

    async with get_session() as session:
        if await WatchlistRepo.exists(session, user_db_id, movie_id):
            await query.answer("Already saved! 📋", show_alert=True)
            return
        count = await WatchlistRepo.count(session, user_db_id)
        if not is_pro and count >= FREE_LIMITS["watchlist"]:
            await query.answer(
                f"Watchlist full ({FREE_LIMITS['watchlist']}). Upgrade to 👑 Pro!",
                show_alert=True,
            )
            return

    try:
        movie = await tmdb_service.get_movie(movie_id)
        async with get_session() as session:
            await WatchlistRepo.add(
                session, user_db_id, movie_id,
                movie.get("title", "Unknown"),
                movie.get("poster_path"),
            )
        await query.answer("Added! 🍿")
        from bot.utils.keyboards import movie_detail_kb
        kb = movie_detail_kb(movie_id, in_watchlist=True)
        try:
            await query.edit_message_reply_markup(reply_markup=kb)
        except Exception:
            pass
    except CineBotError as e:
        await query.answer(e.user_message, show_alert=True)


async def wl_remove_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    movie_id = int(query.data.split(":")[1])
    await ensure_user(update, context)
    user_db_id = context.user_data.get("db_user_id", 0)

    async with get_session() as session:
        await WatchlistRepo.remove(session, user_db_id, movie_id)
    await query.answer("Removed! 🗑️")
    from bot.utils.keyboards import movie_detail_kb
    kb = movie_detail_kb(movie_id, in_watchlist=False)
    try:
        await query.edit_message_reply_markup(reply_markup=kb)
    except Exception:
        pass


async def wl_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":")[2])
    await ensure_user(update, context)
    await _show_watchlist(update, context, page, message=query.message)


async def priority_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts = query.data.split(":")
    movie_id = int(parts[1])
    priority_str = parts[2]
    user_db_id = context.user_data.get("db_user_id", 0)
    priority = Priority(priority_str)
    async with get_session() as session:
        await WatchlistRepo.update_priority(session, user_db_id, movie_id, priority)
    emoji = {"HIGH": "🔴", "MED": "🟡", "LOW": "🟢"}.get(priority_str, "⚪")
    await query.answer(f"Priority: {emoji} {priority_str}")


def get_handlers() -> list:
    return [
        CommandHandler("watchlist", watchlist_command),
        CallbackQueryHandler(wl_add_callback, pattern=r"^wl_add:\d+$"),
        CallbackQueryHandler(wl_remove_callback, pattern=r"^wl_remove:\d+$"),
        CallbackQueryHandler(wl_page_callback, pattern=r"^wl:page:\d+$"),
        CallbackQueryHandler(priority_callback, pattern=r"^pri:\d+:(HIGH|MED|LOW)$"),
    ]
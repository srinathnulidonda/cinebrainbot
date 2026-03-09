# bot/handlers/alerts.py
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from bot.middleware.subscription_check import ensure_user
from bot.middleware.analytics import track_command
from bot.models.engine import get_session
from bot.models.alert import AlertRepo
from bot.services import tmdb_service
from bot.utils.keyboards import alert_list_kb
from bot.utils.constants import E_BELL, E_CHECK, LINE
from bot.utils.pagination import AsyncPaginator
from bot.config import get_settings
from bot import CineBotError

logger = logging.getLogger(__name__)
_s = get_settings()


async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    await _show_alerts(update, context, 1)


async def _show_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int, message=None) -> None:
    user_db_id = context.user_data.get("db_user_id", 0)
    async with get_session() as session:
        items, total = await AlertRepo.get_user_alerts(session, user_db_id, page, _s.ITEMS_PER_PAGE)
    if not items and page == 1:
        text = (
            f"{E_BELL} <b>No alerts set</b>\n\n"
            "Use the 🔔 button on any movie to get notified!\n\n"
            "💡 /search a movie to set an alert"
        )
        target = message or update.message or update.callback_query.message
        if message:
            await target.edit_text(text, parse_mode="HTML")
        else:
            await target.reply_text(text, parse_mode="HTML")
        return
    pag = AsyncPaginator(items, total, page, _s.ITEMS_PER_PAGE)
    lines = [
        f"{E_BELL} <b>RELEASE ALERTS</b> ({total})",
        LINE,
        "",
    ]
    for a in items:
        date_str = a.release_date.strftime("%Y-%m-%d") if a.release_date else "TBD"
        status = "✅ Notified" if a.notified else f"📅 {date_str}"
        lines.append(f"  🎬 <b>{a.movie_title}</b> — {status}")
    lines.append(f"\n📄 {pag.info}")
    lines.append("Tap to remove:")
    text = "\n".join(lines)
    kb = alert_list_kb(items, page, pag.total_pages)
    target = message or update.message or update.callback_query.message
    if message:
        await target.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def alert_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    movie_id = int(query.data.split(":")[1])
    await ensure_user(update, context)
    user_db_id = context.user_data.get("db_user_id", 0)

    async with get_session() as session:
        if await AlertRepo.exists(session, user_db_id, movie_id):
            await query.answer("Alert already set! 🔔", show_alert=True)
            return
    try:
        movie = await tmdb_service.get_movie(movie_id)
        release_date = None
        rd_str = movie.get("release_date", "")
        if rd_str:
            try:
                release_date = datetime.strptime(rd_str, "%Y-%m-%d")
            except ValueError:
                pass
        async with get_session() as session:
            await AlertRepo.create(session, user_db_id, movie_id, movie.get("title", "Unknown"), release_date)
        title = movie.get("title", "movie")
        await query.answer(f"🔔 Alert set for {title}!")
    except CineBotError as e:
        await query.answer(e.user_message, show_alert=True)


async def alert_remove_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    movie_id = int(query.data.split(":")[1])
    await ensure_user(update, context)
    user_db_id = context.user_data.get("db_user_id", 0)

    async with get_session() as session:
        removed = await AlertRepo.remove(session, user_db_id, movie_id)
    if removed:
        await query.answer("Removed! 🗑️")
        await _show_alerts(update, context, 1, message=query.message)
    else:
        await query.answer("Alert not found 🙈", show_alert=True)


async def alerts_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":")[2])
    await ensure_user(update, context)
    await _show_alerts(update, context, page, message=query.message)


def get_handlers() -> list:
    return [
        CommandHandler("alerts", alerts_command),
        CallbackQueryHandler(alert_add_callback, pattern=r"^alert_add:\d+$"),
        CallbackQueryHandler(alert_remove_callback, pattern=r"^alert_rm:\d+$"),
        CallbackQueryHandler(alerts_page_callback, pattern=r"^alerts:page:\d+$"),
    ]
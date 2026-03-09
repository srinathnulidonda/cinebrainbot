# bot/handlers/start.py
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from bot.models.engine import get_session
from bot.models.user import UserRepo
from bot.middleware.subscription_check import ensure_user
from bot.middleware.analytics import track_command
from bot.utils.constants import (
    MSG_WELCOME, MSG_HELP, MSG_ONBOARDING_GENRES,
    E_CROWN, E_CHECK, E_INFO, E_SEARCH, E_ROBOT, E_LIST, E_BRAIN,
    LINE, LINE_LIGHT, BADGE_PRO, FREE_LIMITS,
)
from bot.utils.formatters import format_pro_status, format_free_status
from bot.utils.keyboards import genre_select_kb, pro_upgrade_kb

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    async with get_session() as session:
        user = await UserRepo.get_by_telegram_id(session, update.effective_user.id)
    if user and not user.onboarding_completed:
        context.user_data["selected_genres"] = set()
        await update.message.reply_text(
            MSG_ONBOARDING_GENRES,
            reply_markup=genre_select_kb(),
            parse_mode="HTML",
        )
        return
    await update.message.reply_text(MSG_WELCOME, parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    await update.message.reply_text(MSG_HELP, parse_mode="HTML")


async def genre_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    selected = context.user_data.get("selected_genres", set())

    if data.startswith("genre_sel:"):
        genre_id = int(data.split(":")[1])
        if genre_id in selected:
            selected.discard(genre_id)
        else:
            selected.add(genre_id)
        context.user_data["selected_genres"] = selected
        await query.edit_message_reply_markup(reply_markup=genre_select_kb(selected))

    elif data == "genre_done":
        if len(selected) < 2:
            await query.answer("Pick at least 2 genres! 🎭", show_alert=True)
            return
        from bot.utils.constants import TMDB_GENRES
        genre_names = [TMDB_GENRES[gid] for gid in selected if gid in TMDB_GENRES]
        async with get_session() as session:
            await UserRepo.set_preferred_genres(session, update.effective_user.id, genre_names)
            await UserRepo.complete_onboarding(session, update.effective_user.id)
        context.user_data.pop("selected_genres", None)
        tags = " ".join(f"⌈{g}⌋" for g in genre_names)
        await query.edit_message_text(
            f"{E_CHECK} <b>Great taste!</b>\n\n"
            f"Your genres: {tags}\n\n"
            f"{LINE_LIGHT}\n"
            f"{MSG_WELCOME}",
            parse_mode="HTML",
        )


async def pro_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    async with get_session() as session:
        user = await UserRepo.get_by_telegram_id(session, update.effective_user.id)
    if not user:
        return

    from bot.middleware.rate_limiter import get_all_usage
    from bot.models.watchlist import WatchlistRepo
    usage = await get_all_usage(update.effective_user.id)
    async with get_session() as session:
        wl_count = await WatchlistRepo.count(session, user.id)

    if user.is_pro:
        text = format_pro_status(user, usage, wl_count)
        await update.message.reply_text(text, parse_mode="HTML")
    else:
        text = format_free_status(usage, wl_count)
        await update.message.reply_text(text, reply_markup=pro_upgrade_kb(), parse_mode="HTML")


def get_handlers() -> list:
    return [
        CommandHandler("start", start_command),
        CommandHandler("help", help_command),
        CommandHandler("pro", pro_command),
        CallbackQueryHandler(genre_select_callback, pattern=r"^genre_(sel|done)"),
    ]
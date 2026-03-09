# bot/handlers/callbacks.py
import logging
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from bot.middleware.subscription_check import ensure_user
from bot.services import tmdb_service, youtube_service
from bot.utils.constants import LINE

logger = logging.getLogger(__name__)


async def trailer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Finding trailer... 🎥")
    movie_id = int(query.data.split(":")[1])
    try:
        videos = await tmdb_service.get_movie_videos(movie_id)
        trailer = await youtube_service.find_trailer_from_tmdb(videos)
        if not trailer:
            movie = await tmdb_service.get_movie(movie_id)
            title = movie.get("title", "Unknown")
            year = movie.get("release_date", "")[:4]
            trailer = await youtube_service.find_trailer(title, year)
        if trailer:
            await query.message.reply_text(
                f"🎥 <b>TRAILER</b>\n"
                f"{LINE}\n\n"
                f"{trailer['title']}\n"
                f"{trailer['url']}",
                parse_mode="HTML",
                disable_web_page_preview=False,
            )
        else:
            await query.answer("No trailer found 🙈", show_alert=True)
    except Exception as e:
        logger.error(f"Trailer fetch failed: {e}")
        await query.answer("Failed to load trailer 🙈", show_alert=True)


async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()


async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Cancelled.")
    await query.edit_message_text("❌ Cancelled.", parse_mode="HTML")


async def back_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    from bot.utils.constants import MSG_WELCOME
    await query.edit_message_text(MSG_WELCOME, parse_mode="HTML")


async def contact_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📞 <b>CONTACT ADMIN</b>\n"
        f"{LINE}\n\n"
        "Send your message:\n"
        "<code>/contact Your message here</code>\n\n"
        "💡 <code>/contact I want to buy Pro</code>",
        parse_mode="HTML",
    )


async def unknown_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query:
        await query.answer()


def get_handlers() -> list:
    return [
        CallbackQueryHandler(trailer_callback, pattern=r"^trailer:\d+$"),
        CallbackQueryHandler(noop_callback, pattern=r"^noop$"),
        CallbackQueryHandler(cancel_callback, pattern=r"^cancel$"),
        CallbackQueryHandler(back_main_callback, pattern=r"^back_main$"),
        CallbackQueryHandler(contact_admin_callback, pattern=r"^contact:admin$"),
    ]
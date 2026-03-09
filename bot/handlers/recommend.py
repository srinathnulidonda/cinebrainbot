# bot/handlers/recommend.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from bot.middleware.subscription_check import ensure_user
from bot.middleware.rate_limiter import check_rate_limit, increment_usage
from bot.middleware.analytics import track_command
from bot.services import recommendation_engine, tmdb_service
from bot.models.engine import get_session
from bot.models.user import UserRepo
from bot.utils.formatters import format_recommendation_list
from bot.utils.keyboards import recommend_type_kb, mood_kb, search_results_kb
from bot.utils.constants import E_BRAIN, TMDB_GENRES, LINE
from bot import CineBotError

logger = logging.getLogger(__name__)


def _rec_genre_kb(selected: set[int] | None = None) -> InlineKeyboardMarkup:
    selected = selected or set()
    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for gid, name in sorted(TMDB_GENRES.items(), key=lambda x: x[1]):
        prefix = "✅ " if gid in selected else ""
        row.append(InlineKeyboardButton(f"{prefix}{name}", callback_data=f"rg_sel:{gid}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("✅ Done", callback_data="rg_done")])
    return InlineKeyboardMarkup(buttons)


async def recommend_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    telegram_id = update.effective_user.id
    async with get_session() as session:
        user = await UserRepo.get_by_telegram_id(session, telegram_id)
    is_pro = user.is_pro if user else False
    await check_rate_limit(telegram_id, "recommend", is_pro)
    await update.message.reply_text(
        f"{E_BRAIN} <b>RECOMMENDATIONS</b>\n"
        f"{LINE}\n\n"
        "How would you like your picks?",
        reply_markup=recommend_type_kb(),
        parse_mode="HTML",
    )


async def rec_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    rec_type = query.data.split(":")[1]
    await ensure_user(update, context)

    if rec_type == "mood":
        await query.edit_message_text(
            "😊 <b>What's your mood?</b>\n"
            f"{LINE}\n\n"
            "Pick one and I'll find the perfect match:",
            reply_markup=mood_kb(),
            parse_mode="HTML",
        )
    elif rec_type == "genre":
        context.user_data["rec_genres"] = set()
        await query.edit_message_text(
            "🎭 <b>SELECT GENRES</b>\n"
            f"{LINE}\n\n"
            "Pick genres for your recommendations:",
            reply_markup=_rec_genre_kb(),
            parse_mode="HTML",
        )
    elif rec_type == "similar":
        context.user_data["awaiting_similar_movie"] = True
        await query.edit_message_text(
            f"{E_BRAIN} <b>SIMILAR MOVIES</b>\n"
            f"{LINE}\n\n"
            "Type the name of a movie you love:",
            parse_mode="HTML",
        )
    elif rec_type == "surprise":
        await _generate_and_send(query, update.effective_user.id, "surprise")


async def rec_genre_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    genre_id = int(query.data.split(":")[1])
    selected = context.user_data.get("rec_genres", set())
    if genre_id in selected:
        selected.discard(genre_id)
    else:
        selected.add(genre_id)
    context.user_data["rec_genres"] = selected
    await query.edit_message_reply_markup(reply_markup=_rec_genre_kb(selected))


async def rec_genre_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    selected = context.user_data.get("rec_genres", set())
    if not selected:
        await query.answer("Pick at least one genre! 🎭", show_alert=True)
        return
    await query.answer()
    telegram_id = update.effective_user.id
    genre_ids = list(selected)
    context.user_data.pop("rec_genres", None)
    await _generate_genre_recs(query, telegram_id, genre_ids)


async def rec_mood_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    mood = query.data.split(":", 1)[1]
    telegram_id = update.effective_user.id
    await _generate_mood_recs(query, telegram_id, mood)


async def _generate_and_send(query, telegram_id: int, mode: str) -> None:
    await query.edit_message_text(
        f"{E_BRAIN} Finding your perfect picks...\n⏳ This may take a moment",
        parse_mode="HTML",
    )
    try:
        async with get_session() as session:
            user = await UserRepo.get_by_telegram_id(session, telegram_id)
        user_db_id = user.id if user else 0
        movies = await recommendation_engine.recommend_surprise(user_db_id)
        await increment_usage(telegram_id, "recommend")
        if not movies:
            await query.edit_message_text(
                "😕 Couldn't generate picks. Try again! 🎬", parse_mode="HTML",
            )
            return
        text = format_recommendation_list(movies, "🎲 Surprise Picks")
        kb = search_results_kb(movies) if movies else None
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    except CineBotError as e:
        await query.edit_message_text(e.user_message, parse_mode="HTML")


async def _generate_genre_recs(query, telegram_id: int, genre_ids: list[int]) -> None:
    genre_names = [TMDB_GENRES.get(g, "?") for g in genre_ids]
    tags = " ".join(f"⌈{n}⌋" for n in genre_names)
    await query.edit_message_text(
        f"{E_BRAIN} Finding movies in {tags}...\n⏳ This may take a moment",
        parse_mode="HTML",
    )
    try:
        async with get_session() as session:
            user = await UserRepo.get_by_telegram_id(session, telegram_id)
        user_db_id = user.id if user else 0
        movies = await recommendation_engine.recommend_by_genre(user_db_id, genre_ids)
        await increment_usage(telegram_id, "recommend")
        if not movies:
            await query.edit_message_text(
                f"😕 No picks for {tags}. Try different genres! 🎭", parse_mode="HTML",
            )
            return
        text = format_recommendation_list(movies, f"🎭 {', '.join(genre_names)}")
        kb = search_results_kb(movies) if movies else None
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    except CineBotError as e:
        await query.edit_message_text(e.user_message, parse_mode="HTML")


async def _generate_mood_recs(query, telegram_id: int, mood: str) -> None:
    await query.edit_message_text(
        f"{E_BRAIN} Matching your {mood} vibe...\n⏳ This may take a moment",
        parse_mode="HTML",
    )
    try:
        async with get_session() as session:
            user = await UserRepo.get_by_telegram_id(session, telegram_id)
        user_db_id = user.id if user else 0
        movies = await recommendation_engine.recommend_by_mood(user_db_id, mood)
        await increment_usage(telegram_id, "recommend")
        if not movies:
            await query.edit_message_text(
                "😕 No mood-based picks found. Try again! 🎬", parse_mode="HTML",
            )
            return
        text = format_recommendation_list(movies, f"{mood} Picks")
        kb = search_results_kb(movies) if movies else None
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    except CineBotError as e:
        await query.edit_message_text(e.user_message, parse_mode="HTML")


def get_handlers() -> list:
    return [
        CommandHandler("recommend", recommend_command),
        CallbackQueryHandler(rec_type_callback, pattern=r"^rec_type:"),
        CallbackQueryHandler(rec_genre_select_callback, pattern=r"^rg_sel:\d+$"),
        CallbackQueryHandler(rec_genre_done_callback, pattern=r"^rg_done$"),
        CallbackQueryHandler(rec_mood_callback, pattern=r"^mood:"),
    ]
# bot/handlers/contact.py
import logging
import re
from telegram import Update, Message
from telegram.ext import ContextTypes, CommandHandler
from bot.middleware.subscription_check import ensure_user
from bot.middleware.analytics import track_command
from bot.services import chat_service
from bot.config import get_settings
from bot.utils.constants import E_CHECK, E_CROSS, E_PHONE, E_WARN, LINE, LINE_LIGHT, BADGE_PRO
from bot.utils.validators import sanitize_html

logger = logging.getLogger(__name__)
_s = get_settings()


def _format_admin_header(chat_id: int, ctx: dict, message_text: str = "") -> str:
    display = sanitize_html(ctx.get("display_name", "Unknown"))
    username = f"@{ctx['username']}" if ctx.get("username") else "N/A"
    tier = f"👑 PRO" if ctx.get("is_pro") else "📋 FREE"
    watched = ctx.get("watched_count", 0)
    watchlist = ctx.get("watchlist_count", 0)
    user_id = ctx.get("user_id", 0)
    stats = f"{watched} watched · {watchlist} queued"
    lines = [
        f"💬 #{chat_id}",
        LINE,
        f"👤 {display} ({username})",
        f"🆔 {user_id}",
        f"{tier} · {stats}",
        LINE,
    ]
    if message_text:
        lines.append(message_text)
    return "\n".join(lines)


async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    user_id = update.effective_user.id

    if await chat_service.is_blocked(user_id):
        await update.message.reply_text(
            f"{E_CROSS} You are currently blocked from support.\n"
            "Please try again later.",
            parse_mode="HTML",
        )
        return

    if await chat_service.is_in_chat(user_id):
        await update.message.reply_text(
            f"{E_PHONE} You're already in a chat session.\n\n"
            "Just type your message here.\n"
            "Use /endchat when done.",
            parse_mode="HTML",
        )
        return

    chat_id = await chat_service.start_chat(user_id)
    ctx = await chat_service.get_user_context(user_id)

    await update.message.reply_text(
        f"{E_CHECK} <b>LIVE CHAT STARTED</b>\n"
        f"{LINE}\n\n"
        "You're now connected to support.\n"
        "Type your message and we'll respond here.\n\n"
        "📎 You can send text, photos, videos, docs & voice.\n"
        "Use /endchat to close this session.",
        parse_mode="HTML",
    )

    header = _format_admin_header(chat_id, ctx, "📩 <b>New chat session started</b>")
    from bot.utils.keyboards import support_admin_kb
    kb = support_admin_kb(chat_id, user_id)

    for admin_id in _s.ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id, header, reply_markup=kb, parse_mode="HTML",
            )
        except Exception as e:
            logger.debug(f"Failed to notify admin {admin_id}: {e}")

    await chat_service.save_message(chat_id, "system", "Chat session started")


async def endchat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    user_id = update.effective_user.id

    chat_id = await chat_service.get_chat_id(user_id)
    closed = await chat_service.end_chat(user_id)

    if closed:
        await update.message.reply_text(
            f"{E_CHECK} <b>Chat ended.</b>\n\n"
            "Thanks for reaching out!\n"
            "Use /chat anytime to start a new session.",
            parse_mode="HTML",
        )
        if chat_id:
            await chat_service.save_message(int(chat_id), "system", "User ended chat")
            for admin_id in _s.ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        admin_id,
                        f"💬 #{chat_id}\n{LINE}\n\n"
                        f"👤 User ended the chat session.",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
    else:
        await update.message.reply_text(
            "You don't have an active chat session.\n"
            "Use /chat to start one.",
            parse_mode="HTML",
        )


async def user_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    user_id = update.effective_user.id
    chat_id = await chat_service.get_chat_id(user_id)
    if not chat_id:
        return

    if not await chat_service.check_rate_limit(user_id):
        await update.message.reply_text(
            "⏳ Slow down — try again in a moment.",
            parse_mode="HTML",
        )
        return

    ctx = await chat_service.get_user_context(user_id)
    text = update.message.text or update.message.caption or ""
    header = _format_admin_header(chat_id, ctx, sanitize_html(text) if text else "")

    from bot.utils.keyboards import support_admin_kb
    kb = support_admin_kb(chat_id, user_id)

    await chat_service.save_message(chat_id, "user", text)

    for admin_id in _s.ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id, header, reply_markup=kb, parse_mode="HTML",
            )
        except Exception as e:
            logger.debug(f"Failed to forward to admin {admin_id}: {e}")


async def user_chat_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    user_id = update.effective_user.id
    chat_id = await chat_service.get_chat_id(user_id)
    if not chat_id:
        return

    if not await chat_service.check_rate_limit(user_id):
        await update.message.reply_text(
            "⏳ Slow down — try again in a moment.",
            parse_mode="HTML",
        )
        return

    msg = update.message
    media_type = None
    media_id = None
    if msg.photo:
        media_type = "photo"
        media_id = msg.photo[-1].file_id
    elif msg.video:
        media_type = "video"
        media_id = msg.video.file_id
    elif msg.document:
        media_type = "document"
        media_id = msg.document.file_id
    elif msg.voice:
        media_type = "voice"
        media_id = msg.voice.file_id
    elif msg.video_note:
        media_type = "video_note"
        media_id = msg.video_note.file_id
    elif msg.sticker:
        media_type = "sticker"
        media_id = msg.sticker.file_id
    elif msg.audio:
        media_type = "audio"
        media_id = msg.audio.file_id
    elif msg.animation:
        media_type = "animation"
        media_id = msg.animation.file_id

    if not media_type or not media_id:
        return

    caption = msg.caption or ""
    ctx = await chat_service.get_user_context(user_id)
    header = _format_admin_header(chat_id, ctx, sanitize_html(caption) if caption else f"[{media_type}]")

    from bot.utils.keyboards import support_admin_kb
    kb = support_admin_kb(chat_id, user_id)

    await chat_service.save_message(chat_id, "user", caption, media_type, media_id)

    send_map = {
        "photo": "send_photo",
        "video": "send_video",
        "document": "send_document",
        "voice": "send_voice",
        "video_note": "send_video_note",
        "audio": "send_audio",
        "animation": "send_animation",
        "sticker": "send_sticker",
    }

    for admin_id in _s.ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id, header, reply_markup=kb, parse_mode="HTML",
            )
            send_method = getattr(context.bot, send_map.get(media_type, "send_document"))
            if media_type in ("video_note", "sticker"):
                await send_method(admin_id, media_id)
            else:
                await send_method(
                    admin_id, media_id,
                    caption=f"💬 #{chat_id} · 📎 {media_type}" if media_type != "sticker" else None,
                )
        except Exception as e:
            logger.debug(f"Failed to forward media to admin {admin_id}: {e}")


def get_handlers() -> list:
    return [
        CommandHandler(["chat", "support", "contact"], chat_command),
        CommandHandler("endchat", endchat_command),
    ]
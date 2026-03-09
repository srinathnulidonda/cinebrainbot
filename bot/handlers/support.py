# bot/handlers/support.py
import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from bot.middleware.admin_check import admin_only
from bot.middleware.subscription_check import ensure_user
from bot.middleware.analytics import track_command
from bot.services import chat_service, key_service
from bot.config import get_settings
from bot.utils.constants import (
    E_CHECK, E_CROSS, E_PHONE, E_PERSON, E_CROWN, E_KEY, E_SHIELD,
    LINE, LINE_LIGHT, KEY_TYPES, BADGE_PRO,
)
from bot.utils.validators import sanitize_html

logger = logging.getLogger(__name__)
_s = get_settings()

_CANNED = {
    "greet": "👋 Hi there! Thanks for reaching out. How can I help you today?",
    "wait": "⏳ Please hold on — I'm looking into this for you.",
    "plans": (
        "👑 <b>CineBot Pro Plans:</b>\n\n"
        "💎 1 Month · 💎 2 Months · 💎 3 Months\n"
        "💎 6 Months · 💎 1 Year\n\n"
        "All plans include unlimited searches, recommendations, "
        "explanations, and watchlist. Reply to purchase!"
    ),
    "thanks": "🙏 You're welcome! Anything else I can help with?",
    "bye": "👋 Glad I could help! Use /chat anytime you need us. Enjoy your movies! 🍿",
    "key_sent": "🔑 Your Pro key has been sent! Use /redeem to activate it. Enjoy! ✨",
}

_USER_ID_RE = re.compile(r"🆔\s*(\d+)")


def _parse_user_id_from_reply(message) -> int | None:
    if not message:
        return None
    text = message.text or message.caption or ""
    match = _USER_ID_RE.search(text)
    if match:
        return int(match.group(1))
    return None


def _parse_chat_id_from_reply(message) -> int | None:
    if not message:
        return None
    text = message.text or message.caption or ""
    match = re.search(r"💬\s*#(\d+)", text)
    if match:
        return int(match.group(1))
    return None


@admin_only
async def chats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    active = await chat_service.get_active_chats()

    if not active:
        await update.message.reply_text(
            f"{E_PHONE} <b>No active chats</b>\n\n"
            "All quiet! 🎬",
            parse_mode="HTML",
        )
        return

    lines = [
        f"{E_PHONE} <b>ACTIVE CHATS</b> ({len(active)})",
        LINE,
        "",
    ]
    for ch in active[:20]:
        cid = ch.get("chat_id", "?")
        uid = ch.get("user_id", "?")
        status = ch.get("status", "?")
        msgs = ch.get("message_count", "0")
        status_dot = {"active": "🟢", "hold": "🟡", "closed": "⚪"}.get(status, "⚪")
        ctx = await chat_service.get_user_context(int(uid)) if uid != "?" else {}
        name = sanitize_html(ctx.get("display_name", uid))
        tier = "👑" if ctx.get("is_pro") else "📋"
        lines.append(f"  {status_dot} <b>#{cid}</b> · {name} · {tier} · {msgs} msgs")

    lines.append(f"\n{LINE_LIGHT}")
    lines.append("Reply to any forwarded message to respond.")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def _send_to_user(context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str) -> bool:
    try:
        await context.bot.send_message(
            user_id,
            f"🤖 <b>Support</b>\n{LINE}\n\n{text}",
            parse_mode="HTML",
        )
        return True
    except Exception as e:
        logger.warning(f"Failed to send to user {user_id}: {e}")
        return False


async def _send_media_to_user(
    context: ContextTypes.DEFAULT_TYPE, user_id: int,
    media_type: str, media_id: str, caption: str = "",
) -> bool:
    try:
        formatted_caption = f"🤖 <b>Support</b>\n{LINE}\n\n{caption}" if caption else f"🤖 <b>Support</b>"
        send_map = {
            "photo": context.bot.send_photo,
            "video": context.bot.send_video,
            "document": context.bot.send_document,
            "voice": context.bot.send_voice,
            "video_note": context.bot.send_video_note,
            "audio": context.bot.send_audio,
            "animation": context.bot.send_animation,
            "sticker": context.bot.send_sticker,
        }
        send_fn = send_map.get(media_type)
        if not send_fn:
            return False
        if media_type in ("video_note", "sticker"):
            await send_fn(user_id, media_id)
        else:
            await send_fn(user_id, media_id, caption=formatted_caption, parse_mode="HTML")
        return True
    except Exception as e:
        logger.warning(f"Failed to send media to user {user_id}: {e}")
        return False


async def admin_text_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.message or not update.message.reply_to_message:
        return False

    admin_id = update.effective_user.id
    if admin_id not in _s.ADMIN_IDS:
        return False

    user_id = _parse_user_id_from_reply(update.message.reply_to_message)
    if not user_id:
        return False

    chat_id = await chat_service.get_chat_id(user_id)
    reply_text = update.message.text or ""

    if not reply_text.strip():
        return False

    sent = await _send_to_user(context, user_id, sanitize_html(reply_text))
    if sent:
        if chat_id:
            await chat_service.save_message(chat_id, "admin", reply_text)
        await update.message.reply_text(
            f"{E_CHECK} Sent to user <code>{user_id}</code>",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            f"{E_CROSS} Failed to deliver to <code>{user_id}</code>",
            parse_mode="HTML",
        )
    return True


async def admin_media_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.message or not update.message.reply_to_message:
        return False

    admin_id = update.effective_user.id
    if admin_id not in _s.ADMIN_IDS:
        return False

    user_id = _parse_user_id_from_reply(update.message.reply_to_message)
    if not user_id:
        return False

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
        return False

    caption = msg.caption or ""
    chat_id = await chat_service.get_chat_id(user_id)
    sent = await _send_media_to_user(context, user_id, media_type, media_id, sanitize_html(caption))

    if sent:
        if chat_id:
            await chat_service.save_message(chat_id, "admin", caption, media_type, media_id)
        await update.message.reply_text(
            f"{E_CHECK} Media sent to <code>{user_id}</code>",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            f"{E_CROSS} Failed to deliver media to <code>{user_id}</code>",
            parse_mode="HTML",
        )
    return True


async def sr_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts = query.data.split(":")
    chat_id = int(parts[1])
    user_id = int(parts[2])
    await query.answer("Type your reply to the message above ↑")


async def sp_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts = query.data.split(":")
    user_id = int(parts[1])
    await query.answer()
    lines = [
        f"{E_CROWN} <b>PLANS</b> → <code>{user_id}</code>",
        LINE,
        "",
    ]
    for k, v in KEY_TYPES.items():
        lines.append(f"  💎 <b>{v['label']}</b> ({v['days']}d)")
    lines.append(f"\n{LINE_LIGHT}")
    lines.append(f"Use /giftkey {user_id} TYPE to gift directly.")
    await query.message.reply_text("\n".join(lines), parse_mode="HTML")


async def sg_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts = query.data.split(":")
    user_id = int(parts[1])
    await query.answer()
    buttons = [
        [InlineKeyboardButton(
            f"💎 {v['label']} ({v['days']}d)",
            callback_data=f"sgt:{user_id}:{k}",
        )]
        for k, v in KEY_TYPES.items()
    ]
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    await query.message.reply_text(
        f"🎁 <b>GIFT PRO</b> → <code>{user_id}</code>\n{LINE}\n\nSelect duration:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML",
    )


async def sgt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts = query.data.split(":")
    user_id = int(parts[1])
    key_type = parts[2]
    admin_id = query.from_user.id
    await query.answer()

    try:
        result = await key_service.gift_key(admin_id, user_id, key_type)
        await query.edit_message_text(
            f"🎁 <b>PRO GIFTED!</b>\n{LINE}\n\n"
            f"User: {result['user']} ({result['telegram_id']})\n"
            f"Duration: <b>{result['duration']}</b>\n"
            f"Key: <code>{result['key']}</code>",
            parse_mode="HTML",
        )
        try:
            await context.bot.send_message(
                user_id,
                f"🤖 <b>Support</b>\n{LINE}\n\n"
                f"🎁 You've been upgraded to <b>Pro</b>!\n"
                f"Duration: <b>{result['duration']}</b>\n\n"
                "Use /pro to check your status. Enjoy! ✨",
                parse_mode="HTML",
            )
        except Exception:
            pass
        chat_id = await chat_service.get_chat_id(user_id)
        if chat_id:
            await chat_service.save_message(chat_id, "admin", f"Gifted Pro: {result['duration']}")
    except Exception as e:
        await query.edit_message_text(f"{E_CROSS} Error: {e}", parse_mode="HTML")


async def si_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts = query.data.split(":")
    user_id = int(parts[1])
    await query.answer()
    ctx = await chat_service.get_user_context(user_id)
    display = sanitize_html(ctx.get("display_name", "?"))
    username = f"@{ctx['username']}" if ctx.get("username") else "N/A"
    tier = f"👑 PRO" if ctx.get("is_pro") else "📋 FREE"
    lines = [
        f"{E_PERSON} <b>USER INFO</b>",
        LINE,
        "",
        f"👤 {display} ({username})",
        f"🆔 <code>{user_id}</code>",
        f"Plan: <b>{tier}</b>",
        f"🎬 Watched: <b>{ctx.get('watched_count', 0)}</b>",
        f"📋 Watchlist: <b>{ctx.get('watchlist_count', 0)}</b>",
        f"📅 Joined: {ctx.get('joined', 'N/A')}",
    ]
    await query.message.reply_text("\n".join(lines), parse_mode="HTML")


async def sh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts = query.data.split(":")
    chat_id = int(parts[1])
    await query.answer()
    history = await chat_service.get_history(chat_id, 20)
    if not history:
        await query.message.reply_text("📭 No messages in this chat.", parse_mode="HTML")
        return
    lines = [f"📜 <b>CHAT #{chat_id} HISTORY</b>", LINE, ""]
    for m in history:
        sender = m.get("sender", "?")
        text = sanitize_html(m.get("text", ""))[:80]
        media = m.get("media_type")
        ts = m.get("timestamp", "")[:16]
        icon = {"user": "👤", "admin": "🤖", "system": "⚙️"}.get(sender, "❓")
        content = text if text else f"[{media}]" if media else "[empty]"
        lines.append(f"  {icon} {content} <i>({ts})</i>")
    await query.message.reply_text("\n".join(lines), parse_mode="HTML")


async def shold_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts = query.data.split(":")
    chat_id = int(parts[1])
    user_id = int(parts[2])
    await query.answer("Chat on hold")
    await chat_service.set_hold(chat_id)
    await _send_to_user(context, user_id, "⏳ Please hold — we'll be right with you.")
    await chat_service.save_message(chat_id, "admin", "[Put on hold]")


async def sq_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts = query.data.split(":")
    chat_id = int(parts[1])
    user_id = int(parts[2])
    await query.answer()
    buttons = [
        [
            InlineKeyboardButton("👋 Greet", callback_data=f"sqr:{chat_id}:{user_id}:greet"),
            InlineKeyboardButton("⏳ Wait", callback_data=f"sqr:{chat_id}:{user_id}:wait"),
            InlineKeyboardButton("💰 Plans", callback_data=f"sqr:{chat_id}:{user_id}:plans"),
        ],
        [
            InlineKeyboardButton("🙏 Thanks", callback_data=f"sqr:{chat_id}:{user_id}:thanks"),
            InlineKeyboardButton("👋 Bye", callback_data=f"sqr:{chat_id}:{user_id}:bye"),
            InlineKeyboardButton("🔑 Key Sent", callback_data=f"sqr:{chat_id}:{user_id}:key_sent"),
        ],
    ]
    await query.message.reply_text(
        "⚡ <b>Quick Replies</b>",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML",
    )


async def sqr_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts = query.data.split(":")
    chat_id = int(parts[1])
    user_id = int(parts[2])
    canned_key = parts[3]
    text = _CANNED.get(canned_key, "")
    if not text:
        await query.answer("Unknown reply", show_alert=True)
        return
    await query.answer(f"Sending: {canned_key}")
    sent = await _send_to_user(context, user_id, text)
    if sent:
        await chat_service.save_message(chat_id, "admin", f"[Quick: {canned_key}] {text}")
        await query.edit_message_text(f"{E_CHECK} Sent: <b>{canned_key}</b>", parse_mode="HTML")
    else:
        await query.edit_message_text(f"{E_CROSS} Failed to deliver.", parse_mode="HTML")


async def sc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts = query.data.split(":")
    chat_id = int(parts[1])
    user_id = int(parts[2])
    await query.answer("Chat closed")
    session_info = await chat_service.get_session_info(chat_id)
    await chat_service.end_chat(user_id)
    await chat_service.save_message(chat_id, "system", "Admin closed chat")
    await _send_to_user(
        context, user_id,
        f"{E_CHECK} This chat has been closed.\n\nUse /chat anytime to reach us again!",
    )
    await query.message.reply_text(
        f"💬 #{chat_id} — <b>CLOSED</b> {E_CHECK}", parse_mode="HTML",
    )


async def sb_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts = query.data.split(":")
    chat_id = int(parts[1])
    user_id = int(parts[2])
    await query.answer("User blocked")
    await chat_service.block_user(user_id)
    await chat_service.save_message(chat_id, "system", "User blocked by admin")
    try:
        await context.bot.send_message(
            user_id,
            f"{E_CROSS} Your support access has been restricted.",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await query.message.reply_text(
        f"🚫 User <code>{user_id}</code> blocked for 7 days.", parse_mode="HTML",
    )


@admin_only
async def unblock_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Usage: <code>/unblock USER_ID</code>", parse_mode="HTML",
        )
        return
    try:
        user_id = int(args[0])
        await chat_service.unblock_user(user_id)
        await update.message.reply_text(
            f"{E_CHECK} User <code>{user_id}</code> unblocked.", parse_mode="HTML",
        )
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.", parse_mode="HTML")


def get_handlers() -> list:
    return [
        CommandHandler("chats", chats_command),
        CommandHandler("unblock", unblock_command),
        CallbackQueryHandler(sr_callback, pattern=r"^sr:\d+:\d+$"),
        CallbackQueryHandler(sp_callback, pattern=r"^sp:\d+$"),
        CallbackQueryHandler(sg_callback, pattern=r"^sg:\d+$"),
        CallbackQueryHandler(sgt_callback, pattern=r"^sgt:\d+:\w+$"),
        CallbackQueryHandler(si_callback, pattern=r"^si:\d+$"),
        CallbackQueryHandler(sh_callback, pattern=r"^sh:\d+$"),
        CallbackQueryHandler(shold_callback, pattern=r"^shold:\d+:\d+$"),
        CallbackQueryHandler(sq_callback, pattern=r"^sq:\d+:\d+$"),
        CallbackQueryHandler(sqr_callback, pattern=r"^sqr:\d+:\d+:\w+$"),
        CallbackQueryHandler(sc_callback, pattern=r"^sc:\d+:\d+$"),
        CallbackQueryHandler(sb_callback, pattern=r"^sb:\d+:\d+$"),
    ]
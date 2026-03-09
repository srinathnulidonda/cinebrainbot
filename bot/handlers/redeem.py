# bot/handlers/redeem.py
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from bot.middleware.subscription_check import ensure_user
from bot.middleware.analytics import track_command, track_event
from bot.services import key_service
from bot.utils.constants import MSG_KEY_REDEEMED, E_KEY, E_CROWN, E_SPARKLE, LINE, KEY_TYPES, LINE_LIGHT
from bot.utils.keyboards import rate_limit_kb
from bot import CineBotError

logger = logging.getLogger(__name__)


async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)

    if not context.args:
        await update.message.reply_text(
            f"{E_KEY} <b>REDEEM KEY</b>\n"
            f"{LINE}\n\n"
            "Usage: <code>/redeem CINE-XXXX-XXXX-XXXX-XXXX</code>\n\n"
            "📞 /contact an admin to get your key!",
            parse_mode="HTML",
        )
        return

    key_str = context.args[0].upper().strip()
    telegram_id = update.effective_user.id

    try:
        result = await key_service.redeem_key(telegram_id, key_str)
        text = MSG_KEY_REDEEMED.format(
            duration=result["duration"],
            expires=result["expires"],
        )
        await track_event("key_redeemed", telegram_id)
        await update.message.reply_text(text, parse_mode="HTML")
    except CineBotError as e:
        await update.message.reply_text(
            e.user_message, reply_markup=rate_limit_kb(), parse_mode="HTML",
        )


async def redeem_prompt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{E_KEY} <b>REDEEM KEY</b>\n"
        f"{LINE}\n\n"
        "Send: <code>/redeem CINE-XXXX-XXXX-XXXX-XXXX</code>\n\n"
        "📞 /contact an admin to purchase a key!",
        parse_mode="HTML",
    )


async def view_plans_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lines = [
        f"{E_CROWN} <b>CINEBOT PRO</b>",
        LINE,
        "",
        f"{E_SPARKLE} <b>Unlimited</b> searches & recommendations",
        f"{E_SPARKLE} <b>Unlimited</b> AI explanations",
        f"{E_SPARKLE} <b>Unlimited</b> watchlist",
        f"{E_SPARKLE} Priority support",
        "",
        f"{LINE_LIGHT}",
        "",
        "─── ◆ Plans ◆ ───",
    ]
    for k, v in KEY_TYPES.items():
        lines.append(f"  💎 <b>{v['label']}</b> ({k})")
    lines.append("")
    lines.append("📞 /contact an admin to get your key!")
    await query.edit_message_text("\n".join(lines), parse_mode="HTML")


def get_handlers() -> list:
    return [
        CommandHandler("redeem", redeem_command),
        CallbackQueryHandler(redeem_prompt_callback, pattern=r"^redeem_prompt$"),
        CallbackQueryHandler(view_plans_callback, pattern=r"^view_plans$"),
    ]
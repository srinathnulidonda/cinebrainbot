# bot/middleware/admin_check.py
import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from bot.config import get_settings
from bot.models.engine import get_session
from bot.models.user import UserRepo
from bot import AdminRequiredError

logger = logging.getLogger(__name__)
_s = get_settings()


def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        telegram_id = update.effective_user.id
        if telegram_id in _s.ADMIN_IDS:
            return await func(update, context)
        async with get_session() as session:
            user = await UserRepo.get_by_telegram_id(session, telegram_id)
        if user and user.is_admin:
            return await func(update, context)
        raise AdminRequiredError()
    return wrapper


def is_admin(telegram_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if telegram_id in _s.ADMIN_IDS:
        return True
    return context.user_data.get("is_admin", False)
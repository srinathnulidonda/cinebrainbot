# bot/middleware/subscription_check.py
import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from bot.models.engine import get_session
from bot.models.user import UserRepo
from bot import SubscriptionRequiredError
from bot.middleware.rate_limiter import check_rate_limit, increment_usage

logger = logging.getLogger(__name__)


def require_pro(feature_name: str = "this feature"):
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            telegram_id = update.effective_user.id
            async with get_session() as session:
                user = await UserRepo.get_by_telegram_id(session, telegram_id)
            if not user or not user.is_pro:
                raise SubscriptionRequiredError(feature_name)
            return await func(update, context)
        return wrapper
    return decorator


def rate_limited(feature: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            telegram_id = update.effective_user.id
            async with get_session() as session:
                user = await UserRepo.get_by_telegram_id(session, telegram_id)
            is_pro = user.is_pro if user else False
            await check_rate_limit(telegram_id, feature, is_pro)
            result = await func(update, context)
            await increment_usage(telegram_id, feature)
            return result
        return wrapper
    return decorator


async def ensure_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user:
        return
    tg_user = update.effective_user
    async with get_session() as session:
        user, created = await UserRepo.get_or_create(
            session, tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            language_code=tg_user.language_code,
        )
        context.user_data["db_user_id"] = user.id
        context.user_data["is_pro"] = user.is_pro
        context.user_data["is_admin"] = user.is_admin
        context.user_data["tier"] = user.subscription_tier.value
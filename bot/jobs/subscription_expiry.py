# bot/jobs/subscription_expiry.py
import logging
from telegram.ext import ContextTypes
from bot.models.engine import get_session
from bot.models.user import UserRepo
from bot.utils.constants import MSG_EXPIRY_WARNING, MSG_EXPIRED, E_WARN, E_KEY

logger = logging.getLogger(__name__)


async def subscription_expiry_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Running subscription expiry job")
    await _send_expiry_warnings(context)
    await _downgrade_expired(context)


async def _send_expiry_warnings(context: ContextTypes.DEFAULT_TYPE) -> None:
    sent = 0
    for days_ahead in [3, 1]:
        async with get_session() as session:
            users = await UserRepo.get_expiring_subscriptions(session, days_ahead)

        for user in users:
            try:
                from bot.models.engine import redis_client
                warn_key = f"expiry_warn:{user.telegram_id}:{days_ahead}"
                already_warned = await redis_client.get(warn_key)
                if already_warned:
                    continue

                expires_date = user.subscription_expires_at.strftime("%B %d, %Y") if user.subscription_expires_at else "soon"
                text = MSG_EXPIRY_WARNING.format(days=days_ahead, date=expires_date)

                if days_ahead == 1:
                    text += (
                        f"\n\n{E_KEY} Use /redeem with a new key to extend your subscription!"
                    )

                await context.bot.send_message(
                    user.telegram_id, text, parse_mode="HTML",
                )
                await redis_client.setex(warn_key, 86400 * 2, "1")
                sent += 1
            except Exception as e:
                logger.debug(f"Expiry warning failed for {user.telegram_id}: {e}")

    logger.info(f"Expiry warnings sent: {sent}")


async def _downgrade_expired(context: ContextTypes.DEFAULT_TYPE) -> None:
    downgraded = 0
    async with get_session() as session:
        expired_users = await UserRepo.get_expired_pro_users(session)

    for user in expired_users:
        try:
            async with get_session() as session:
                await UserRepo.downgrade_to_free(session, user.telegram_id)

            try:
                await context.bot.send_message(
                    user.telegram_id, MSG_EXPIRED, parse_mode="HTML",
                )
            except Exception:
                pass

            downgraded += 1
            logger.info(f"Downgraded user {user.telegram_id} to FREE")
        except Exception as e:
            logger.error(f"Failed to downgrade {user.telegram_id}: {e}")

    logger.info(f"Subscription expiry job: downgraded={downgraded}")
# bot/jobs/release_alerts.py
import logging
from telegram.ext import ContextTypes
from bot.models.engine import get_session
from bot.models.alert import AlertRepo
from bot.models.user import UserRepo
from bot.utils.constants import E_BELL, E_MOVIE
from bot.utils.keyboards import movie_detail_kb

logger = logging.getLogger(__name__)


async def release_alerts_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Running release alerts job")
    sent, failed = 0, 0

    async with get_session() as session:
        due_alerts = await AlertRepo.get_due_alerts(session)

    for alert in due_alerts:
        try:
            async with get_session() as session:
                user = await UserRepo.get_by_id(session, alert.user_id)
                if not user:
                    await AlertRepo.mark_notified(session, alert.id)
                    continue

                date_str = alert.release_date.strftime("%B %d, %Y") if alert.release_date else "soon"
                text = (
                    f"{E_BELL} <b>Release Alert!</b>\n\n"
                    f"{E_MOVIE} <b>{alert.movie_title}</b> is releasing <b>{date_str}</b>!\n\n"
                    f"Don't miss it! 🍿"
                )

                kb = movie_detail_kb(alert.tmdb_movie_id)

                try:
                    await context.bot.send_message(
                        user.telegram_id, text, parse_mode="HTML",
                        reply_markup=kb, disable_web_page_preview=True,
                    )
                    sent += 1
                except Exception as e:
                    logger.debug(f"Alert send failed for user {user.telegram_id}: {e}")
                    failed += 1

                await AlertRepo.mark_notified(session, alert.id)

        except Exception as e:
            logger.error(f"Alert processing error for alert {alert.id}: {e}")
            failed += 1

    logger.info(f"Release alerts job complete: sent={sent}, failed={failed}")
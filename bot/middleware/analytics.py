# bot/middleware/analytics.py
import logging
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes
from bot.models.engine import redis_client

logger = logging.getLogger(__name__)


async def track_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    command = ""
    if update.message.text and update.message.text.startswith("/"):
        command = update.message.text.split()[0].split("@")[0]
    elif update.callback_query:
        command = "callback"
    if not command:
        return
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pipe = redis_client.pipeline()
    pipe.hincrby(f"analytics:commands:{today}", command, 1)
    pipe.hincrby(f"analytics:users:{today}", str(update.effective_user.id), 1)
    pipe.expire(f"analytics:commands:{today}", 604800)
    pipe.expire(f"analytics:users:{today}", 604800)
    await pipe.execute()


async def get_daily_stats(date_str: str | None = None) -> dict:
    if not date_str:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    commands = await redis_client.hgetall(f"analytics:commands:{date_str}")
    users = await redis_client.hgetall(f"analytics:users:{date_str}")
    total_commands = sum(int(v) for v in commands.values()) if commands else 0
    return {
        "date": date_str,
        "total_commands": total_commands,
        "unique_users": len(users),
        "top_commands": dict(sorted(commands.items(), key=lambda x: int(x[1]), reverse=True)[:10]),
    }


async def track_event(event_name: str, telegram_id: int, metadata: dict | None = None) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await redis_client.hincrby(f"analytics:events:{today}", event_name, 1)
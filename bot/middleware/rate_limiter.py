# bot/middleware/rate_limiter.py
import logging
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import BaseHandler
from bot.models.engine import redis_client
from bot.config import get_settings
from bot import RateLimitExceededError

logger = logging.getLogger(__name__)
_s = get_settings()


def _seconds_until_midnight() -> int:
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    next_midnight = midnight + timedelta(days=1)
    return int((next_midnight - now).total_seconds())


async def check_rate_limit(telegram_id: int, feature: str, is_pro: bool) -> None:
    if is_pro:
        return
    limits = {
        "search": _s.FREE_DAILY_SEARCHES,
        "explain": _s.FREE_DAILY_EXPLAINS,
        "recommend": _s.FREE_DAILY_RECOMMENDS,
    }
    limit = limits.get(feature)
    if limit is None:
        return
    key = f"rl:{feature}:{telegram_id}"
    count = int(await redis_client.get(key) or 0)
    if count >= limit:
        ttl = await redis_client.ttl(key)
        raise RateLimitExceededError(feature, max(ttl, 0))


async def increment_usage(telegram_id: int, feature: str) -> int:
    key = f"rl:{feature}:{telegram_id}"
    pipe = redis_client.pipeline()
    pipe.incr(key)
    ttl_val = await redis_client.ttl(key)
    if ttl_val == -1 or ttl_val == -2:
        pipe.expire(key, _seconds_until_midnight())
    results = await pipe.execute()
    return results[0]


async def get_usage(telegram_id: int, feature: str) -> int:
    key = f"rl:{feature}:{telegram_id}"
    return int(await redis_client.get(key) or 0)


async def get_all_usage(telegram_id: int) -> dict[str, int]:
    features = ["search", "explain", "recommend"]
    result = {}
    for f in features:
        result[f] = await get_usage(telegram_id, f)
    return result


async def check_global_rate_limit(telegram_id: int) -> bool:
    key = f"global_rl:{telegram_id}"
    count = int(await redis_client.get(key) or 0)
    if count >= 30:
        return False
    pipe = redis_client.pipeline()
    pipe.incr(key)
    pipe.expire(key, 60)
    await pipe.execute()
    return True
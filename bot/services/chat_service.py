# bot/services/chat_service.py
import json
import time
import logging
from datetime import datetime, timezone
from bot.config import get_settings
from bot.models.engine import redis_client, get_session
from bot.models.user import UserRepo
from bot.models.watched import WatchedRepo
from bot.models.watchlist import WatchlistRepo

logger = logging.getLogger(__name__)
_s = get_settings()


async def _next_chat_id() -> int:
    return await redis_client.incr("chat:counter")


async def start_chat(user_id: int) -> int:
    existing = await redis_client.get(f"chat:user:{user_id}")
    if existing:
        return int(existing)
    chat_id = await _next_chat_id()
    now = datetime.now(timezone.utc).isoformat()
    pipe = redis_client.pipeline()
    pipe.set(f"chat:user:{user_id}", str(chat_id), ex=_s.CHAT_SESSION_TTL)
    pipe.hset(f"chat:session:{chat_id}", mapping={
        "user_id": str(user_id),
        "chat_id": str(chat_id),
        "status": "active",
        "started_at": now,
        "last_activity": now,
        "message_count": "0",
    })
    pipe.expire(f"chat:session:{chat_id}", _s.CHAT_SESSION_TTL)
    pipe.sadd("chat:active", str(chat_id))
    await pipe.execute()
    return chat_id


async def end_chat(user_id: int) -> bool:
    chat_id = await redis_client.get(f"chat:user:{user_id}")
    if not chat_id:
        return False
    pipe = redis_client.pipeline()
    pipe.delete(f"chat:user:{user_id}")
    pipe.hset(f"chat:session:{chat_id}", "status", "closed")
    pipe.srem("chat:active", chat_id)
    await pipe.execute()
    return True


async def is_in_chat(user_id: int) -> bool:
    return await redis_client.exists(f"chat:user:{user_id}") == 1


async def get_chat_id(user_id: int) -> int | None:
    val = await redis_client.get(f"chat:user:{user_id}")
    return int(val) if val else None


async def is_blocked(user_id: int) -> bool:
    return await redis_client.exists(f"chat:blocked:{user_id}") == 1


async def block_user(user_id: int) -> None:
    await redis_client.set(f"chat:blocked:{user_id}", "1", ex=_s.CHAT_BLOCK_TTL)
    await end_chat(user_id)


async def unblock_user(user_id: int) -> None:
    await redis_client.delete(f"chat:blocked:{user_id}")


async def check_rate_limit(user_id: int) -> bool:
    now = time.time()
    last_key = f"chat:rl_last:{user_id}"
    hour_key = f"chat:rl_hour:{user_id}"
    last_ts = await redis_client.get(last_key)
    if last_ts and (now - float(last_ts)) < _s.CHAT_RATE_LIMIT_INTERVAL:
        return False
    hour_count = int(await redis_client.get(hour_key) or 0)
    if hour_count >= _s.CHAT_RATE_LIMIT_HOURLY:
        return False
    pipe = redis_client.pipeline()
    pipe.set(last_key, str(now), ex=_s.CHAT_RATE_LIMIT_INTERVAL + 1)
    pipe.incr(hour_key)
    ttl = await redis_client.ttl(hour_key)
    if ttl == -1 or ttl == -2:
        pipe.expire(hour_key, 3600)
    await pipe.execute()
    return True


async def save_message(
    chat_id: int, sender: str, text: str | None = None,
    media_type: str | None = None, media_id: str | None = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    msg = json.dumps({
        "sender": sender,
        "text": text or "",
        "media_type": media_type,
        "media_id": media_id,
        "timestamp": now,
    })
    key = f"chat:messages:{chat_id}"
    pipe = redis_client.pipeline()
    pipe.rpush(key, msg)
    pipe.ltrim(key, -200, -1)
    pipe.expire(key, _s.CHAT_HISTORY_TTL)
    pipe.hset(f"chat:session:{chat_id}", "last_activity", now)
    pipe.hincrby(f"chat:session:{chat_id}", "message_count", 1)
    pipe.expire(f"chat:session:{chat_id}", _s.CHAT_SESSION_TTL)
    await pipe.execute()
    user_id_raw = await redis_client.hget(f"chat:session:{chat_id}", "user_id")
    if user_id_raw:
        await redis_client.expire(f"chat:user:{user_id_raw}", _s.CHAT_SESSION_TTL)


async def get_history(chat_id: int, limit: int = 50) -> list[dict]:
    key = f"chat:messages:{chat_id}"
    raw = await redis_client.lrange(key, -limit, -1)
    return [json.loads(m) for m in raw]


async def get_session_info(chat_id: int) -> dict | None:
    data = await redis_client.hgetall(f"chat:session:{chat_id}")
    return data if data else None


async def get_active_chats() -> list[dict]:
    chat_ids = await redis_client.smembers("chat:active")
    chats = []
    for cid in sorted(chat_ids, key=lambda x: int(x), reverse=True):
        session_data = await redis_client.hgetall(f"chat:session:{cid}")
        if session_data and session_data.get("status") == "active":
            session_data["chat_id"] = cid
            chats.append(session_data)
    return chats


async def get_user_context(user_id: int) -> dict:
    ctx = {
        "user_id": user_id,
        "display_name": str(user_id),
        "username": None,
        "tier": "FREE",
        "is_pro": False,
        "watched_count": 0,
        "watchlist_count": 0,
        "joined": "N/A",
    }
    try:
        async with get_session() as session:
            user = await UserRepo.get_by_telegram_id(session, user_id)
            if not user:
                return ctx
            ctx["display_name"] = user.display_name
            ctx["username"] = user.username
            ctx["tier"] = user.subscription_tier.value
            ctx["is_pro"] = user.is_pro
            ctx["joined"] = user.created_at.strftime("%Y-%m-%d") if user.created_at else "N/A"
            ctx["db_user_id"] = user.id
            ctx["watched_count"] = await WatchedRepo.count(session, user.id)
            ctx["watchlist_count"] = await WatchlistRepo.count(session, user.id)
    except Exception as e:
        logger.warning(f"Failed to get user context for {user_id}: {e}")
    return ctx


async def set_hold(chat_id: int) -> None:
    await redis_client.hset(f"chat:session:{chat_id}", "status", "hold")


async def resume_from_hold(chat_id: int) -> None:
    await redis_client.hset(f"chat:session:{chat_id}", "status", "active")


async def cleanup_stale_sessions() -> int:
    chat_ids = await redis_client.smembers("chat:active")
    removed = 0
    for cid in chat_ids:
        exists = await redis_client.exists(f"chat:session:{cid}")
        if not exists:
            await redis_client.srem("chat:active", cid)
            removed += 1
    return removed
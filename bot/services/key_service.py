# bot/services/key_service.py
import logging
from datetime import datetime, timezone
from bot.models.engine import get_session, redis_client
from bot.models.user import UserRepo
from bot.models.license_key import LicenseKeyRepo
from bot.models.database import KeyStatus
from bot.utils.key_generator import generate_key, generate_keys
from bot.utils.validators import validate_key_format
from bot.utils.constants import KEY_TYPES
from bot import (
    InvalidKeyError, KeyNotFoundError, KeyAlreadyUsedError,
    KeyExpiredError, KeyRevokedError, RateLimitExceededError,
)

logger = logging.getLogger(__name__)


async def check_redeem_rate_limit(telegram_id: int) -> None:
    hour_key = f"redeem_hr:{telegram_id}"
    day_key = f"redeem_day:{telegram_id}"
    hour_count = int(await redis_client.get(hour_key) or 0)
    day_count = int(await redis_client.get(day_key) or 0)
    if hour_count >= 5:
        raise RateLimitExceededError("key redemption (hourly)", 3600)
    if day_count >= 10:
        raise RateLimitExceededError("key redemption (daily)", 86400)


async def _increment_redeem_counter(telegram_id: int) -> None:
    hour_key = f"redeem_hr:{telegram_id}"
    day_key = f"redeem_day:{telegram_id}"
    pipe = redis_client.pipeline()
    pipe.incr(hour_key)
    pipe.expire(hour_key, 3600)
    pipe.incr(day_key)
    pipe.expire(day_key, 86400)
    await pipe.execute()


async def redeem_key(telegram_id: int, key_str: str) -> dict:
    if not validate_key_format(key_str):
        raise InvalidKeyError()

    await check_redeem_rate_limit(telegram_id)
    await _increment_redeem_counter(telegram_id)

    async with get_session() as session:
        user = await UserRepo.get_by_telegram_id(session, telegram_id)
        if not user:
            raise InvalidKeyError()
        lk = await LicenseKeyRepo.redeem(session, key_str, user.id)
        user = await UserRepo.extend_subscription(session, telegram_id, lk.duration_days)
        await LicenseKeyRepo.log_action(
            session, telegram_id, "REDEEM", key_id=lk.id,
        )

    key_type_info = KEY_TYPES.get(lk.key_type, {"label": f"{lk.duration_days} days"})
    return {
        "duration": key_type_info.get("label", f"{lk.duration_days} days"),
        "expires": user.subscription_expires_at.strftime("%Y-%m-%d %H:%M UTC") if user.subscription_expires_at else "N/A",
        "days": lk.duration_days,
    }


async def generate_single_key(
    admin_id: int, key_type: str, batch_name: str | None = None,
) -> str:
    type_info = KEY_TYPES.get(key_type.upper())
    if not type_info:
        raise ValueError(f"Invalid key type: {key_type}")
    key = generate_key()
    async with get_session() as session:
        lk = await LicenseKeyRepo.create_key(
            session, key, key_type.upper(), type_info["days"], admin_id, batch_name,
        )
        await LicenseKeyRepo.log_action(
            session, admin_id, "GENERATE", key_id=lk.id, batch_name=batch_name, quantity=1,
        )
    return key


async def generate_bulk_keys(
    admin_id: int, key_type: str, quantity: int, batch_name: str,
) -> list[str]:
    type_info = KEY_TYPES.get(key_type.upper())
    if not type_info:
        raise ValueError(f"Invalid key type: {key_type}")
    keys = generate_keys(quantity)
    async with get_session() as session:
        await LicenseKeyRepo.create_bulk(
            session, keys, key_type.upper(), type_info["days"], admin_id, batch_name,
        )
        await LicenseKeyRepo.log_action(
            session, admin_id, "BULK_GENERATE", batch_name=batch_name, quantity=quantity,
        )
    return keys


async def get_key_info(key_str: str) -> dict | None:
    if not validate_key_format(key_str):
        raise InvalidKeyError()
    async with get_session() as session:
        lk = await LicenseKeyRepo.get_by_key(session, key_str)
        if not lk:
            return None
        result = {
            "key": lk.key,
            "key_type": lk.key_type,
            "duration_days": lk.duration_days,
            "status": lk.status.value,
            "batch_name": lk.batch_name,
            "created_at": lk.created_at.strftime("%Y-%m-%d %H:%M") if lk.created_at else "N/A",
            "redeemed_by_user_id": lk.redeemed_by_user_id,
            "redeemed_at": lk.redeemed_at.strftime("%Y-%m-%d %H:%M") if lk.redeemed_at else None,
        }
        if lk.redeemed_by_user_id:
            user = await UserRepo.get_by_id(session, lk.redeemed_by_user_id)
            if user:
                result["redeemed_by_name"] = user.display_name
                result["redeemed_by_telegram_id"] = user.telegram_id
        return result


async def revoke_key(admin_id: int, key_str: str) -> dict:
    if not validate_key_format(key_str):
        raise InvalidKeyError()
    async with get_session() as session:
        lk = await LicenseKeyRepo.revoke(session, key_str)
        if not lk:
            raise KeyNotFoundError()
        result = {"key": lk.key, "status": "REVOKED", "downgraded_user": None}
        if lk.redeemed_by_user_id:
            user = await UserRepo.get_by_id(session, lk.redeemed_by_user_id)
            if user:
                await UserRepo.downgrade_to_free(session, user.telegram_id)
                result["downgraded_user"] = user.display_name
                result["downgraded_telegram_id"] = user.telegram_id
        await LicenseKeyRepo.log_action(
            session, admin_id, "REVOKE", key_id=lk.id,
        )
    return result


async def gift_key(admin_id: int, target_telegram_id: int, key_type: str) -> dict:
    type_info = KEY_TYPES.get(key_type.upper())
    if not type_info:
        raise ValueError(f"Invalid key type: {key_type}")
    key = generate_key()
    async with get_session() as session:
        user = await UserRepo.get_by_telegram_id(session, target_telegram_id)
        if not user:
            raise ValueError("User not found")
        lk = await LicenseKeyRepo.create_key(
            session, key, key_type.upper(), type_info["days"], admin_id, f"gift_{target_telegram_id}",
        )
        lk = await LicenseKeyRepo.redeem(session, key, user.id)
        await UserRepo.extend_subscription(session, target_telegram_id, type_info["days"])
        await LicenseKeyRepo.log_action(
            session, admin_id, "GIFT", key_id=lk.id,
        )
    return {
        "key": key,
        "duration": type_info["label"],
        "user": user.display_name,
        "telegram_id": target_telegram_id,
    }


async def get_key_stats() -> dict:
    async with get_session() as session:
        return await LicenseKeyRepo.get_stats(session)


async def list_keys(
    status: str | None = None, batch_name: str | None = None,
    page: int = 1, per_page: int = 10,
) -> tuple[list, int]:
    status_enum = KeyStatus(status) if status and status in [s.value for s in KeyStatus] else None
    async with get_session() as session:
        return await LicenseKeyRepo.get_filtered(session, status_enum, batch_name, page, per_page)
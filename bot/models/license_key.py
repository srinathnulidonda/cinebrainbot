# bot/models/license_key.py
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from bot.models.database import LicenseKey, KeyStatus, KeyGenerationLog


class LicenseKeyRepo:
    @staticmethod
    async def create_key(
        session: AsyncSession, key: str, key_type: str,
        duration_days: int, admin_id: int, batch_name: str | None = None,
    ) -> LicenseKey:
        lk = LicenseKey(
            key=key, key_type=key_type, duration_days=duration_days,
            generated_by_admin_id=admin_id, batch_name=batch_name,
        )
        session.add(lk)
        await session.flush()
        return lk

    @staticmethod
    async def create_bulk(
        session: AsyncSession, keys: list[str], key_type: str,
        duration_days: int, admin_id: int, batch_name: str,
    ) -> list[LicenseKey]:
        objects = [
            LicenseKey(
                key=k, key_type=key_type, duration_days=duration_days,
                generated_by_admin_id=admin_id, batch_name=batch_name,
            )
            for k in keys
        ]
        session.add_all(objects)
        await session.flush()
        return objects

    @staticmethod
    async def get_by_key(session: AsyncSession, key: str) -> LicenseKey | None:
        result = await session.execute(select(LicenseKey).where(LicenseKey.key == key.upper().strip()))
        return result.scalar_one_or_none()

    @staticmethod
    async def redeem(session: AsyncSession, key_str: str, user_id: int) -> LicenseKey:
        from bot import KeyNotFoundError, KeyAlreadyUsedError, KeyExpiredError, KeyRevokedError
        result = await session.execute(select(LicenseKey).where(LicenseKey.key == key_str.upper().strip()))
        lk = result.scalar_one_or_none()
        if not lk:
            raise KeyNotFoundError()
        if lk.status == KeyStatus.USED:
            raise KeyAlreadyUsedError()
        if lk.status == KeyStatus.EXPIRED:
            raise KeyExpiredError()
        if lk.status == KeyStatus.REVOKED:
            raise KeyRevokedError()
        now = datetime.now(timezone.utc)
        lk.status = KeyStatus.USED
        lk.redeemed_by_user_id = user_id
        lk.redeemed_at = now
        lk.expires_at = now + timedelta(days=lk.duration_days)
        await session.flush()
        return lk

    @staticmethod
    async def revoke(session: AsyncSession, key_str: str) -> LicenseKey | None:
        result = await session.execute(select(LicenseKey).where(LicenseKey.key == key_str.upper().strip()))
        lk = result.scalar_one_or_none()
        if lk:
            lk.status = KeyStatus.REVOKED
            await session.flush()
        return lk

    @staticmethod
    async def get_filtered(
        session: AsyncSession, status: KeyStatus | None = None,
        batch_name: str | None = None, page: int = 1, per_page: int = 20,
    ) -> tuple[list[LicenseKey], int]:
        stmt = select(LicenseKey)
        count_stmt = select(func.count(LicenseKey.id))
        if status:
            stmt = stmt.where(LicenseKey.status == status)
            count_stmt = count_stmt.where(LicenseKey.status == status)
        if batch_name:
            stmt = stmt.where(LicenseKey.batch_name == batch_name)
            count_stmt = count_stmt.where(LicenseKey.batch_name == batch_name)
        total = (await session.execute(count_stmt)).scalar_one()
        stmt = stmt.order_by(LicenseKey.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        result = await session.execute(stmt)
        return list(result.scalars().all()), total

    @staticmethod
    async def get_stats(session: AsyncSession) -> dict:
        results = {}
        for status in KeyStatus:
            count = (await session.execute(
                select(func.count(LicenseKey.id)).where(LicenseKey.status == status)
            )).scalar_one()
            results[status.value] = count
        results["TOTAL"] = sum(results.values())
        return results

    @staticmethod
    async def log_action(
        session: AsyncSession, admin_id: int, action: str,
        key_id: int | None = None, batch_name: str | None = None, quantity: int | None = None,
    ):
        log = KeyGenerationLog(
            admin_telegram_id=admin_id, action=action,
            key_id=key_id, batch_name=batch_name, quantity=quantity,
        )
        session.add(log)
        await session.flush()

    @staticmethod
    async def get_user_active_key(session: AsyncSession, user_id: int) -> LicenseKey | None:
        result = await session.execute(
            select(LicenseKey).where(
                and_(
                    LicenseKey.redeemed_by_user_id == user_id,
                    LicenseKey.status == KeyStatus.USED,
                )
            ).order_by(LicenseKey.redeemed_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()
# bot/models/user.py
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from bot.models.database import User, SubscriptionTier


class UserRepo:
    @staticmethod
    async def get_or_create(
        session: AsyncSession, telegram_id: int,
        username: str | None = None, first_name: str | None = None,
        last_name: str | None = None, language_code: str | None = None,
    ) -> tuple[User, bool]:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user:
            user.username = username or user.username
            user.first_name = first_name or user.first_name
            user.last_name = last_name or user.last_name
            await session.flush()
            return user, False
        user = User(
            telegram_id=telegram_id, username=username,
            first_name=first_name, last_name=last_name,
            language_code=language_code,
        )
        session.add(user)
        await session.flush()
        return user, True

    @staticmethod
    async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(session: AsyncSession, user_id: int) -> User | None:
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_subscription(
        session: AsyncSession, telegram_id: int,
        tier: SubscriptionTier, expires_at: datetime | None,
    ) -> User | None:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user:
            user.subscription_tier = tier
            user.subscription_expires_at = expires_at
            await session.flush()
        return user

    @staticmethod
    async def extend_subscription(session: AsyncSession, telegram_id: int, days: int) -> User | None:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            return None
        now = datetime.now(timezone.utc)
        if user.subscription_expires_at and user.subscription_expires_at > now:
            base = user.subscription_expires_at
        else:
            base = now
        user.subscription_tier = SubscriptionTier.PRO
        user.subscription_expires_at = base + timedelta(days=days)
        await session.flush()
        return user

    @staticmethod
    async def downgrade_to_free(session: AsyncSession, telegram_id: int) -> User | None:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user:
            user.subscription_tier = SubscriptionTier.FREE
            user.subscription_expires_at = None
            await session.flush()
        return user

    @staticmethod
    async def complete_onboarding(session: AsyncSession, telegram_id: int):
        await session.execute(
            update(User).where(User.telegram_id == telegram_id).values(onboarding_completed=True)
        )

    @staticmethod
    async def set_preferred_genres(session: AsyncSession, telegram_id: int, genres: list[str]):
        await session.execute(
            update(User).where(User.telegram_id == telegram_id).values(preferred_genres=genres)
        )

    @staticmethod
    async def get_user_count(session: AsyncSession) -> int:
        result = await session.execute(select(func.count(User.id)))
        return result.scalar_one()

    @staticmethod
    async def get_pro_user_count(session: AsyncSession) -> int:
        result = await session.execute(
            select(func.count(User.id)).where(User.subscription_tier == SubscriptionTier.PRO)
        )
        return result.scalar_one()

    @staticmethod
    async def get_expiring_subscriptions(session: AsyncSession, days_ahead: int) -> list[User]:
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days_ahead)
        result = await session.execute(
            select(User).where(
                and_(
                    User.subscription_tier == SubscriptionTier.PRO,
                    User.subscription_expires_at <= cutoff,
                    User.subscription_expires_at > now,
                )
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_expired_pro_users(session: AsyncSession) -> list[User]:
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(User).where(
                and_(
                    User.subscription_tier == SubscriptionTier.PRO,
                    User.subscription_expires_at <= now,
                )
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_all_user_ids(session: AsyncSession) -> list[int]:
        result = await session.execute(select(User.telegram_id))
        return list(result.scalars().all())

    @staticmethod
    async def get_pro_user_ids(session: AsyncSession) -> list[int]:
        result = await session.execute(
            select(User.telegram_id).where(User.subscription_tier == SubscriptionTier.PRO)
        )
        return list(result.scalars().all())

    @staticmethod
    async def search_users(
        session: AsyncSession, query: str | None = None,
        tier: SubscriptionTier | None = None, page: int = 1, per_page: int = 20,
    ) -> tuple[list[User], int]:
        stmt = select(User)
        count_stmt = select(func.count(User.id))
        if query:
            like = f"%{query}%"
            filt = User.username.ilike(like) | User.first_name.ilike(like)
            stmt = stmt.where(filt)
            count_stmt = count_stmt.where(filt)
        if tier:
            stmt = stmt.where(User.subscription_tier == tier)
            count_stmt = count_stmt.where(User.subscription_tier == tier)
        total = (await session.execute(count_stmt)).scalar_one()
        stmt = stmt.order_by(User.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        result = await session.execute(stmt)
        return list(result.scalars().all()), total
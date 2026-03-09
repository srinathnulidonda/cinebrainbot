# bot/models/alert.py
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, delete, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from bot.models.database import ReleaseAlert


class AlertRepo:
    @staticmethod
    async def create(
        session: AsyncSession, user_id: int, tmdb_movie_id: int,
        movie_title: str, release_date: datetime | None = None,
    ) -> ReleaseAlert:
        alert = ReleaseAlert(
            user_id=user_id, tmdb_movie_id=tmdb_movie_id,
            movie_title=movie_title, release_date=release_date,
        )
        session.add(alert)
        await session.flush()
        return alert

    @staticmethod
    async def get_due_alerts(session: AsyncSession) -> list[ReleaseAlert]:
        now = datetime.now(timezone.utc)
        tomorrow = now + timedelta(days=1)
        result = await session.execute(
            select(ReleaseAlert).where(
                and_(
                    ReleaseAlert.notified == False,
                    ReleaseAlert.release_date <= tomorrow,
                )
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def mark_notified(session: AsyncSession, alert_id: int):
        await session.execute(
            update(ReleaseAlert).where(ReleaseAlert.id == alert_id).values(notified=True)
        )

    @staticmethod
    async def get_user_alerts(
        session: AsyncSession, user_id: int, page: int = 1, per_page: int = 5,
    ) -> tuple[list[ReleaseAlert], int]:
        total = (await session.execute(
            select(func.count(ReleaseAlert.id)).where(ReleaseAlert.user_id == user_id)
        )).scalar_one()
        result = await session.execute(
            select(ReleaseAlert).where(ReleaseAlert.user_id == user_id)
            .order_by(ReleaseAlert.release_date.asc())
            .offset((page - 1) * per_page).limit(per_page)
        )
        return list(result.scalars().all()), total

    @staticmethod
    async def remove(session: AsyncSession, user_id: int, tmdb_movie_id: int) -> bool:
        result = await session.execute(
            delete(ReleaseAlert).where(
                ReleaseAlert.user_id == user_id, ReleaseAlert.tmdb_movie_id == tmdb_movie_id
            )
        )
        return result.rowcount > 0

    @staticmethod
    async def exists(session: AsyncSession, user_id: int, tmdb_movie_id: int) -> bool:
        return (await session.execute(
            select(func.count(ReleaseAlert.id)).where(
                ReleaseAlert.user_id == user_id, ReleaseAlert.tmdb_movie_id == tmdb_movie_id
            )
        )).scalar_one() > 0
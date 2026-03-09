# bot/models/watchlist.py
from sqlalchemy import select, delete, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from bot.models.database import Watchlist, Priority


class WatchlistRepo:
    @staticmethod
    async def add(
        session: AsyncSession, user_id: int, tmdb_movie_id: int,
        movie_title: str, poster_path: str | None = None, priority: Priority = Priority.MED,
    ) -> Watchlist:
        item = Watchlist(
            user_id=user_id, tmdb_movie_id=tmdb_movie_id,
            movie_title=movie_title, poster_path=poster_path, priority=priority,
        )
        session.add(item)
        await session.flush()
        return item

    @staticmethod
    async def remove(session: AsyncSession, user_id: int, tmdb_movie_id: int) -> bool:
        result = await session.execute(
            delete(Watchlist).where(
                Watchlist.user_id == user_id, Watchlist.tmdb_movie_id == tmdb_movie_id
            )
        )
        return result.rowcount > 0

    @staticmethod
    async def get_paginated(
        session: AsyncSession, user_id: int, page: int = 1, per_page: int = 5,
    ) -> tuple[list[Watchlist], int]:
        total = (await session.execute(
            select(func.count(Watchlist.id)).where(Watchlist.user_id == user_id)
        )).scalar_one()
        priority_order = func.array_position(["HIGH", "MED", "LOW"], Watchlist.priority)
        result = await session.execute(
            select(Watchlist).where(Watchlist.user_id == user_id)
            .order_by(priority_order, Watchlist.added_at.desc())
            .offset((page - 1) * per_page).limit(per_page)
        )
        return list(result.scalars().all()), total

    @staticmethod
    async def count(session: AsyncSession, user_id: int) -> int:
        result = await session.execute(
            select(func.count(Watchlist.id)).where(Watchlist.user_id == user_id)
        )
        return result.scalar_one()

    @staticmethod
    async def exists(session: AsyncSession, user_id: int, tmdb_movie_id: int) -> bool:
        result = await session.execute(
            select(func.count(Watchlist.id)).where(
                Watchlist.user_id == user_id, Watchlist.tmdb_movie_id == tmdb_movie_id
            )
        )
        return result.scalar_one() > 0

    @staticmethod
    async def update_priority(
        session: AsyncSession, user_id: int, tmdb_movie_id: int, priority: Priority,
    ) -> bool:
        result = await session.execute(
            update(Watchlist).where(
                Watchlist.user_id == user_id, Watchlist.tmdb_movie_id == tmdb_movie_id
            ).values(priority=priority)
        )
        return result.rowcount > 0

    @staticmethod
    async def get_all(session: AsyncSession, user_id: int) -> list[Watchlist]:
        result = await session.execute(
            select(Watchlist).where(Watchlist.user_id == user_id).order_by(Watchlist.added_at.desc())
        )
        return list(result.scalars().all())
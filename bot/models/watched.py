# bot/models/watched.py
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from bot.models.database import WatchedMovie


class WatchedRepo:
    @staticmethod
    async def add(
        session: AsyncSession, user_id: int, tmdb_movie_id: int,
        movie_title: str, poster_path: str | None = None,
        user_rating: float | None = None, review_text: str | None = None,
        genre_ids: list | None = None,
    ) -> WatchedMovie:
        item = WatchedMovie(
            user_id=user_id, tmdb_movie_id=tmdb_movie_id,
            movie_title=movie_title, poster_path=poster_path,
            user_rating=user_rating, review_text=review_text, genre_ids=genre_ids,
        )
        session.add(item)
        await session.flush()
        return item

    @staticmethod
    async def get_paginated(
        session: AsyncSession, user_id: int, page: int = 1, per_page: int = 5,
    ) -> tuple[list[WatchedMovie], int]:
        total = (await session.execute(
            select(func.count(WatchedMovie.id)).where(WatchedMovie.user_id == user_id)
        )).scalar_one()
        result = await session.execute(
            select(WatchedMovie).where(WatchedMovie.user_id == user_id)
            .order_by(WatchedMovie.watched_at.desc())
            .offset((page - 1) * per_page).limit(per_page)
        )
        return list(result.scalars().all()), total

    @staticmethod
    async def count(session: AsyncSession, user_id: int) -> int:
        return (await session.execute(
            select(func.count(WatchedMovie.id)).where(WatchedMovie.user_id == user_id)
        )).scalar_one()

    @staticmethod
    async def exists(session: AsyncSession, user_id: int, tmdb_movie_id: int) -> bool:
        return (await session.execute(
            select(func.count(WatchedMovie.id)).where(
                WatchedMovie.user_id == user_id, WatchedMovie.tmdb_movie_id == tmdb_movie_id
            )
        )).scalar_one() > 0

    @staticmethod
    async def update_rating(
        session: AsyncSession, user_id: int, tmdb_movie_id: int,
        rating: float, review: str | None = None,
    ) -> bool:
        values = {"user_rating": rating}
        if review is not None:
            values["review_text"] = review
        result = await session.execute(
            update(WatchedMovie).where(
                WatchedMovie.user_id == user_id, WatchedMovie.tmdb_movie_id == tmdb_movie_id
            ).values(**values)
        )
        return result.rowcount > 0

    @staticmethod
    async def get_recent(session: AsyncSession, user_id: int, limit: int = 10) -> list[WatchedMovie]:
        result = await session.execute(
            select(WatchedMovie).where(WatchedMovie.user_id == user_id)
            .order_by(WatchedMovie.watched_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_genre_stats(session: AsyncSession, user_id: int) -> dict[str, int]:
        result = await session.execute(
            select(WatchedMovie.genre_ids).where(
                WatchedMovie.user_id == user_id, WatchedMovie.genre_ids.isnot(None)
            )
        )
        genre_counts: dict[str, int] = {}
        for (genre_ids,) in result:
            if genre_ids:
                for gid in genre_ids:
                    genre_counts[str(gid)] = genre_counts.get(str(gid), 0) + 1
        return genre_counts

    @staticmethod
    async def get_rating_stats(session: AsyncSession, user_id: int) -> dict:
        result = await session.execute(
            select(
                func.count(WatchedMovie.id),
                func.avg(WatchedMovie.user_rating),
                func.min(WatchedMovie.user_rating),
                func.max(WatchedMovie.user_rating),
            ).where(WatchedMovie.user_id == user_id, WatchedMovie.user_rating.isnot(None))
        )
        row = result.one()
        return {
            "count": row[0], "avg": round(float(row[1]), 1) if row[1] else 0,
            "min": float(row[2]) if row[2] else 0, "max": float(row[3]) if row[3] else 0,
        }

    @staticmethod
    async def get_all_movie_ids(session: AsyncSession, user_id: int) -> list[int]:
        result = await session.execute(
            select(WatchedMovie.tmdb_movie_id).where(WatchedMovie.user_id == user_id)
        )
        return list(result.scalars().all())
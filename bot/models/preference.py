# bot/models/preference.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from bot.models.database import UserPreference


class PreferenceRepo:
    @staticmethod
    async def get_or_create(session: AsyncSession, user_id: int) -> UserPreference:
        result = await session.execute(
            select(UserPreference).where(UserPreference.user_id == user_id)
        )
        pref = result.scalar_one_or_none()
        if not pref:
            pref = UserPreference(user_id=user_id, liked_genres={}, liked_actors={}, taste_vector={})
            session.add(pref)
            await session.flush()
        return pref

    @staticmethod
    async def update_genres(session: AsyncSession, user_id: int, genres: dict):
        pref = await PreferenceRepo.get_or_create(session, user_id)
        pref.liked_genres = genres
        await session.flush()

    @staticmethod
    async def update_actors(session: AsyncSession, user_id: int, actors: dict):
        pref = await PreferenceRepo.get_or_create(session, user_id)
        pref.liked_actors = actors
        await session.flush()

    @staticmethod
    async def update_taste_vector(session: AsyncSession, user_id: int, vector: dict):
        pref = await PreferenceRepo.get_or_create(session, user_id)
        pref.taste_vector = vector
        await session.flush()

    @staticmethod
    async def increment_genre(session: AsyncSession, user_id: int, genre_id: str, genre_name: str):
        pref = await PreferenceRepo.get_or_create(session, user_id)
        genres = dict(pref.liked_genres or {})
        genres[genre_id] = {"name": genre_name, "count": genres.get(genre_id, {}).get("count", 0) + 1}
        pref.liked_genres = genres
        await session.flush()

    @staticmethod
    async def increment_actors(session: AsyncSession, user_id: int, actors: list[dict]):
        pref = await PreferenceRepo.get_or_create(session, user_id)
        current = dict(pref.liked_actors or {})
        for actor in actors[:5]:
            aid = str(actor.get("id", ""))
            if aid:
                current[aid] = {
                    "name": actor.get("name", ""),
                    "count": current.get(aid, {}).get("count", 0) + 1,
                }
        pref.liked_actors = current
        await session.flush()
# bot/models/engine.py
import logging
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
import redis.asyncio as aioredis
from bot.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()

engine = create_async_engine(
    _settings.async_database_url,
    pool_size=_settings.DB_POOL_SIZE,
    max_overflow=_settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=_settings.DB_POOL_RECYCLE,
    echo=False,
)

AsyncSessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

redis_client: aioredis.Redis = aioredis.from_url(
    _settings.REDIS_URL, decode_responses=True, max_connections=20
)


@asynccontextmanager
async def get_session():
    session = AsyncSessionFactory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def init_db():
    from bot.models.database import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized")


async def close_db():
    await engine.dispose()
    await redis_client.aclose()
    logger.info("Database and Redis connections closed")
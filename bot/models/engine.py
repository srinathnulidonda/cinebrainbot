# bot/models/engine.py
import logging
import asyncio
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
    pool_recycle=min(_settings.DB_POOL_RECYCLE, 300),
    pool_timeout=30,
    echo=False,
    connect_args={
        "timeout": 15,
        "command_timeout": 30,
    },
)

AsyncSessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

_bot_loop: asyncio.AbstractEventLoop | None = None


def get_bot_loop() -> asyncio.AbstractEventLoop | None:
    return _bot_loop


class _RedisProxy:
    __slots__ = ("_client",)

    def __init__(self):
        self._client: aioredis.Redis | None = None

    def _init_client(self, url: str, **kwargs):
        self._client = aioredis.from_url(url, **kwargs)

    async def _close_client(self):
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass
            self._client = None

    def __getattr__(self, name: str):
        c = self._client
        if c is None:
            raise RuntimeError("Redis not initialised – call init_db() first")
        return getattr(c, name)


redis_client: aioredis.Redis = _RedisProxy()  # type: ignore[assignment]


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


async def _connect_db_with_retry(max_attempts: int = 5, base_delay: float = 2.0) -> None:
    """
    Connect to PostgreSQL with exponential backoff.
    Handles cold starts on Render's free tier where the DB may be sleeping.
    """
    from bot.models.database import Base

    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database connected and tables initialized")
            return
        except (
            ConnectionResetError,
            ConnectionRefusedError,
            ConnectionAbortedError,
            OSError,
            TimeoutError,
        ) as e:
            last_error = e
            if attempt < max_attempts:
                delay = base_delay * (2 ** (attempt - 1))  # 2s, 4s, 8s, 16s
                logger.warning(
                    "⚠️ DB connection attempt %d/%d failed: %s — retrying in %.0fs",
                    attempt, max_attempts, type(e).__name__, delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "❌ DB connection failed after %d attempts: %s",
                    max_attempts, e,
                )
        except Exception as e:
            # Non-transient error, don't retry
            logger.error("❌ DB connection failed (non-retryable): %s", e)
            raise

    raise last_error  # type: ignore[misc]


async def init_db():
    global _bot_loop
    _bot_loop = asyncio.get_running_loop()

    # Initialize Redis first (usually faster)
    await redis_client._close_client()
    redis_client._init_client(
        _settings.REDIS_URL,
        decode_responses=True,
        max_connections=20,
        socket_connect_timeout=10,
        socket_keepalive=True,
        retry_on_timeout=True,
    )

    # Retry Redis connection too
    for attempt in range(1, 4):
        try:
            await redis_client.ping()
            logger.info("✅ Redis connected")
            break
        except Exception as e:
            if attempt < 3:
                logger.warning("⚠️ Redis ping attempt %d/3 failed: %s", attempt, e)
                await asyncio.sleep(2)
            else:
                logger.error("❌ Redis connection failed: %s", e)
                raise

    # Connect to PostgreSQL with retry
    await _connect_db_with_retry(max_attempts=5, base_delay=2.0)


async def close_db():
    await engine.dispose()
    await redis_client._close_client()
    logger.info("Database and Redis connections closed")
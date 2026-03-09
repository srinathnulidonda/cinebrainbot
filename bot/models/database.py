# bot/models/database.py
import enum
from datetime import datetime
from sqlalchemy import (
    String, Integer, BigInteger, Boolean, DateTime, Text, Float,
    JSON, ForeignKey, UniqueConstraint, Index,
    Enum as SAEnum,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class SubscriptionTier(str, enum.Enum):
    FREE = "FREE"
    PRO = "PRO"


class KeyStatus(str, enum.Enum):
    UNUSED = "UNUSED"
    USED = "USED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class Priority(str, enum.Enum):
    HIGH = "HIGH"
    MED = "MED"
    LOW = "LOW"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_sub_expires", "subscription_tier", "subscription_expires_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    language_code: Mapped[str | None] = mapped_column(String(10))
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        SAEnum(SubscriptionTier, name="subscription_tier_enum", create_constraint=True),
        default=SubscriptionTier.FREE, server_default="FREE",
    )
    subscription_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    daily_searches_used: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    daily_searches_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    preferred_genres: Mapped[list | None] = mapped_column(ARRAY(String))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    watchlist_items: Mapped[list["Watchlist"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    watched_movies: Mapped[list["WatchedMovie"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    preferences: Mapped["UserPreference | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    alerts: Mapped[list["ReleaseAlert"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    @property
    def is_pro(self) -> bool:
        if self.subscription_tier != SubscriptionTier.PRO:
            return False
        if self.subscription_expires_at and self.subscription_expires_at.replace(tzinfo=None) < datetime.utcnow():
            return False
        return True

    @property
    def display_name(self) -> str:
        if self.first_name:
            return self.first_name
        if self.username:
            return f"@{self.username}"
        return str(self.telegram_id)


class LicenseKey(Base):
    __tablename__ = "license_keys"
    __table_args__ = (Index("ix_keys_status_batch", "status", "batch_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(24), unique=True, nullable=False, index=True)
    key_type: Mapped[str] = mapped_column(String(10), nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[KeyStatus] = mapped_column(
        SAEnum(KeyStatus, name="key_status_enum", create_constraint=True),
        default=KeyStatus.UNUSED, server_default="UNUSED",
    )
    generated_by_admin_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    redeemed_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    batch_name: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    redeemer: Mapped["User | None"] = relationship(foreign_keys=[redeemed_by_user_id])


class KeyGenerationLog(Base):
    __tablename__ = "key_generation_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    key_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("license_keys.id"))
    batch_name: Mapped[str | None] = mapped_column(String(100))
    quantity: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Watchlist(Base):
    __tablename__ = "watchlist"
    __table_args__ = (
        UniqueConstraint("user_id", "tmdb_movie_id", name="uq_watchlist_user_movie"),
        Index("ix_watchlist_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tmdb_movie_id: Mapped[int] = mapped_column(Integer, nullable=False)
    movie_title: Mapped[str] = mapped_column(String(500), nullable=False)
    poster_path: Mapped[str | None] = mapped_column(String(500))
    priority: Mapped[Priority] = mapped_column(
        SAEnum(Priority, name="priority_enum", create_constraint=True),
        default=Priority.MED, server_default="MED",
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="watchlist_items")


class WatchedMovie(Base):
    __tablename__ = "watched_movies"
    __table_args__ = (
        UniqueConstraint("user_id", "tmdb_movie_id", name="uq_watched_user_movie"),
        Index("ix_watched_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tmdb_movie_id: Mapped[int] = mapped_column(Integer, nullable=False)
    movie_title: Mapped[str] = mapped_column(String(500), nullable=False)
    poster_path: Mapped[str | None] = mapped_column(String(500))
    user_rating: Mapped[float | None] = mapped_column(Float)
    review_text: Mapped[str | None] = mapped_column(Text)
    genre_ids: Mapped[list | None] = mapped_column(JSON)
    watched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="watched_movies")


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    liked_genres: Mapped[dict | None] = mapped_column(JSON, default=dict)
    liked_actors: Mapped[dict | None] = mapped_column(JSON, default=dict)
    taste_vector: Mapped[dict | None] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="preferences")


class ReleaseAlert(Base):
    __tablename__ = "release_alerts"
    __table_args__ = (Index("ix_alerts_release_notified", "release_date", "notified"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tmdb_movie_id: Mapped[int] = mapped_column(Integer, nullable=False)
    movie_title: Mapped[str] = mapped_column(String(500), nullable=False)
    release_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="alerts")
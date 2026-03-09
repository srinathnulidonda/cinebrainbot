# scripts/setup_db.py
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.config import get_settings
from bot.models.engine import init_db, close_db, AsyncSessionFactory
from bot.models.database import Base, User, SubscriptionTier
from sqlalchemy import select


async def setup():
    print("=" * 40)
    print("CineBot Database Setup")
    print("=" * 40)

    settings = get_settings()
    db_url = settings.async_database_url
    safe_url = db_url.split("@")[-1] if "@" in db_url else "local"
    print(f"Database: ...@{safe_url}")

    print("\nCreating tables...")
    await init_db()
    print("✅ Tables created successfully")

    if settings.ADMIN_IDS:
        print(f"\nSetting up admins: {settings.ADMIN_IDS}")
        async with AsyncSessionFactory() as session:
            for admin_id in settings.ADMIN_IDS:
                try:
                    result = await session.execute(
                        select(User).where(User.telegram_id == admin_id)
                    )
                    user = result.scalar_one_or_none()
                    if user:
                        user.is_admin = True
                        print(f"  ✅ Updated user {admin_id} as admin")
                    else:
                        user = User(
                            telegram_id=admin_id,
                            is_admin=True,
                            subscription_tier=SubscriptionTier.PRO,
                            onboarding_completed=True,
                        )
                        session.add(user)
                        print(f"  ✅ Created admin user {admin_id}")
                    await session.commit()
                except Exception as e:
                    print(f"  ⚠️ Error setting admin {admin_id}: {e}")
                    await session.rollback()
    else:
        print("\n⚠️ No ADMIN_IDS set in environment")

    await close_db()
    print("\n✅ Setup complete!")
    print("=" * 40)


if __name__ == "__main__":
    asyncio.run(setup())
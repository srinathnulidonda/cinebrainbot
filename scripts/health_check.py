# scripts/health_check.py
import asyncio
import sys
sys.path.insert(0, ".")


async def check():
    results = {}

    try:
        from bot.models.engine import redis_client
        await redis_client.ping()
        results["redis"] = "✅ OK"
    except Exception as e:
        results["redis"] = f"❌ {e}"

    try:
        from bot.models.engine import engine
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        results["postgres"] = "✅ OK"
    except Exception as e:
        results["postgres"] = f"❌ {e}"

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://api.themoviedb.org/3/configuration", params={
                "api_key": __import__("bot.config", fromlist=["get_settings"]).get_settings().TMDB_API_KEY
            })
            resp.raise_for_status()
        results["tmdb"] = "✅ OK"
    except Exception as e:
        results["tmdb"] = f"❌ {e}"

    try:
        from bot.config import get_settings
        s = get_settings()
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://api.telegram.org/bot{s.BOT_TOKEN}/getMe"
            )
            data = resp.json()
            if data.get("ok"):
                results["telegram"] = f"✅ OK (@{data['result']['username']})"
            else:
                results["telegram"] = f"❌ {data}"
    except Exception as e:
        results["telegram"] = f"❌ {e}"

    print("\n🏥 CineBot Health Check\n" + "=" * 35)
    all_ok = True
    for service, status in results.items():
        print(f"  {service:12s} {status}")
        if "❌" in status:
            all_ok = False
    print("=" * 35)
    print(f"  Overall: {'✅ All systems go!' if all_ok else '⚠️ Issues detected'}\n")

    from bot.models.engine import close_db
    await close_db()
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    asyncio.run(check())
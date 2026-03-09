# scripts/generate_keys.py
import asyncio
import sys
sys.path.insert(0, ".")

from bot.config import get_settings
from bot.services.key_service import generate_bulk_keys
from bot.models.engine import init_db, close_db
from bot.utils.key_generator import format_keys_file


async def main():
    if len(sys.argv) < 4:
        print("Usage: python scripts/generate_keys.py TYPE QUANTITY BATCH_NAME [ADMIN_ID]")
        print("Example: python scripts/generate_keys.py 1M 100 launch_promo")
        print("Types: 1M, 2M, 3M, 6M, 1Y")
        sys.exit(1)

    key_type = sys.argv[1].upper()
    quantity = int(sys.argv[2])
    batch_name = sys.argv[3]
    settings = get_settings()
    admin_id = int(sys.argv[4]) if len(sys.argv) > 4 else (settings.ADMIN_IDS[0] if settings.ADMIN_IDS else 0)

    await init_db()

    print(f"Generating {quantity} keys of type {key_type} (batch: {batch_name})...")
    keys = await generate_bulk_keys(admin_id, key_type, quantity, batch_name)

    filename = f"keys_{batch_name}_{key_type}_{quantity}.txt"
    content = format_keys_file(keys, key_type, batch_name)
    with open(filename, "w") as f:
        f.write(content)

    print(f"Generated {len(keys)} keys → {filename}")
    print(f"First 3 keys:")
    for k in keys[:3]:
        print(f"  {k}")

    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
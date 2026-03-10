# run.py
import logging
import sys
import time
import socket
import urllib.request
import json

logger = logging.getLogger(__name__)


def wait_for_port(port, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                logger.info("✅ Port %d is ready", port)
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.5)
    logger.warning("⚠️ Port %d not ready after %ds", port, timeout)
    return False


def force_kill_old_session():
    from bot.config import get_settings
    token = get_settings().BOT_TOKEN

    logger.info("🔪 Clearing old polling session...")

    try:
        url = f"https://api.telegram.org/bot{token}/deleteWebhook"
        data = json.dumps({"drop_pending_updates": True}).encode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            logger.info("🔪 deleteWebhook: %s", result.get("description", "ok"))
    except Exception as e:
        logger.warning("🔪 deleteWebhook failed: %s", e)

    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        data = json.dumps({"offset": -1, "timeout": 0}).encode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            logger.info("🔪 Cleared pending updates")
    except Exception as e:
        logger.warning("🔪 Clear updates failed: %s", e)


def main():
    logging.basicConfig(
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        level=logging.INFO,
        stream=sys.stdout,
    )

    logger.info("🎬 CineBrainBot starting...")

    from bot.jobs.status import start_server, start_self_ping, PORT

    start_server()
    wait_for_port(PORT)
    start_self_ping()

    force_kill_old_session()

    logger.info("⏳ Waiting 30s for old instance to fully die...")
    time.sleep(30)

    force_kill_old_session()
    time.sleep(2)

    logger.info("🚀 Starting Telegram polling...")
    from bot.main import run_polling
    run_polling()


if __name__ == "__main__":
    main()
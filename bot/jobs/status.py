# bot/jobs/status.py

from __future__ import annotations
import logging
import os
import platform
import threading
import time
import urllib.request
from datetime import datetime, timezone

import psutil
from flask import Flask, Response, jsonify, request

logger = logging.getLogger(__name__)

PORT: int = int(os.environ.get("PORT", 10000))
PING_INTERVAL: int = int(os.environ.get("PING_INTERVAL", 300))
ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "production")
STATUS_SECRET: str = os.environ.get("STATUS_SECRET", "")

START_TIME: float = time.time()

_lock = threading.Lock()
_bot_state: dict = {"running": False, "mode": "polling"}


def set_bot_running(running: bool, mode: str = "polling") -> None:
    """Call from post_init / post_shutdown to flip bot status."""
    with _lock:
        _bot_state["running"] = running
        _bot_state["mode"] = mode



def _uptime() -> tuple[str, int]:
    total = int(time.time() - START_TIME)
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s", total


def _system_metrics() -> dict:
    """Return Python version, system CPU %, and process RSS."""
    try:
        proc = psutil.Process()
        mem_mb = round(proc.memory_info().rss / (1024 * 1024), 1)
        cpu = psutil.cpu_percent(interval=0.5)
    except (psutil.Error, OSError):
        mem_mb = 0.0
        cpu = 0.0
    return {
        "python_version": platform.python_version(),
        "cpu_percent": cpu,
        "memory_mb": mem_mb,
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")



app = Flask(__name__)

app.logger.setLevel(logging.ERROR)
logging.getLogger("werkzeug").setLevel(logging.ERROR)


@app.route("/")
def root() -> Response:
    return Response(
        "CineBrainBot is running!",
        status=200,
        mimetype="text/plain",
    )


@app.route("/health")
def health():
    """Public. Render's health‑check and the self‑ping both hit this."""
    return jsonify({"status": "alive"}), 200


@app.route("/bot/services/status")
def detailed_status():
    if STATUS_SECRET:
        header = request.headers.get("Authorization", "")
        if header != f"Bearer {STATUS_SECRET}":
            return jsonify({"error": "unauthorized"}), 401
    human, seconds = _uptime()

    with _lock:
        bot_snapshot = dict(_bot_state)

    try:
        from bot import __version__ as version
    except ImportError:
        version = "1.0.0"

    body = {
        "status": "healthy",
        "service": "CineBrainBot",
        "version": version,
        "environment": ENVIRONMENT,
        "timestamp": _now_iso(),
        "uptime": {
            "human": human,
            "seconds": seconds,
        },
        "system": _system_metrics(),
        "bot": bot_snapshot,
    }
    return jsonify(body), 200


def start_server() -> threading.Thread:
    def _serve() -> None:
        app.run(
            host="0.0.0.0",
            port=PORT,
            debug=False,
            use_reloader=False,
        )

    thread = threading.Thread(target=_serve, daemon=True, name="StatusServer")
    thread.start()
    logger.info("🚀 Status server started on 0.0.0.0:%d", PORT)
    return thread

def start_self_ping() -> threading.Thread | None:
    base_url = (
        os.environ.get("RENDER_EXTERNAL_URL")
        or os.environ.get("STATUS_URL")
    )
    if not base_url:
        logger.warning(
            "⚠️  RENDER_EXTERNAL_URL / STATUS_URL not set — self‑ping disabled"
        )
        return None

    ping_url = f"{base_url.rstrip('/')}/health"

    def _loop() -> None:
        time.sleep(30)
        while True:
            try:
                req = urllib.request.Request(ping_url, method="GET")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    logger.info("🏓 Self‑ping → %d", resp.status)
            except Exception as exc:
                logger.warning("🏓 Self‑ping failed: %s", exc)
            time.sleep(PING_INTERVAL)

    thread = threading.Thread(target=_loop, daemon=True, name="SelfPing")
    thread.start()
    logger.info("🏓 Self‑ping target: %s  (every %ds)", ping_url, PING_INTERVAL)
    return thread
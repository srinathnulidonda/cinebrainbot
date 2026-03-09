# run.py
import threading
import logging
import time
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import os

logger = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", 10000))
START_TIME = time.time()


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        client_ip = self.client_address[0]
        user_agent = self.headers.get("User-Agent", "Unknown")

        if self.path == "/health":
            uptime = int(time.time() - START_TIME)
            hours, remainder = divmod(uptime, 3600)
            minutes, seconds = divmod(remainder, 60)

            body = json.dumps({
                "status": "alive",
                "service": "CineBrainBot",
                "uptime": f"{hours}h {minutes}m {seconds}s",
                "uptime_seconds": uptime,
            })

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body.encode())

            logger.info(
                f"✅ Health check | IP: {client_ip} | "
                f"Uptime: {hours}h {minutes}m {seconds}s | "
                f"Agent: {user_agent[:50]}"
            )
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"CineBrainBot is running!")
            logger.info(f"📡 Request: {self.path} | IP: {client_ip}")

    def log_message(self, format, *args):
        pass


def start_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    logger.info(f"🚀 Health server started on port {PORT}")
    server.serve_forever()


def main():
    logging.basicConfig(
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        level=logging.INFO,
    )

    logger.info("🎬 CineBrainBot starting...")

    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()

    from bot.main import run_polling
    run_polling()


if __name__ == "__main__":
    main()
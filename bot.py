"""
OpenWA WhatsApp Bot
A simple bot that listens to incoming messages via webhook
and auto-replies using the OpenWA REST API.
"""

import os
import logging
import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify

# Load .env file (must be called before os.getenv)
load_dotenv()

# ──────────────────────────────────────────────────────────────
# Configuration — update these values to match your OpenWA setup
# ──────────────────────────────────────────────────────────────
OPENWA_BASE_URL = os.getenv("OPENWA_BASE_URL", "http://localhost:2785")
OPENWA_API_KEY = os.getenv("OPENWA_API_KEY", "YOUR_API_KEY")
OPENWA_SESSION_ID = os.getenv("OPENWA_SESSION_ID", "YOUR_SESSION_ID")
BOT_PORT = int(os.getenv("BOT_PORT", "5000"))

# ──────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Flask App
# ──────────────────────────────────────────────────────────────
app = Flask(__name__)


def send_text(chat_id: str, text: str) -> dict:
    """Send a text message through the OpenWA API."""
    url = f"{OPENWA_BASE_URL}/api/sessions/{OPENWA_SESSION_ID}/messages/send-text"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": OPENWA_API_KEY,
    }
    payload = {
        "chatId": chat_id,
        "text": text,
    }

    logger.info("📤 Sending to %s | chatId=%s | text=%s", url, chat_id, text)

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        logger.info("✅ Message sent to %s: %s", chat_id, text)
        return data
    except requests.HTTPError as exc:
        # Log the full error response from OpenWA
        error_body = exc.response.text if exc.response is not None else "no response body"
        logger.error("❌ HTTP %s for %s: %s", exc.response.status_code if exc.response else '?', chat_id, error_body)
        return {"success": False, "error": error_body}
    except requests.RequestException as exc:
        logger.error("❌ Request failed for %s: %s", chat_id, exc)
        return {"success": False, "error": str(exc)}


def handle_message(data: dict) -> None:
    """
    Process an incoming message and decide whether to reply.
    Add your command/keyword logic here.
    """
    # Log the full incoming data for debugging
    logger.info("📦 Raw message data: %s", data)

    # Skip messages sent by the bot itself to avoid infinite loops
    if data.get("fromMe", False):
        logger.info("⏭️ Skipping own message")
        return

    # Extract message details
    body = (data.get("body") or "").strip().lower()
    from_id = data.get("from", "")
    is_group = data.get("isGroup", False)

    # Determine the chat to reply to
    # For groups, reply to the group; for private chats, reply to the sender
    chat_id = data.get("chatId") or from_id

    logger.info("📩 Message from %s (chatId=%s): %s", from_id, chat_id, body)

    # ── Command handlers ─────────────────────────────────────
    if body == "hello":
        send_text(chat_id, "hello too 👋")

    elif body == "ping":
        send_text(chat_id, "pong 🏓")

    elif body == "help":
        help_text = (
            "🤖 *Bot Commands*\n\n"
            "• *hello* — Say hello\n"
            "• *ping* — Check if bot is alive\n"
            "• *help* — Show this help message"
        )
        send_text(chat_id, help_text)


@app.route("/webhook", methods=["POST"])
def webhook():
    """
    Webhook endpoint that OpenWA calls when events occur.
    Register this URL in your OpenWA session webhook settings.
    """
    payload = request.get_json(silent=True)

    if not payload:
        return jsonify({"status": "no payload"}), 400

    event = payload.get("event", "")
    data = payload.get("data", {})

    logger.info("🔔 Webhook event: %s", event)

    if event == "message.received":
        handle_message(data)
    elif event == "session.status":
        status = data.get("status", "")
        logger.info("📡 Session status changed: %s", status)

    return jsonify({"status": "ok"}), 200


@app.route("/health", methods=["GET"])
def health():
    """Simple health-check endpoint."""
    return jsonify({"status": "running", "bot": "openwa-bot"}), 200


# ──────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🤖 OpenWA Bot starting...")
    logger.info("   API URL    : %s", OPENWA_BASE_URL)
    logger.info("   Session ID : %s", OPENWA_SESSION_ID)
    logger.info("   Bot Port   : %s", BOT_PORT)
    logger.info("=" * 50)
    logger.info("")
    logger.info("📌 Register this webhook URL in OpenWA:")
    logger.info("   http://<your-server-ip>:%s/webhook", BOT_PORT)
    logger.info("")

    app.run(host="0.0.0.0", port=BOT_PORT, debug=False)

"""
OpenWA WhatsApp Bot
A simple bot that listens to incoming messages via webhook
and auto-replies using the OpenWA REST API.
"""

import os
import logging
import requests
import pyotp
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from openai import OpenAI

import storage

# Load .env file (must be called before os.getenv)
load_dotenv()

# ──────────────────────────────────────────────────────────────
# Configuration — update these values to match your OpenWA setup
# ──────────────────────────────────────────────────────────────
OPENWA_BASE_URL = os.getenv("OPENWA_BASE_URL", "http://localhost:2785")
OPENWA_API_KEY = os.getenv("OPENWA_API_KEY", "YOUR_API_KEY")
OPENWA_SESSION_ID = os.getenv("OPENWA_SESSION_ID", "YOUR_SESSION_ID")
BOT_PORT = int(os.getenv("BOT_PORT", "5000"))

# OpenRouter API configuration (Bypasses region locks!)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Initialize OpenRouter Client (if configured)
if OPENROUTER_API_KEY:
    ai_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )
else:
    ai_client = None

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


# ──────────────────────────────────────────────────────────────
# Command handlers
# ──────────────────────────────────────────────────────────────
def cmd_set_password(chat_id: str, phone: str, raw_body: str) -> None:
    """Handle: set ambri pass <password>"""
    # Extract password from the original (non-lowered) message
    # "set ambri pass myPassword123" → "myPassword123"
    parts = raw_body.split(maxsplit=3)
    if len(parts) < 4 or not parts[3].strip():
        send_text(chat_id, "⚠️ Usage: *set ambri pass <your_password>*")
        return

    password = parts[3].strip()
    storage.set_password(phone, password)
    send_text(chat_id, "✅ Password saved and encrypted successfully!")


def cmd_set_totp(chat_id: str, phone: str, raw_body: str) -> None:
    """Handle: set ambri totp <totp_secret>"""
    # Extract TOTP secret from the original (non-lowered) message
    # "set ambri totp 7XCU6AG2..." → "7XCU6AG2..."
    parts = raw_body.split(maxsplit=3)
    if len(parts) < 4 or not parts[3].strip():
        send_text(chat_id, "⚠️ Usage: *set ambri totp <your_totp_secret>*")
        return

    totp_secret = parts[3].strip()

    # Validate the TOTP secret format
    try:
        pyotp.TOTP(totp_secret).now()
    except Exception:
        send_text(chat_id, "❌ Invalid TOTP secret. Please provide a valid base32 secret key.")
        return

    storage.set_totp_secret(phone, totp_secret)
    send_text(chat_id, "✅ TOTP secret saved and encrypted successfully!")


def cmd_generate_code(chat_id: str, phone: str) -> None:
    """Handle: generate code"""
    creds = storage.get_credentials(phone)

    if not creds:
        send_text(chat_id, "⚠️ You haven't set up yet.\nPlease set your password and TOTP secret first:\n\n• *set ambri pass <password>*\n• *set ambri totp <secret>*")
        return

    if not creds["password"]:
        send_text(chat_id, "⚠️ Password not set.\nUse: *set ambri pass <password>*")
        return

    if not creds["totp_secret"]:
        send_text(chat_id, "⚠️ TOTP secret not set.\nUse: *set ambri totp <secret>*")
        return

    # Generate the TOTP code and combine with password
    totp = pyotp.TOTP(creds["totp_secret"])
    totp_code = totp.now()
    login_code = f"{creds['password']}{totp_code}"

    send_text(chat_id, "🔑 Your login code:\n⏱️ _Expires in ~30 seconds_")
    send_text(chat_id, login_code)


def cmd_ai(chat_id: str, raw_body: str) -> None:
    """Handle: ai <message>"""
    if not ai_client:
        send_text(chat_id, "⚠️ AI Chat is not configured yet. Please configure OPENROUTER_API_KEY in the .env file.")
        return

    # Extract the user's prompt
    parts = raw_body.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        send_text(chat_id, "⚠️ Usage: *ai <your question>*")
        return
        
    prompt = parts[1].strip()
    
    try:
        response = ai_client.chat.completions.create(
            model="meta-llama/llama-3.1-8b-instruct:free",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful, friendly AI assistant. Keep your responses concise and well-formatted for WhatsApp."
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0.7,
            max_tokens=800,
        )
        
        reply = response.choices[0].message.content
        send_text(chat_id, reply)
    except Exception as e:
        logger.error("❌ OpenRouter AI error: %s", e)
        send_text(chat_id, f"❌ Sorry, I encountered an error while processing your request.")


# ──────────────────────────────────────────────────────────────
# Message router
# ──────────────────────────────────────────────────────────────
def handle_message(data: dict) -> None:
    """
    Process an incoming message and decide whether to reply.
    """
    # Log the full incoming data for debugging
    logger.info("📦 Raw message data: %s", data)

    # Skip messages sent by the bot itself to avoid infinite loops
    if data.get("fromMe", False):
        logger.info("⏭️ Skipping own message")
        return

    # Keep original body for extracting case-sensitive values (password, totp)
    raw_body = (data.get("body") or "").strip()
    body = raw_body.lower()
    from_id = data.get("from", "")
    is_group = data.get("isGroup", False)

    # Determine the chat to reply to
    chat_id = data.get("chatId") or from_id

    # Extract phone number (strip @c.us / @g.us suffix)
    phone = from_id.split("@")[0] if "@" in from_id else from_id

    logger.info("📩 Message from %s (chatId=%s): %s", from_id, chat_id, body)

    # ── Command routing ──────────────────────────────────────
    if body.startswith("set ambri pass"):
        cmd_set_password(chat_id, phone, raw_body)

    elif body.startswith("set ambri totp"):
        cmd_set_totp(chat_id, phone, raw_body)

    elif body == "generate code":
        cmd_generate_code(chat_id, phone)

    elif body.startswith("ai "):
        cmd_ai(chat_id, raw_body)

    elif body == "hello":
        send_text(chat_id, "hello too 👋")

    elif body == "ping":
        send_text(chat_id, "pong 🏓")

    elif body == "help":
        help_text = (
            "🤖 *Bot Commands*\n\n"
            "📋 *General*\n"
            "• *hello* — Say hello\n"
            "• *ping* — Check if bot is alive\n"
            "• *help* — Show this help message\n\n"
            "🧠 *AI Chat*\n"
            "• *ai <question>* — Ask the AI anything\n\n"
            "🔐 *Login Code*\n"
            "• *set ambri pass <password>* — Set your password\n"
            "• *set ambri totp <secret>* — Set your TOTP secret\n"
            "• *generate code* — Get your login code"
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
    # Initialize the database on startup
    storage.init_db()

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

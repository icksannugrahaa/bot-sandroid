"""
OpenWA WhatsApp Bot
A simple bot that listens to incoming messages via webhook
and auto-replies using the OpenWA REST API.
"""

import os
import re
import logging
import requests
import pyotp
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from openai import OpenAI
import threading

import storage
import attendance_handlers as ah

# Load .env file (must be called before os.getenv)
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(_env_path)

# ──────────────────────────────────────────────────────────────
# Configuration — update these values to match your OpenWA setup
# ──────────────────────────────────────────────────────────────
from whatsapp import send_text, OPENWA_BASE_URL, OPENWA_SESSION_ID
BOT_PORT = int(os.getenv("BOT_PORT", "5000"))
BOT_PHONE = os.getenv("BOT_PHONE", "")
# WhatsApp LID (Linked ID) — the internal ID WhatsApp uses for @mentions
# Find it in the logs: the body will show @<LID> when someone tags the bot
BOT_LID = os.getenv("BOT_LID", "")

# GitHub Models configuration (Runs natively on Azure!)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# Initialize AI Client
if GITHUB_TOKEN:
    ai_client = OpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=GITHUB_TOKEN,
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

# ──────────────────────────────────────────────────────────────
# Maintenance mode
# ──────────────────────────────────────────────────────────────
_maintenance_mode = False


def is_maintenance() -> bool:
    return _maintenance_mode


def set_maintenance(enabled: bool) -> None:
    global _maintenance_mode
    _maintenance_mode = enabled
    logger.info("🔧 Maintenance mode %s", "ENABLED" if enabled else "DISABLED")


# Removed send_text in favor of whatsapp.py


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
    try:
        creds = storage.get_credentials(phone)
    except Exception:
        send_text(chat_id, "❌ Encryption Error: Data is locked with a different ENCRYPTION_KEY. Please ensure the ENCRYPTION_KEY in your server's .env matches the one on your Mac.")
        return

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

    send_text(chat_id, "🔑 Your login code:\n⏱️ _Expires in ~30 seconds_\n📋 _Tap & hold pesan di bawah untuk copy_")
    send_text(chat_id, login_code)


def cmd_ai(chat_id: str, prompt: str, media: dict = None) -> None:
    """Handle: AI chat (default fallback)"""
    if not ai_client:
        send_text(chat_id, "⚠️ AI Chat is not configured yet. Please configure GITHUB_TOKEN in the .env file.")
        return

    if not prompt.strip() and not media:
        return
        
    user_content = []
    
    if prompt.strip():
        user_content.append({"type": "text", "text": prompt.strip()})
    else:
        if media:
            user_content.append({"type": "text", "text": "Tolong jelaskan gambar ini."})

    if media and "data" in media and "mimetype" in media:
        base64_data = media["data"]
        mime_type = media["mimetype"]
        user_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{base64_data}"
            }
        })
    
    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful, friendly AI assistant. Keep your responses concise and well-formatted for WhatsApp."
                },
                {
                    "role": "user",
                    "content": user_content,
                }
            ],
            temperature=0.7,
            max_tokens=800,
        )
        
        reply = response.choices[0].message.content
        send_text(chat_id, reply)
    except Exception as e:
        logger.error("❌ GitHub Models AI error: %s", e)
        send_text(chat_id, f"❌ Sorry, I encountered an error while processing your request.")


# ──────────────────────────────────────────────────────────────
# "Who made the bot?" detector
# ──────────────────────────────────────────────────────────────
_CREATOR_PATTERNS = [
    # English patterns
    r"who\s+(made|create[ds]?|built|develop(ed|s)?|wrote|own[s]?|design(ed|s)?)\s.*(bot|this)",
    r"who\s+(is|are)\s+(the\s+)?(creator|maker|developer|author|owner)\s*(of\s+)?(this\s+)?(bot)?",
    r"who.*(made|create[ds]?|built|develop(ed)?)\s*(this\s+)?(bot|you)",
    r"(bot|you).*(made|created|built|developed)\s+by\s+who",

    # Indonesian patterns
    r"siapa\s+(yang\s+)?(buat|bikin|develop|ngembangin|kembang(in|kan)?|ciptain|ciptakan|biki?n)\s*(bot|ini)",
    r"(bot|ini)\s+(di)?(buat|bikin|develop|kembang(in|kan)?)\s+(oleh\s+)?siapa",
    r"(bot|ini)\s+buatan\s+(siapa|mana)",
    r"(pembuat|pencipta|developer|creator)\s*(bot|nya)\s*(siapa|ini)",
    r"siapa\s+(pembuat|pencipta|developer|creator)\s*(bot|nya)?",
]
_CREATOR_RE = re.compile("|".join(f"({p})" for p in _CREATOR_PATTERNS), re.IGNORECASE)


def _is_asking_about_creator(text: str) -> bool:
    """Return True if the message is asking who made/created the bot."""
    return bool(_CREATOR_RE.search(text))


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
    from_id = data.get("from", "")
    is_group = data.get("isGroup", False)

    # Determine the chat to reply to
    chat_id = data.get("chatId") or from_id

    # In group chats, the actual sender is in 'sender' or 'author', not 'from'
    # In private chats, 'from' is the sender
    sender_id = data.get("sender") or data.get("author") or from_id

    # Extract phone number (strip @c.us / @g.us suffix)
    phone = from_id.split("@")[0] if "@" in from_id else from_id

    logger.info("📩 Message from %s (sender=%s, chatId=%s): %s", from_id, sender_id, chat_id, raw_body)

    # ── Group mention filter ─────────────────────────────────
    # In group chats, only respond when the bot is @mentioned.
    # Strip the @mention tag from the message so commands parse normally.
    if is_group:
        mentioned_jids = (
            data.get("mentionedJidList")
            or data.get("mentionedJids")
            or []
        )
        bot_jid = f"{BOT_PHONE}@c.us" if BOT_PHONE else ""

        # WhatsApp uses LID (Linked ID) for @mentions in the body,
        # e.g. "@39656188063751 hello" instead of "@628xxx hello".
        # Check both BOT_LID and BOT_PHONE for compatibility.
        bot_mentioned = (
            (bot_jid and bot_jid in mentioned_jids)
            or (BOT_LID and f"@{BOT_LID}" in raw_body)
            or (BOT_PHONE and f"@{BOT_PHONE}" in raw_body)
        )

        if not bot_mentioned:
            logger.info("⏭️ Group message without bot mention, skipping")
            return

        # Strip the @mention tag from the message body so commands parse cleanly
        if BOT_LID and f"@{BOT_LID}" in raw_body:
            raw_body = raw_body.replace(f"@{BOT_LID}", "").strip()
        elif BOT_PHONE and f"@{BOT_PHONE}" in raw_body:
            raw_body = raw_body.replace(f"@{BOT_PHONE}", "").strip()
        else:
            # Fallback: strip the first @mention token
            raw_body = re.sub(r"@\S+", "", raw_body, count=1).strip()

    body = raw_body.lower()

    # ── Determine if sender is admin ────────────────────────
    from users import is_admin
    user_is_admin = is_admin(chat_id) or is_admin(sender_id)

    # ── Maintenance mode commands (admin only) ────────────────
    if body == "maintenance on":
        if not user_is_admin:
            return send_text(chat_id, "❌ Akses ditolak. Hanya admin yang bisa mengubah mode maintenance.")
        set_maintenance(True)
        return send_text(chat_id, "🔧 *Maintenance mode AKTIF*\n\nBot tidak akan merespons pengguna biasa sampai maintenance dimatikan.")

    elif body == "maintenance off":
        if not user_is_admin:
            return send_text(chat_id, "❌ Akses ditolak. Hanya admin yang bisa mengubah mode maintenance.")
        set_maintenance(False)
        return send_text(chat_id, "✅ *Maintenance mode NONAKTIF*\n\nBot kembali aktif untuk semua pengguna.")

    elif body == "maintenance status":
        if not user_is_admin:
            return send_text(chat_id, "❌ Akses ditolak.")
        status = "🔧 AKTIF" if is_maintenance() else "✅ NONAKTIF"
        return send_text(chat_id, f"Status maintenance: {status}")

    # ── Maintenance mode gate ─────────────────────────────────
    # Block non-admin users when maintenance is active
    if is_maintenance() and not user_is_admin:
        send_text(chat_id, "🔧 *Bot sedang dalam maintenance*\n\nMohon maaf, bot sedang dalam perbaikan. Silakan coba lagi nanti. 🙏")
        return

    # ── Command routing ──────────────────────────────────────
    if body.startswith("set ambri pass "):
        cmd_set_password(chat_id, phone, raw_body)

    elif body.startswith("set ambri totp "):
        cmd_set_totp(chat_id, phone, raw_body)

    elif body == "generate code":
        cmd_generate_code(chat_id, phone)

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
            "🏃‍♂️ *Attendance*\n"
            "• *checkin [alias]* - Absen masuk\n"
            "• *checkout [alias]* - Absen pulang\n"
            "• *list history [alias] [week/month]* - Cek riwayat\n\n"
            "⚙️ *Konfigurasi*\n"
            "• *set auto on/off [alias]* - Set automasi harian\n"
            "• *set checkin timerange [alias] HH:MM HH:MM* - Waktu acak masuk\n"
            "• *set checkout timerange [alias] HH:MM HH:MM* - Waktu acak pulang\n"
            "• *set notes [alias] [notes]* - Custom notes absen\n"
            "• *clear notes [alias]* - Reset notes absen\n"
            "• *set location [alias] [ID/nama]* - Set lokasi default\n\n"
            "📍 *Lokasi*\n"
            "• *list location* - Lihat daftar semua lokasi\n"
            "• *add location [nama] [lat,lng]* - Tambah lokasi baru\n\n"
            "👥 *User Management*\n"
            "• *list users* - Lihat user terdaftar\n"
            "• *add user <alias> <user> <pass> <imei>* - Tambah user\n"
            "• *login [alias]* - Login paksa/refresh token\n"
            "• *register imei [alias]* - Daftarkan IMEI saat ini\n"
            "• *generate device id [alias]* - Generate IMEI baru\n\n"
            "🔐 *Login Code*\n"
            "• *set ambri pass <password>* — Set your password\n"
            "• *set ambri totp <secret>* — Set your TOTP secret\n"
            "• *generate code* — Get your login code\n\n"
            "🧠 *AI Chat*\n"
            "• _Just send any normal message and the AI will reply!_\n\n"
            "🔧 *Maintenance (Admin)*\n"
            "• *maintenance on* — Aktifkan mode maintenance\n"
            "• *maintenance off* — Matikan mode maintenance\n"
            "• *maintenance status* — Cek status maintenance\n\n"
            "Made with 🤖 and ❤️\n"
            "By Sandroid"
        )
        send_text(chat_id, help_text)

    # ── Attendance routing ───────────────────────────────────
    elif body.startswith("add user "):
        ah.adduser_cmd(send_text, chat_id, raw_body)
    elif body.startswith("login "):
        ah.login_cmd(send_text, chat_id, raw_body)
    elif body.startswith("register imei "):
        ah.register_imei_cmd(send_text, chat_id, raw_body)
    elif body.startswith("generate device id"):
        ah.gendeviceid_cmd(send_text, chat_id, raw_body)
    elif body.startswith("checkin ") or body == "checkin":
        ah.masuk_cmd(send_text, chat_id, raw_body)
    elif body.startswith("checkout ") or body == "checkout":
        ah.pulang_cmd(send_text, chat_id, raw_body)
    elif body.startswith("list history"):
        ah.history_cmd(send_text, chat_id, raw_body)
    elif body.startswith("set auto"):
        ah.auto_cmd(send_text, chat_id, raw_body)
    elif body.startswith("set checkin timerange"):
        ah.set_checkin_timerange_cmd(send_text, chat_id, raw_body)
    elif body.startswith("set checkout timerange"):
        ah.set_checkout_timerange_cmd(send_text, chat_id, raw_body)
    elif body.startswith("set notes "):
        ah.setnotes_cmd(send_text, chat_id, raw_body)
    elif body.startswith("clear notes "):
        ah.clearnotes_cmd(send_text, chat_id, raw_body)
    elif body.startswith("set location "):
        ah.setlocation_cmd(send_text, chat_id, raw_body)
    elif body == "list location":
        ah.location_list_cmd(send_text, chat_id)
    elif body.startswith("add location "):
        ah.addlocation_cmd(send_text, chat_id, raw_body)
    elif body == "list users":
        ah.users_cmd(send_text, chat_id)

    # ── "Who made the bot?" detector ────────────────────────
    elif _is_asking_about_creator(body):
        send_text(chat_id, "🤖 Bot ini dibuat oleh *Sandroid* ✨\n\nMade with 🤖 and ❤️")

    else:
        # Default fallback: Treat as an AI prompt
        cmd_ai(chat_id, raw_body, data.get("media"))


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
        threading.Thread(target=handle_message, args=(data,)).start()
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

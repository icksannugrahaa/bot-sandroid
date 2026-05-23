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
from users import is_admin
import rbac
from automation import is_maintenance, set_maintenance

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


def cmd_spam(chat_id: str, raw_body: str, sender_id: str, pushname: str = "") -> None:
    """Handle: spam <nomor_wa> [jumlah]"""
    parts = raw_body.split()
    if len(parts) < 2:
        send_text(chat_id, "⚠️ Usage: *spam <nomor_wa> [jumlah]*\nContoh: *spam 628123456789 3*\n_(Maksimal 5 untuk mencegah ban)_")
        return
        
    target = parts[1].strip()
    import re
    target = re.sub(r'\D', '', target)
    if not target:
        return send_text(chat_id, "⚠️ Nomor tidak valid.")
        
    target_chat_id = f"{target}@c.us"
    
    count = 3
    if len(parts) >= 3 and parts[2].isdigit():
        count = int(parts[2])
        
    # LIMIT MAX SPAM
    MAX_SPAM = 5
    if count > MAX_SPAM:
        send_text(chat_id, f"⚠️ Jumlah terlalu banyak! Dibatasi maksimal {MAX_SPAM} pesan untuk mencegah bot dibanned.")
        count = MAX_SPAM
        
    if count < 1:
        count = 1

    # Coba cari username user di database attendance
    import storage
    users = storage.get_attendance_users()
    display_name = ""
    for alias, u in users.items():
        if u.get("owner_chat_id") == sender_id:
            display_name = u.get("username")
            break

    # Format the caller's name/link safely
    if display_name:
        if display_name.isdigit():
            clean_num = display_name
            if clean_num.startswith("08"):
                clean_num = "628" + clean_num[2:]
            caller_display = f"wa.me/{clean_num}"
        else:
            caller_display = f"*{display_name}*"
    elif pushname:
        caller_display = f"*{pushname}*"
    elif "@lid" in sender_id:
        caller_display = "seseorang"
    else:
        # It's a normal @c.us phone number
        caller_display = f"wa.me/{sender_id.split('@')[0]}"
    
    send_text(chat_id, f"⏳ Sedang mengirim {count} pesan ke {target}...")
    
    def _spam_worker():
        import time
        for i in range(count):
            send_text(target_chat_id, f"🚨 *PANGGILAN URGENT!* 🚨\nKamu dipanggil oleh {caller_display}! Tolong cek WhatsApp sekarang. ({i+1}/{count})")
            time.sleep(2)
        send_text(chat_id, f"✅ Selesai mengirim {count} pesan ke {target}")

    threading.Thread(target=_spam_worker).start()


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
    user_is_admin = is_admin(chat_id) or is_admin(sender_id)

    # ── Maintenance mode commands (admin only) ────────────────
    if body.startswith("maintenance on"):
        if check_rbac("user_management"):
            set_maintenance(True)
            send_text(chat_id, "🔧 Mode maintenance AKTIF.\nSemua command dari non-admin akan diblokir.")
    elif body.startswith("maintenance off"):
        if check_rbac("user_management"):
            set_maintenance(False)
            send_text(chat_id, "✅ Mode maintenance NONAKTIF.\nBot dapat digunakan kembali oleh semua user.")
    elif body == "maintenance status" or body == "maintenance":
        if check_rbac("user_management"):
            status = "AKTIF 🔴" if is_maintenance() else "NONAKTIF 🟢"
            send_text(chat_id, f"🔧 Status Maintenance saat ini: *{status}*")

    # ── Maintenance mode gate ─────────────────────────────────
    # Block non-admin users when maintenance is active
    if is_maintenance() and not user_is_admin:
        send_text(chat_id, "🔧 *Bot sedang dalam maintenance*\n\nMohon maaf, bot sedang dalam perbaikan. Silakan coba lagi nanti. 🙏")
        return

    def check_rbac(feature: str) -> bool:
        if rbac.has_permission(sender_id, feature):
            return True
        send_text(chat_id, f"❌ Anda tidak memiliki akses ke fitur: *{feature}*")
        return False

    # ── Command routing ──────────────────────────────────────
    if body.startswith("set ambri pass "):
        if check_rbac("login_code"):
            cmd_set_password(chat_id, phone, raw_body)

    elif body.startswith("set ambri totp "):
        if check_rbac("login_code"):
            cmd_set_totp(chat_id, phone, raw_body)

    elif body == "generate code":
        if check_rbac("login_code"):
            cmd_generate_code(chat_id, phone)

    elif body == "hello":
        send_text(chat_id, "hello too 👋")

    elif body == "ping":
        send_text(chat_id, "pong 🏓")
        
    elif body.startswith("spam "):
        if check_rbac("spam"):
            pushname = data.get("pushname") or data.get("notifyName") or ""
            cmd_spam(chat_id, raw_body, sender_id, pushname)

    elif body == "help":
        lines = ["🤖 *Bot Commands*\n"]
        lines.append("📋 *General*")
        lines.append("• *hello* — Say hello")
        lines.append("• *ping* — Check if bot is alive")
        
        # We don't use check_rbac here to avoid sending an error message to the user,
        # we just want to silently check if they have permission to see it.
        if rbac.has_permission(sender_id, "spam"):
            lines.append("• *spam <nomor> [jumlah]* — Spam pesan (max 5)")
            
        lines.append("• *help* — Show this help message\n")

        if rbac.has_permission(sender_id, "attendance"):
            lines.append("🏃‍♂️ *Attendance*")
            lines.append("• *checkin [alias]* - Absen masuk")
            lines.append("• *checkout [alias]* - Absen pulang")
            lines.append("• *list history [alias] [week/month]* - Cek riwayat\n")

        if rbac.has_permission(sender_id, "konfigurasi"):
            lines.append("⚙️ *Konfigurasi*")
            lines.append("• *set auto on/off [alias]* - Set automasi harian")
            lines.append("• *set checkin timerange [alias] HH:MM HH:MM* - Waktu acak masuk")
            lines.append("• *set checkout timerange [alias] HH:MM HH:MM* - Waktu acak pulang")
            lines.append("• *set notes [alias] [notes]* - Custom notes absen")
            lines.append("• *clear notes [alias]* - Reset notes absen\n")

        if rbac.has_permission(sender_id, "lokasi"):
            lines.append("📍 *Lokasi*")
            lines.append("• *list location* - Lihat daftar semua lokasi")
            lines.append("• *add location [nama] [lat,lng]* - Tambah lokasi baru\n")

        if rbac.has_permission(sender_id, "user_management"):
            lines.append("👥 *User Management*")
            lines.append("• *list users* - Lihat user terdaftar")
            lines.append("• *add user <alias> <user> <pass> <imei>* - Tambah user")
            lines.append("• *login [alias]* - Login paksa/refresh token")
            lines.append("• *register imei [alias]* - Daftarkan IMEI saat ini")
            lines.append("• *generate device id [alias]* - Generate IMEI baru\n")

        if rbac.has_permission(sender_id, "login_code"):
            lines.append("🔐 *Login Code*")
            lines.append("• *set ambri pass <password>* — Set your password")
            lines.append("• *set ambri totp <secret>* — Set your TOTP secret")
            lines.append("• *generate code* — Get your login code\n")

        if rbac.has_permission(sender_id, "rbac"):
            lines.append("🛡️ *RBAC (Access Control)*")
            lines.append("• *rbac download* — Download template Excel RBAC")
            lines.append("• *(kirim file Excel)* + *rbac upload* — Upload & Terapkan RBAC")
            lines.append("• *set role <nomor> <role>* — Ubah role pengguna\n")

        if rbac.has_permission(sender_id, "ai"):
            lines.append("🧠 *AI Chat*")
            lines.append("• _Just send any normal message and the AI will reply!_\n")

        if rbac.has_permission(sender_id, "user_management"):
            lines.append("🔧 *Maintenance (Admin)*")
            lines.append("• *maintenance on* — Aktifkan mode maintenance")
            lines.append("• *maintenance off* — Matikan mode maintenance")
            lines.append("• *maintenance status* — Cek status maintenance\n")

        lines.append("Made with 🤖 and ❤️\nBy Sandroid")
        
        help_text = "\n".join(lines)
        send_text(chat_id, help_text)

    # ── Attendance routing ───────────────────────────────────
    elif body.startswith("add user "):
        if check_rbac("user_management"):
            ah.adduser_cmd(send_text, chat_id, raw_body)
    elif body.startswith("login "):
        if check_rbac("user_management"):
            ah.login_cmd(send_text, chat_id, raw_body)
    elif body.startswith("register imei "):
        if check_rbac("user_management"):
            ah.register_imei_cmd(send_text, chat_id, raw_body)
    elif body.startswith("generate device id"):
        if check_rbac("user_management"):
            ah.gendeviceid_cmd(send_text, chat_id, raw_body)
    elif body.startswith("checkin ") or body == "checkin":
        if check_rbac("attendance"):
            ah.masuk_cmd(send_text, chat_id, raw_body)
    elif body.startswith("checkout ") or body == "checkout":
        if check_rbac("attendance"):
            ah.pulang_cmd(send_text, chat_id, raw_body)
    elif body.startswith("list history"):
        if check_rbac("attendance"):
            ah.history_cmd(send_text, chat_id, raw_body)
    elif body.startswith("set auto"):
        if check_rbac("attendance"):
            ah.auto_cmd(send_text, chat_id, raw_body)
    elif body.startswith("set checkin timerange"):
        if check_rbac("konfigurasi"):
            ah.set_checkin_timerange_cmd(send_text, chat_id, raw_body)
    elif body.startswith("set checkout timerange"):
        if check_rbac("konfigurasi"):
            ah.set_checkout_timerange_cmd(send_text, chat_id, raw_body)
    elif body.startswith("set notes "):
        if check_rbac("konfigurasi"):
            ah.setnotes_cmd(send_text, chat_id, raw_body)
    elif body.startswith("clear notes "):
        if check_rbac("konfigurasi"):
            ah.clearnotes_cmd(send_text, chat_id, raw_body)
    elif body.startswith("set location "):
        if check_rbac("lokasi"):
            ah.setlocation_cmd(send_text, chat_id, raw_body)
    elif body == "list location":
        if check_rbac("lokasi"):
            ah.location_list_cmd(send_text, chat_id)
    elif body.startswith("add location "):
        if check_rbac("lokasi"):
            ah.addlocation_cmd(send_text, chat_id, raw_body)
    elif body == "list users":
        if check_rbac("user_management"):
            ah.users_cmd(send_text, chat_id)

    # ── RBAC routing ─────────────────────────────────────────
    elif body == "rbac download":
        if check_rbac("rbac"):
            send_text(chat_id, "⏳ Generating RBAC Excel template...")
            b64_data = rbac.generate_template_b64()
            import whatsapp
            whatsapp.send_file(
                chat_id=chat_id,
                base64_data=b64_data,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename="rbac_template.xlsx",
                caption="✅ Ini adalah konfigurasi RBAC saat ini. Edit dan kirim kembali file ini dengan caption `rbac upload`."
            )
            
    elif body == "rbac upload":
        if check_rbac("rbac"):
            media = data.get("media")
            if media and "data" in media:
                base64_data = media["data"]
                send_text(chat_id, "⏳ Memproses file RBAC...")
                msg = rbac.parse_template_b64(base64_data)
                send_text(chat_id, msg)
            else:
                send_text(chat_id, "❌ Tidak ada file document/excel yang dilampirkan. Pastikan Anda melampirkan file Excel saat mengetik `rbac upload`.")
                
    elif body.startswith("set role "):
        if check_rbac("rbac"):
            # format: set role 628123 admin
            parts = body.split(maxsplit=3)
            if len(parts) >= 4:
                target_number = parts[2]
                role_name = parts[3]
                msg = rbac.assign_role(sender_id, target_number, role_name)
                send_text(chat_id, msg)
            else:
                send_text(chat_id, "⚠️ Usage: *set role <nomor> <role_name>*\nContoh: *set role 628123 admin*")

    # ── "Who made the bot?" detector ────────────────────────
    elif _is_asking_about_creator(body):
        send_text(chat_id, "🤖 Bot ini dibuat oleh *Sandroid* ✨\n\nMade with 🤖 and ❤️")

    else:
        # Default fallback: Treat as an AI prompt
        if check_rbac("ai"):
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

import os
from dotenv import load_dotenv

_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(_env_path)

EMAIL_CONFIG = {
    "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    "smtp_port": int(os.getenv("SMTP_PORT", 465)),
    "sender_email": os.getenv("SENDER_EMAIL", ""),
    "receiver_email": os.getenv("RECEIVER_EMAIL", ""),
    "app_password": os.getenv("GMAIL_APP_PASSWORD", "")
}


ADMIN_CHAT_IDS = [
    c.strip() for c in os.getenv("ADMIN_CHAT_IDS", "").split(",") if c.strip()
]

BASE_URL = os.getenv("BASE_URL", "https://starbridges.indocyber.co.id")

# API Endpoints
URL_VALIDASI_LOGIN = f"{BASE_URL}/ESS/api/Attendance/ValidasiLogin"
URL_TOKEN = f"{BASE_URL}/ESS/token"
URL_REGISTER_IMEI = f"{BASE_URL}/ESS/api/Attendance/RegisterIMEI"
URL_ABSENCE = f"{BASE_URL}/ESS/api/Attendance/Absence"
URL_HISTORY = f"{BASE_URL}/ESS/api/Attendance/History"

TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

_hash_raw = os.getenv("ADMIN_SERVICE_PASSWORD_HASH", "")
ADMIN_SERVICE_PASSWORD_HASH = _hash_raw.encode() if _hash_raw else b""

SERVICE_NAME = os.getenv("SERVICE_NAME", "attendance-bot")
_DEFAULT_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log")
LOG_PATH = os.getenv("LOG_PATH", _DEFAULT_LOG_PATH)
AUDIT_LOG_FILE = os.path.join(LOG_PATH, "audit.log")
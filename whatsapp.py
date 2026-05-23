import os
import requests
import logging
from dotenv import load_dotenv

_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(_env_path)

logger = logging.getLogger(__name__)

OPENWA_BASE_URL = os.getenv("OPENWA_BASE_URL", "http://localhost:2785")
OPENWA_API_KEY = os.getenv("OPENWA_API_KEY", "YOUR_API_KEY")
OPENWA_SESSION_ID = os.getenv("OPENWA_SESSION_ID", "YOUR_SESSION_ID")

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

def send_file(chat_id: str, base64_data: str, mimetype: str, filename: str, caption: str = "") -> dict:
    """Send a file (base64) through the OpenWA API."""
    url = f"{OPENWA_BASE_URL}/api/sessions/{OPENWA_SESSION_ID}/messages/send-file"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": OPENWA_API_KEY,
    }
    
    # OpenWA requires the file to be a data URI
    data_uri = f"data:{mimetype};base64,{base64_data}"
    
    payload = {
        "chatId": chat_id,
        "file": data_uri,
        "filename": filename,
        "caption": caption
    }

    logger.info("📤 Sending file to %s | chatId=%s | filename=%s", url, chat_id, filename)

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        logger.info("✅ File sent to %s: %s", chat_id, filename)
        return data
    except requests.HTTPError as exc:
        error_body = exc.response.text if exc.response is not None else "no response body"
        logger.error("❌ HTTP %s for %s: %s", exc.response.status_code if exc.response else '?', chat_id, error_body)
        return {"success": False, "error": error_body}
    except requests.RequestException as exc:
        logger.error("❌ Request failed for %s: %s", chat_id, exc)
        return {"success": False, "error": str(exc)}

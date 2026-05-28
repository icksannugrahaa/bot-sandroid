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
        resp_obj = exc.response
        status = resp_obj.status_code if resp_obj is not None else "unknown"
        error_body = resp_obj.text if resp_obj is not None else "no response body"
        logger.error("❌ HTTP %s for %s: %s", status, chat_id, error_body)
        return {"success": False, "error": error_body}

    except requests.RequestException as exc:
        logger.error("❌ Request failed for %s: %s", chat_id, exc)
        return {"success": False, "error": str(exc)}

def send_file(chat_id: str, base64_data: str, mimetype: str, filename: str, caption: str = "") -> dict:
    """Send a file (base64) through the OpenWA API."""
    url = f"{OPENWA_BASE_URL}/api/sessions/{OPENWA_SESSION_ID}/messages/send-document"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": OPENWA_API_KEY,
    }
    
    payload = {
        "chatId": chat_id,
        "base64": base64_data,
        "mimetype": mimetype,
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

def create_group(name: str, participants: list) -> dict:
    url = f"{OPENWA_BASE_URL}/api/sessions/{OPENWA_SESSION_ID}/groups"
    headers = {"Content-Type": "application/json", "X-API-Key": OPENWA_API_KEY}
    payload = {"name": name, "participants": participants}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as exc:
        error_body = exc.response.text if exc.response is not None else "no response body"
        logger.error("❌ HTTP %s for group create: %s", exc.response.status_code if exc.response else '?', error_body)
        return {"success": False, "error": error_body}

def get_group_invite_code(group_id: str) -> str:
    url = f"{OPENWA_BASE_URL}/api/sessions/{OPENWA_SESSION_ID}/groups/{group_id}/invite-code"
    headers = {"X-API-Key": OPENWA_API_KEY}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return f"https://chat.whatsapp.com/{data}"
    except Exception as exc:
        logger.error("❌ Failed to get invite code for %s: %s", group_id, exc)
        return ""
    except Exception as exc:
        logger.error("❌ Failed to create group: %s", exc)
        return {"success": False, "error": str(exc)}

def update_group(group_id: str, name: str = None, description: str = None) -> dict:
    headers = {"Content-Type": "application/json", "X-API-Key": OPENWA_API_KEY}
    success = True
    errors = []
    
    if name:
        url = f"{OPENWA_BASE_URL}/api/sessions/{OPENWA_SESSION_ID}/groups/{group_id}/subject"
        try:
            resp = requests.put(url, json={"subject": name}, headers=headers, timeout=30)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("❌ Failed to update group name %s: %s", group_id, exc)
            success = False
            errors.append(str(exc))
            
    if description:
        # Note: OpenWA doesn't have an endpoint for description in the same payload, it's a separate PUT.
        # However, following the spec, we attempt it if it exists.
        payload = {"description": description}
        url_desc = f"{OPENWA_BASE_URL}/api/sessions/{OPENWA_SESSION_ID}/groups/{group_id}/description"
        try:
            resp_desc = requests.put(url_desc, json=payload, headers=headers, timeout=30)
            resp_desc.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            success = False
            errors.append(f"description error: {exc.response.text if exc.response is not None else 'no body'}")
        except Exception as exc:
            success = False
            errors.append(str(exc))
            
    if not success:
        return {"success": False, "error": "; ".join(errors)}
    return {"success": True}

def set_group_messages_setting(group_id: str, admins_only: bool) -> dict:
    url = f"{OPENWA_BASE_URL}/api/sessions/{OPENWA_SESSION_ID}/groups/{group_id}/settings/messages"
    headers = {"Content-Type": "application/json", "X-API-Key": OPENWA_API_KEY}
    payload = {"adminsOnly": admins_only}
    try:
        resp = requests.put(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as exc:
        error_body = exc.response.text if exc.response is not None else "no response body"
        logger.error("❌ Failed to set group messages setting for %s: %s", group_id, error_body)
        return {"success": False, "error": error_body}
    except Exception as exc:
        logger.error("❌ Failed to set group messages setting for %s: %s", group_id, exc)
        return {"success": False, "error": str(exc)}

def get_group_info(group_id: str) -> dict:
    url = f"{OPENWA_BASE_URL}/api/sessions/{OPENWA_SESSION_ID}/groups/{group_id}"
    headers = {"X-API-Key": OPENWA_API_KEY}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return {"success": True, "data": resp.json()}
    except Exception as exc:
        logger.error("❌ Failed to get group info %s: %s", group_id, exc)
        return {"success": False, "error": str(exc)}

def get_contact_info(contact_id: str) -> dict:
    url = f"{OPENWA_BASE_URL}/api/sessions/{OPENWA_SESSION_ID}/contacts/{contact_id}"
    headers = {"X-API-Key": OPENWA_API_KEY}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return {"success": True, "data": resp.json()}
    except Exception as exc:
        logger.error("❌ Failed to get contact info %s: %s", contact_id, exc)
        return {"success": False, "error": str(exc)}

def leave_group(group_id: str) -> dict:
    url = f"{OPENWA_BASE_URL}/api/sessions/{OPENWA_SESSION_ID}/groups/{group_id}/leave"
    headers = {"X-API-Key": OPENWA_API_KEY}
    try:
        resp = requests.post(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error("❌ Failed to leave group %s: %s", group_id, exc)
        return {"success": False, "error": str(exc)}

def add_group_admin(group_id: str, participants: list) -> dict:
    url = f"{OPENWA_BASE_URL}/api/sessions/{OPENWA_SESSION_ID}/groups/{group_id}/participants/promote"
    headers = {"Content-Type": "application/json", "X-API-Key": OPENWA_API_KEY}
    payload = {"participants": participants}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error("❌ Failed to add admin to group %s: %s", group_id, exc)
        return {"success": False, "error": str(exc)}

def remove_group_admin(group_id: str, participants: list) -> dict:
    url = f"{OPENWA_BASE_URL}/api/sessions/{OPENWA_SESSION_ID}/groups/{group_id}/participants/demote"
    headers = {"Content-Type": "application/json", "X-API-Key": OPENWA_API_KEY}
    payload = {"participants": participants}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error("❌ Failed to remove admin from group %s: %s", group_id, exc)
        return {"success": False, "error": str(exc)}

def add_group_participant(group_id: str, participants: list) -> dict:
    url = f"{OPENWA_BASE_URL}/api/sessions/{OPENWA_SESSION_ID}/groups/{group_id}/participants"
    headers = {"Content-Type": "application/json", "X-API-Key": OPENWA_API_KEY}
    payload = {"participants": participants}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error("❌ Failed to add participant to group %s: %s", group_id, exc)
        return {"success": False, "error": str(exc)}

def remove_group_participant(group_id: str, participants: list) -> dict:
    import json
    url = f"{OPENWA_BASE_URL}/api/sessions/{OPENWA_SESSION_ID}/groups/{group_id}/participants"
    headers = {"Content-Type": "application/json", "X-API-Key": OPENWA_API_KEY}
    payload = {"participants": participants}
    try:
        resp = requests.request("DELETE", url, data=json.dumps(payload), headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as exc:
        err_msg = str(exc)
        if exc.response is not None:
            err_msg += f" - {exc.response.text}"
        logger.error("❌ Failed to remove participant from group %s: %s", group_id, err_msg)
        return {"success": False, "error": err_msg}

def delete_message(chat_id: str, message_id: str, for_everyone: bool = True) -> dict:
    url = f"{OPENWA_BASE_URL}/api/sessions/{OPENWA_SESSION_ID}/messages/delete"
    headers = {"Content-Type": "application/json", "X-API-Key": OPENWA_API_KEY}
    payload = {
        "chatId": chat_id,
        "messageId": message_id,
        "forEveryone": for_everyone
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error("❌ Failed to delete message %s: %s", message_id, exc)
        return {"success": False, "error": str(exc)}

def update_group_picture(group_id: str, base64_data: str, mimetype: str) -> dict:
    url = f"{OPENWA_BASE_URL}/api/sessions/{OPENWA_SESSION_ID}/groups/{group_id}/picture"
    headers = {"Content-Type": "application/json", "X-API-Key": OPENWA_API_KEY}
    payload = {"base64": base64_data, "mimetype": mimetype}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error("❌ Failed to update group picture %s: %s", group_id, exc)
        return {"success": False, "error": str(exc)}


def get_profile_pic(contact_id: str) -> str | None:
    """
    Fetch the profile picture URL for a contact (phone @c.us or @lid).
    Returns the URL string on success, or None if unavailable / API error.
    This call is non-blocking-safe: all exceptions are caught internally.
    """
    url = f"{OPENWA_BASE_URL}/api/sessions/{OPENWA_SESSION_ID}/contacts/{contact_id}/profile-picture"
    headers = {"X-API-Key": OPENWA_API_KEY}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # OpenWA typically returns {"success": true, "data": {"eurl": "https://..."}}
        pic_url = (
            data.get("eurl")
            or data.get("url")
            or (data.get("data") or {}).get("eurl")
            or (data.get("data") or {}).get("url")
        )
        return pic_url if pic_url else None
    except Exception as exc:
        logger.warning("⚠️ Could not fetch profile pic for %s: %s", contact_id, exc)
        return None



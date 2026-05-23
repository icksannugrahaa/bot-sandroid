import storage
from config import ADMIN_CHAT_IDS

def is_admin(chat_id: str) -> bool:
    return chat_id in ADMIN_CHAT_IDS

def get_authorized_alias(chat_id: str, alias: str | None) -> str:
    """
    Returns an authorized alias for the chat_id.
    - If alias is given, checks if user owns it or is admin.
    - If alias is None, finds the only alias owned by the user.
    """
    users = storage.get_attendance_users()
    
    if alias:
        if alias not in users:
            raise Exception(f"Alias '{alias}' tidak ditemukan.")
        owner = users[alias].get("owner_chat_id")
        if owner == chat_id or is_admin(chat_id):
            return alias
        raise PermissionError(f"Anda tidak memiliki akses ke alias '{alias}'.")
    
    # If no alias provided
    owned_aliases = [a for a, u in users.items() if u.get("owner_chat_id") == chat_id]
    
    if len(owned_aliases) == 1:
        return owned_aliases[0]
    elif len(owned_aliases) > 1:
        raise Exception("Anda memiliki lebih dari 1 alias. Harap sebutkan alias spesifik di command Anda.")
    else:
        # 0 owned aliases
        if is_admin(chat_id):
            # Admin might be trying to use default without owning it
            # To be safe, force them to specify alias if they own none.
            raise Exception("Harap sebutkan alias spesifik di command Anda.")
        raise Exception("Anda belum mendaftarkan alias apapun. Silakan 'add user' terlebih dahulu.")

def load_users():
    return storage.get_attendance_users()

def add_user(alias: str, username: str, password: str, imei: str, owner_chat_id: str):
    data = {
        "username": username,
        "password": password,
        "imei": imei,
        "active": True,
        "automation": False,
        "location_pool": "kanpus",
        "checkin_timerange": None,
        "checkout_timerange": None,
        "notes": None,
        "owner_chat_id": owner_chat_id
    }
    storage.upsert_attendance_user(alias, data)

def get_user(alias: str):
    return storage.get_attendance_user(alias)

def list_users(chat_id: str):
    users = storage.get_attendance_users()
    if is_admin(chat_id):
        return users
    return {a: u for a, u in users.items() if u.get("owner_chat_id") == chat_id}

def set_automation(alias: str, enabled: bool):
    user = storage.get_attendance_user(alias)
    if not user:
        return False
    user["automation"] = enabled
    storage.upsert_attendance_user(alias, user)
    return True

def set_notes(alias: str, notes: str | None):
    user = storage.get_attendance_user(alias)
    if not user:
        return False
    user["notes"] = notes
    storage.upsert_attendance_user(alias, user)
    return True

def set_imei(alias: str, imei: str) -> bool:
    user = storage.get_attendance_user(alias)
    if not user:
        return False
    user["imei"] = imei
    storage.upsert_attendance_user(alias, user)
    return True

def set_location_pool(alias: str, pool_name: str) -> bool:
    user = storage.get_attendance_user(alias)
    if not user:
        return False
    user["location_pool"] = pool_name.lower()
    storage.upsert_attendance_user(alias, user)
    return True

def set_checkin_timerange(alias: str, start_time: str, end_time: str) -> bool:
    user = storage.get_attendance_user(alias)
    if not user:
        return False
    user["checkin_timerange"] = f"{start_time}-{end_time}"
    storage.upsert_attendance_user(alias, user)
    return True

def set_checkout_timerange(alias: str, start_time: str, end_time: str) -> bool:
    user = storage.get_attendance_user(alias)
    if not user:
        return False
    user["checkout_timerange"] = f"{start_time}-{end_time}"
    storage.upsert_attendance_user(alias, user)
    return True

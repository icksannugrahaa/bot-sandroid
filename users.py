import storage

def load_users():
    return storage.get_attendance_users()

def add_user(alias: str, username: str, password: str, imei: str):
    data = {
        "username": username,
        "password": password,
        "imei": imei,
        "active": True,
        "automation": False,
        "location_pool": "kanpus",
        "checkin_timerange": None,
        "checkout_timerange": None,
        "notes": None
    }
    storage.upsert_attendance_user(alias, data)

def get_user(alias: str):
    return storage.get_attendance_user(alias)

def list_users():
    return storage.get_attendance_users()

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

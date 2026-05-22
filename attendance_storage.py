# attendance_storage.py
import random
from datetime import datetime, timezone
import storage

# ======================
# TOKEN
# ======================

def save_token(alias: str, data: dict):
    storage.save_attendance_token(alias, data)

def load_token(alias: str):
    return storage.get_attendance_token(alias)


def is_token_expired(token: dict) -> bool:
    expires_at = datetime.fromisoformat(token["expires_at"])
    return datetime.now(timezone.utc) >= expires_at


# ======================
# STATUS
# ======================

def _load_status(alias: str) -> dict:
    return storage.get_attendance_status(alias)

def _save_status(alias: str, data: dict):
    storage.save_attendance_status(alias, data)


def is_already_checked_in(alias: str, date_key: str) -> bool:
    return _load_status(alias).get(date_key) == "IN"


def is_already_checked_out(alias: str, date_key: str) -> bool:
    return _load_status(alias).get(date_key) == "OUT"


def save_check_in(alias: str, date_key: str):
    data = _load_status(alias)
    data[date_key] = "IN"
    _save_status(alias, data)


def save_check_out(alias: str, date_key: str):
    data = _load_status(alias)
    data[date_key] = "OUT"
    _save_status(alias, data)

def get_or_create_time(alias: str, date_key: str, start, end):
    data = _load_status(alias)
    key = f"{date_key}:time:{start}-{end}"

    if key in data:
        return data[key]

    hour, minute = start
    end_hour, end_min = end

    base = hour * 60 + minute
    limit = end_hour * 60 + end_min
    picked = random.randint(base, limit)

    t = f"{picked//60:02d}:{picked%60:02d}:00"
    data[key] = t
    _save_status(alias, data)
    return t
